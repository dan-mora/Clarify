import json
import uuid
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.config import async_client, client
from app.rag.store import query as rag_query

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory store: maps conversation_id -> conversation data.
# Each entry: {"messages": [{"role": ..., "content": ...}, ...], "private_session": bool}
conversations: dict[str, dict] = {}


def _prepare_chat(request):
    """Set up conversation state, run RAG retrieval, and build the system prompt.

    Returns (convo_id, system_prompt).
    """
    if request.conversation_id and request.conversation_id in conversations:
        convo_id = request.conversation_id
    else:
        convo_id = str(uuid.uuid4())
        conversations[convo_id] = {
            "messages": [],
            "private_session": request.private_session or False,
        }

    conversations[convo_id]["messages"].append(
        {"role": "user", "content": request.message}
    )

    # Retrieve relevant context from the RAG store
    relevant_chunks = rag_query(request.message)
    context = "\n\n---\n\n".join(c['text'] for c in relevant_chunks)

    print(f"\n[RAG] Query: {request.message[:80]}")
    for c in relevant_chunks:
        print(f"  → {c['metadata']['section_header']} ({c['metadata']['document_topic']})")

    if conversations[convo_id]["private_session"]:
        system_prompt = (
            "You are a helpful medical communication assistant. "
            "The patient is speaking with you privately. "
            "Help them articulate their symptoms and feelings clearly."
        )
    else:
        system_prompt = (
            "You are a helpful medical communication assistant. "
            "Help patients articulate their symptoms and feelings clearly."
        )

    if context:
        system_prompt += (
            "\n\nUse the following reference material to inform your responses. "
            "Do not quote it directly — use it to give accurate, helpful guidance.\n\n"
            + context
        )

    return convo_id, system_prompt


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    private_session: Optional[bool] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to Claude with full conversation history."""
    convo_id, system_prompt = _prepare_chat(request)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=conversations[convo_id]["messages"],
    )

    assistant_reply = response.content[0].text
    conversations[convo_id]["messages"].append(
        {"role": "assistant", "content": assistant_reply}
    )

    return ChatResponse(reply=assistant_reply, conversation_id=convo_id)


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream a response from Claude as Server-Sent Events."""
    convo_id, system_prompt = _prepare_chat(request)

    async def generate():
        # First event: send the conversation ID so the frontend can track it
        yield f"event: conversation_id\ndata: {json.dumps({'conversation_id': convo_id})}\n\n"

        full_reply = []
        async with async_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=conversations[convo_id]["messages"],
        ) as stream:
            async for text in stream.text_stream:
                full_reply.append(text)
                yield f"event: text_delta\ndata: {json.dumps({'text': text})}\n\n"

        # Save the complete reply to conversation history
        conversations[convo_id]["messages"].append(
            {"role": "assistant", "content": "".join(full_reply)}
        )
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Discard a conversation from memory."""
    conversations.pop(conversation_id, None)
    return {"status": "deleted"}
