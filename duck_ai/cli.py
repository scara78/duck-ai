"""CLI helper:  python -m duck_ai.cli "your prompt" [--model gpt-4o-mini]"""

from __future__ import annotations

import argparse
import asyncio

from .backends import chat_with_fallback


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Free AI chat from the terminal")
    parser.add_argument("prompt", nargs="+", help="Your prompt")
    parser.add_argument("--model", default=None, help="Model alias (gpt-4o-mini, claude, gemini, ...)")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    result = await chat_with_fallback([{"role": "user", "content": prompt}], args.model)
    print(f"[{result['backend']} / {result['model']}]")
    print(result["text"])


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
