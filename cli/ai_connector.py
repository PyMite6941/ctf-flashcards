"""Optional AI agent connector.

The tool works fully offline without this. When GROQ_API_KEY (or another
provider) is set, this connector can:
  - explain a command in more depth
  - suggest related commands
  - generate practice questions / quiz items

All AI calls are opt-in and gated behind an env var. If unavailable, the
local researcher (man pages) is used instead.
"""

from __future__ import annotations

import json
import os
from typing import Optional

try:
    import httpx
except Exception:  # httpx may not be installed
    httpx = None  # type: ignore


GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY")) and httpx is not None


async def explain_command(command: str, context: str = "") -> Optional[str]:
    """Ask the AI to explain a command. Returns None if not configured."""
    if not is_configured():
        return None
    try:
        import anyio

        return anyio.run(_explain_async, command, context)
    except Exception:
        return None


async def _explain_async(command: str, context: str) -> str:
    import httpx  # type: ignore

    api_key = os.environ["GROQ_API_KEY"]
    system = (
        "You are a cybersecurity CTF instructor. Explain the given command "
        "concisely: what it does, common flags, a practical example, and any "
        "safety warning. Keep it short and accurate. Do not fabricate flags."
    )
    user = f"Command: {command}\nContext: {context or '(none)'}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], "temperature": 0.3, "max_tokens": 500},
        )
    res.raise_for_status()
    data = res.json()
    return data["choices"][0]["message"]["content"]


async def generate_quiz_item(command: str, depth: str = "medium") -> Optional[dict]:
    """Generate a multiple-choice quiz item for a command. Returns dict or None."""
    if not is_configured():
        return None
    try:
        import anyio
        return anyio.run(_quiz_async, command, depth)
    except Exception:
        return None


async def _quiz_async(command: str, depth: str) -> dict:
    import httpx  # type: ignore

    api_key = os.environ["GROQ_API_KEY"]
    system = (
        "Generate a multiple-choice quiz question about the given command. "
        'Return STRICT JSON: {"question": str, "options": [str,str,str,str], '
        '"answer_index": int, "explanation": str}. '
        "Make the options plausible but only one correct. "
        "Focus on practical usage and safety."
    )
    user = f"Command: {command}\nDepth: {depth}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], "temperature": 0.4, "max_tokens": 400},
        )
    res.raise_for_status()
    data = res.json()
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except Exception:
        # tolerant extract
        import re
        m = re.search(r"\{[\s\S]*\}", content)
        return json.loads(m.group(0)) if m else {}
