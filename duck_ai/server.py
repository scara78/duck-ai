"""
FastAPI server that exposes free AI chat (DuckDuckGo / Pollinations) as your own
API-key-protected HTTP API. OpenAI-compatible too.

Endpoints:
  GET  /health
  GET  /v1/models
  POST /v1/chat              - simple {prompt|messages, model?} -> {text}
  POST /v1/chat/completions  - OpenAI-compatible drop-in
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .backends import MODEL_ALIASES, chat_with_fallback

load_dotenv()

API_KEY = os.environ.get("DUCK_AI_API_KEY", "")
if not API_KEY or API_KEY == "change-me-to-a-long-random-string":
    API_KEY = secrets.token_urlsafe(32)
    print("⚠️  DUCK_AI_API_KEY not set. Generated for this run:")
    print(f"    Authorization: Bearer {API_KEY}")


def require_api_key(authorization: Optional[str] = Header(None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


app = FastAPI(
    title="Duck AI",
    version="0.1.0",
    description="Free AI chat (DuckDuckGo + Pollinations) wrapped with your own API key.",
)


# -------------------- schemas --------------------


class SimpleChatRequest(BaseModel):
    prompt: Optional[str] = Field(None, description="Single user prompt (shortcut)")
    messages: Optional[list[dict]] = Field(None, description="OpenAI-style messages")
    model: Optional[str] = Field(None, description="Model alias, e.g. gpt-4o-mini, claude, gemini")


class SimpleChatResponse(BaseModel):
    text: str
    model: str
    backend: str


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: Optional[str] = None
    messages: list[OpenAIMessage]
    temperature: Optional[float] = None  # ignored, here for compat
    stream: Optional[bool] = False  # streaming not implemented yet


# -------------------- endpoints --------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/models", dependencies=[Depends(require_api_key)])
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "model", "owned_by": "duck-ai"}
            for name in MODEL_ALIASES
        ],
    }


@app.post("/v1/chat", response_model=SimpleChatResponse, dependencies=[Depends(require_api_key)])
async def simple_chat(req: SimpleChatRequest) -> SimpleChatResponse:
    if not req.messages and not req.prompt:
        raise HTTPException(status_code=400, detail="Provide `prompt` or `messages`")
    messages = req.messages or [{"role": "user", "content": req.prompt}]
    try:
        result = await chat_with_fallback(messages, req.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SimpleChatResponse(**result)


@app.post("/v1/chat/completions", dependencies=[Depends(require_api_key)])
async def openai_compat(req: OpenAIChatRequest) -> dict:
    """OpenAI-compatible endpoint so existing SDKs / tools can point here."""
    messages = [m.model_dump() for m in req.messages]
    try:
        result = await chat_with_fallback(messages, req.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "id": f"chatcmpl-{secrets.token_hex(8)}",
        "object": "chat.completion",
        "model": result["model"],
        "duck_ai_backend": result["backend"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["text"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
