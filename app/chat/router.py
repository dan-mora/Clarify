import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from app.config import client

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory store: maps conversation_id -> list of message dicts.
# Each message is {"role": "user"|"assistant", "content": "..."}
conversations: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to Claude with full conversation history."""
    # Start a new conversation or continue an existing one
    if request.conversation_id and request.conversation_id in conversations:
        convo_id = request.conversation_id
    else:
        convo_id = str(uuid.uuid4())
        conversations[convo_id] = []

    # Append the new user message to history
    conversations[convo_id].append({"role": "user", "content": request.message})

    # Send the full history to Claude
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system="You are a helpful medical communication assistant. Help patients articulate their symptoms and feelings clearly.",
        messages=conversations[convo_id],
    )

    assistant_reply = response.content[0].text

    # Append Claude's response to history
    conversations[convo_id].append({"role": "assistant", "content": assistant_reply})

    return ChatResponse(reply=assistant_reply, conversation_id=convo_id)
