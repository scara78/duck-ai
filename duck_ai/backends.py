"""
Backend providers for free AI chat without login.

Each backend implements:
    async def chat(messages: list[dict], model: str | None) -> str

Backends are tried in BACKEND_ORDER; the first one that doesn't raise wins.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx

# ----- model name mapping -----
# Friendly name -> {backend: actual model id}
MODEL_ALIASES: dict[str, dict[str, str]] = {
    # OpenAI family
    "gpt-4o-mini": {"duckduckgo": "gpt-4o-mini", "pollinations": "openai"},
    "gpt-4": {"duckduckgo": "gpt-4o-mini", "pollinations": "openai-large"},
    "gpt-5-mini": {"duckduckgo": "gpt-5-mini", "pollinations": "openai-large"},
    # Anthropic
    "claude": {"duckduckgo": "claude-3-haiku", "pollinations": "openai"},
    "claude-3-haiku": {"duckduckgo": "claude-3-haiku", "pollinations": "openai"},
    "claude-haiku": {"duckduckgo": "claude-3-haiku", "pollinations": "openai"},
    # Meta
    "llama": {"duckduckgo": "llama", "pollinations": "llama"},
    "llama-3": {"duckduckgo": "llama", "pollinations": "llama"},
    # Mistral
    "mistral": {"duckduckgo": "mistral-small-3", "pollinations": "mistral"},
    "mistral-small-3": {"duckduckgo": "mistral-small-3", "pollinations": "mistral"},
    # Google (only Pollinations exposes Gemini for free without login)
    "gemini": {"pollinations": "gemini"},
    "gemini-flash": {"pollinations": "gemini"},
    # Pollinations defaults
    "openai": {"pollinations": "openai", "duckduckgo": "gpt-4o-mini"},
}


def resolve_model(friendly: str | None, backend: str) -> str:
    """Map a user-friendly name to whatever the backend expects."""
    if not friendly:
        friendly = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    entry = MODEL_ALIASES.get(friendly.lower())
    if entry and backend in entry:
        return entry[backend]
    # If user passed a real backend-specific name, just use it
    return friendly


def messages_to_prompt(messages: list[dict]) -> str:
    """Flatten OpenAI-style messages into one prompt for backends that don't speak chat."""
    parts: list[str] = []
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        parts.append(f"[{role}]\n{content}")
    parts.append("[ASSISTANT]")
    return "\n\n".join(parts)


# ============================================================
#  DuckDuckGo backend  (via the `duckai` package)
# ============================================================


class DuckDuckGoBackend:
    name = "duckduckgo"

    def __init__(self) -> None:
        self._client = None
        self._lock = asyncio.Lock()

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from duckai import DuckAI  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("duckai package not installed") from exc
        proxy = os.getenv("DUCK_PROXY") or None
        self._client = DuckAI(proxy=proxy, timeout=30)

    async def chat(self, messages: list[dict], model: str | None) -> str:
        self._ensure_client()
        resolved = resolve_model(model, self.name)
        prompt = messages_to_prompt(messages)

        # duckai is synchronous, run in a thread + serialize calls (DDG rate-limits)
        async with self._lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._client.chat(prompt, model=resolved),
            )


# ============================================================
#  Pollinations.ai backend
# ============================================================


class PollinationsBackend:
    name = "pollinations"
    OPENAI_URL = "https://text.pollinations.ai/openai"
    SIMPLE_URL = "https://text.pollinations.ai"
    MAX_RETRIES = 3

    async def chat(self, messages: list[dict], model: str | None) -> str:
        resolved = resolve_model(model, self.name)
        last_err: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            # Try OpenAI-compatible endpoint with retries (it's flaky)
            for attempt in range(self.MAX_RETRIES):
                try:
                    r = await client.post(
                        self.OPENAI_URL,
                        json={
                            "model": resolved,
                            "messages": messages,
                            "stream": False,
                            "private": True,
                            "referrer": "duck-ai-server",
                        },
                    )
                    if r.status_code < 400:
                        try:
                            data = r.json()
                            return data["choices"][0]["message"]["content"]
                        except (ValueError, KeyError, IndexError, TypeError):
                            # If body is plain text, return it
                            if r.headers.get("content-type", "").startswith("text/"):
                                return r.text
                            raise
                    last_err = RuntimeError(f"pollinations HTTP {r.status_code}")
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(1 + attempt)

            # Final fallback: the simple GET endpoint (no chat history support)
            try:
                last_msg = messages[-1]["content"] if messages else ""
                prompt_url = f"{self.SIMPLE_URL}/{httpx.QueryParams({'p': last_msg}).get('p')}"
                r = await client.get(prompt_url, params={"model": resolved, "private": "true"})
                if r.status_code < 400 and r.text:
                    return r.text
            except Exception as exc:  # noqa: BLE001
                last_err = exc

            raise RuntimeError(f"pollinations failed after {self.MAX_RETRIES} retries: {last_err}")


# ============================================================
#  Dispatcher
# ============================================================


_ALL_BACKENDS: dict[str, object] = {
    "duckduckgo": DuckDuckGoBackend(),
    "pollinations": PollinationsBackend(),
}


def _ordered_backends() -> list[object]:
    order = [b.strip() for b in os.getenv("BACKEND_ORDER", "duckduckgo,pollinations").split(",")]
    return [_ALL_BACKENDS[name] for name in order if name in _ALL_BACKENDS]


async def chat_with_fallback(messages: list[dict], model: str | None = None) -> dict:
    """Try each configured backend in order. Return {text, backend, model} or raise."""
    errors: list[str] = []
    for backend in _ordered_backends():
        try:
            text = await backend.chat(messages, model)
            return {
                "text": text,
                "backend": backend.name,
                "model": model or os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
            }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{backend.name}: {exc}")
            continue
    raise RuntimeError("All backends failed:\n" + "\n".join(errors))
