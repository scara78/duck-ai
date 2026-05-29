# Duck AI 🦆✨

Free AI chat **without logging into anything**, wrapped behind **your own API key**.

Made for [Hermes](https://github.com/nati48) and friends — drop in as a replacement for an OpenAI API key, get GPT/Claude/Llama/Mistral/Gemini for free.

---

## What you get

- ✅ **No Google / OpenAI / Anthropic account required**
- ✅ **Your own API key** (`Authorization: Bearer <your-key>`)
- ✅ **OpenAI-compatible** endpoint (`/v1/chat/completions`) — drop-in for existing SDKs
- ✅ **Automatic fallback** — tries DuckDuckGo first; if it rate-limits or fails, falls back to Pollinations.ai
- ✅ **Multiple models**: GPT-4o mini, Claude 3 Haiku, Llama, Mistral, Gemini

---

## ⚠️ Reality check

This stitches together free public AI services. That means:
- **Rate limits exist** (DuckDuckGo: ~1 request / 15s, datacenter IPs often blocked)
- **No SLA** — providers can break/change/disappear
- **Not for production** — great for personal projects, bots, experiments
- For real workloads use a paid API

---

## Quick start

```bash
git clone https://github.com/nati48/duck-ai.git
cd duck-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env       # set DUCK_AI_API_KEY to a long random string

uvicorn duck_ai.server:app --host 0.0.0.0 --port 8788
```

That's it — no login, no cookies, no browser.

### Call it

```bash
# Simple form
curl -X POST http://localhost:8788/v1/chat \
  -H "Authorization: Bearer $DUCK_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a joke", "model": "gpt-4o-mini"}'

# OpenAI-compatible form (works with openai SDK, LangChain, etc.)
curl -X POST http://localhost:8788/v1/chat/completions \
  -H "Authorization: Bearer $DUCK_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-haiku",
    "messages": [{"role": "user", "content": "Hi!"}]
  }'
```

### Use with the OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-duck-ai-key",
    base_url="http://localhost:8788/v1",
)

resp = client.chat.completions.create(
    model="claude-3-haiku",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(resp.choices[0].message.content)
```

### CLI

```bash
python -m duck_ai.cli "What's the capital of Japan?" --model claude
```

---

## Models

Friendly aliases you can use in the `model` field:

| Alias | What it maps to |
|---|---|
| `gpt-4o-mini` | DuckDuckGo → GPT-4o mini, fallback → Pollinations openai |
| `gpt-4` | larger OpenAI model where available |
| `claude` / `claude-3-haiku` | DuckDuckGo → Claude 3 Haiku |
| `llama` / `llama-3` | DuckDuckGo → Llama, Pollinations → Llama |
| `mistral` | Mistral Small 3 |
| `gemini` | Pollinations → Gemini (no Google login) |

Default model is set by `DEFAULT_MODEL` in `.env`.

---

## Backends & fallback

`BACKEND_ORDER` in `.env` controls priority. Default: `duckduckgo,pollinations`.

| Backend | Pros | Cons |
|---|---|---|
| **DuckDuckGo** (`duck.ai`) | Real GPT-4o-mini / Claude Haiku quality, fully anonymous | Heavy rate limit, datacenter IPs often blocked |
| **Pollinations.ai** | Works from any IP, no rate limit | Quality varies, occasional 502s |

If DuckDuckGo blocks your server IP, the server transparently falls back to Pollinations.

### Proxy for DuckDuckGo

Set `DUCK_PROXY` in `.env` to a SOCKS5/HTTP proxy to route DuckDuckGo traffic through a residential IP:

```env
DUCK_PROXY=socks5://user:pass@proxy.example.com:1080
```

---

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET  | `/health` | – | Liveness probe |
| GET  | `/v1/models` | ✅ | List available model aliases |
| POST | `/v1/chat` | ✅ | Simple `{prompt, model?}` → `{text, backend, model}` |
| POST | `/v1/chat/completions` | ✅ | OpenAI-compatible |

All authenticated endpoints require `Authorization: Bearer <DUCK_AI_API_KEY>`.

---

## Project layout

```
duck-ai/
├── duck_ai/
│   ├── __init__.py
│   ├── backends.py   # DuckDuckGo + Pollinations adapters & fallback logic
│   ├── server.py     # FastAPI app
│   └── cli.py        # Terminal client
├── requirements.txt
├── .env.example
└── README.md
```

---

## Why "Duck AI"?

Because the first backend is DuckDuckGo, and "duck" is way more fun than "AI proxy". 🦆

---

## License

MIT — do what you want, just don't blame us if a backend stops being free.
