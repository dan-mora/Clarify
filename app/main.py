from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.chat.router import router as chat_router

app = FastAPI(title="Clarify", description="Patient communication aid")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app.include_router(chat_router)


@app.get("/")
async def serve_index():
    """Serve the main HTML page."""
    return FileResponse(STATIC_DIR / "index.html")


# Mount static files last so it doesn't swallow API routes
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
