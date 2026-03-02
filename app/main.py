from fastapi import FastAPI
from app.chat.router import router as chat_router

app = FastAPI(title="Clarify", description="Patient communication aid")

# Mount the chat router so its endpoints are available under /chat
app.include_router(chat_router)


@app.get("/")
async def health_check():
    """Simple health check so we can verify the server is running."""
    return {"status": "ok", "app": "Clarify"}
