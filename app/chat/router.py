import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from app.config import client
from app.rag.store import query as rag_query

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory store: maps conversation_id -> conversation data.
# Each entry: {"messages": [{"role": ..., "content": ...}, ...], "private_session": bool}
conversations: dict[str, dict] = {}


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

    # Choose system prompt based on privacy mode (placeholder — refine later)
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


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Discard a conversation from memory."""
    conversations.pop(conversation_id, None)
    return {"status": "deleted"}
