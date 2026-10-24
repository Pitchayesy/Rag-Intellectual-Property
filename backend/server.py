#!/usr/bin/env python3
"""FastAPI backend bridging the frontend with the legal RAG system.

Endpoints:
    GET  /health            -> {"status": "ok"}
    GET  /v1/models         -> list of embedding + chat models
    POST /api/chat          -> {"answer": "...", "sources": [...]}
    GET  /                  -> chat.html (frontend SPA)
    GET  /<path:file>       -> static files from frontend/

Usage:
    python backend/server.py            # http://127.0.0.1:8000
    python backend/server.py 8080       # custom port
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag import answer_question, EMBED_MODEL, CHAT_MODEL

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Shatter Legal RAG API", version="1.0.0")


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [
            {"id": EMBED_MODEL, "object": "model", "owned_by": "google"},
            {"id": CHAT_MODEL, "object": "model", "owned_by": "google"},
        ],
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    try:
        return answer_question(question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(FRONTEND_DIR / "chat.html")


# Static files (login.html, assets, etc.) — mounted last so API routes win
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True))


def main():
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Server running at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
