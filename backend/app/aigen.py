"""AI topic packs — Groq generates flashcards + practice challenges for a topic.

Mirrors worker/src/aigen.js so the FastAPI backend and the Cloudflare Worker
stay behavior-identical.

Solvability guarantee: the model never invents an (artifact, flag) pair that
might not match. It picks a challenge `type` and writes a `flag`; WE render the
artifact deterministically from the flag (same transforms as the static
puzzles). `concept` challenges carry their own question as the artifact and the
flag is the answer — checked by the normal flag matcher.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

# --- deterministic renderers (derive artifact from the flag) -----------------

XOR_KEY = 0x42
CAESAR_SHIFT = 5


def _b64(s: str) -> str:
    import base64

    return base64.b64encode(s.encode()).decode()


def _hex(s: str) -> str:
    return s.encode().hex()


def _binary(s: str) -> str:
    return " ".join(f"{ord(c):08b}" for c in s)


def _xor_hex(s: str, key: int) -> str:
    return "".join(f"{b ^ key:02x}" for b in s.encode())


def _reverse(s: str) -> str:
    return s[::-1]


def _caesar(s: str, shift: int) -> str:
    out = []
    for ch in s:
        if "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        elif "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        else:
            out.append(ch)
    return "".join(out)


# type -> { render(flag) -> artifact, solution(flag) -> text }
RENDERERS: dict[str, dict[str, Any]] = {
    "base64": {
        "render": _b64,
        "solution": lambda f: "Base64-decode it (base64 -d / CyberChef 'From Base64').",
    },
    "rot13": {
        "render": lambda f: _caesar(f, 13),
        "solution": lambda f: "Apply ROT13 (a Caesar cipher, shift 13; its own inverse).",
    },
    "caesar": {
        "render": lambda f: _caesar(f, CAESAR_SHIFT),
        "solution": lambda f: f"Caesar cipher shifted by {CAESAR_SHIFT} — brute-force the 25 shifts and read the flag.",
    },
    "hex": {
        "render": _hex,
        "solution": lambda f: "Hex -> ASCII (xxd -r -p, or bytes.fromhex).",
    },
    "binary": {
        "render": _binary,
        "solution": lambda f: "Read each 8-bit group as one ASCII byte.",
    },
    "xor": {
        "render": lambda f: _xor_hex(f, XOR_KEY),
        "solution": lambda f: f"Single-byte XOR. Flags start with 'ctf{{' -> key = firstByte XOR 'c' = 0x{XOR_KEY:02x}; XOR everything.",
    },
    "reverse": {
        "render": _reverse,
        "solution": lambda f: "The flag is simply reversed — read it backwards.",
    },
    "concept": {
        "render": lambda f, spec: (spec.get("question") or spec.get("description") or ""),
        "solution": lambda f: f"The answer is {f}.",
    },
}

CHALLENGE_TYPES = list(RENDERERS.keys())

POINTS = {"easy": 50, "medium": 100, "hard": 150}


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:40]


def render_challenge(spec: dict, topic: str, topic_slug: str) -> dict:
    """Render one AI challenge spec into a stored challenge (artifact + solution)."""
    rtype = spec.get("type")
    rtype = rtype if rtype in RENDERERS else "base64"
    r = RENDERERS[rtype]

    flag = str(spec.get("flag") or "").strip().lower()
    if not flag.startswith("ctf{"):
        flag = f"ctf{{{re.sub(r'[^a-z0-9_]', '_', flag)}}}"
    difficulty = spec.get("difficulty", "easy")
    if difficulty not in POINTS:
        difficulty = "easy"

    return {
        "topic": topic,
        "topic_slug": topic_slug,
        "title": (spec.get("title") or f"{topic} challenge")[:120],
        "category": "ai",
        "difficulty": difficulty,
        "points": POINTS[difficulty],
        "description": str(spec.get("description") or "")[:1000],
        "hint": str(spec.get("hint") or "")[:500],
        "artifact": str(r["render"](flag, spec) if rtype == "concept" else r["render"](flag))[:4000],
        "flag": flag,
        "solution": f"{spec.get('solution', '') or ''} {r['solution'](flag)}".strip(),
        "challenge_type": rtype,
    }


SYSTEM = """You are a cybersecurity CTF instructor building a learning pack.
Return STRICT JSON only, matching this shape:
{
  "topic": string,
  "flashcards": [ { "front": string, "back": string, "tags": [string] } ],   // 5-8 items
  "challenges": [ { "type": string, "flag": string, "title": string, "description": string, "hint": string, "difficulty": "easy"|"medium"|"hard", "question": string } ],  // 2-4 items
  "labkit": string   // markdown: a hands-on lab the learner can run in their OWN environment
}
Rules:
- Flashcards teach the core, testable concepts of the topic (free recall Q/A).
- Each challenge "type" MUST be one of: base64, rot13, caesar, hex, binary, xor, reverse, concept.
- "flag" MUST be lowercase of the form ctf{...} with a short, TOPIC-RELEVANT phrase inside using only [a-z0-9_].
- For encoding types (base64/rot13/caesar/hex/binary/xor/reverse): the learner decodes an artifact WE generate from the flag; write description+hint that teach that encoding AND connect it to the topic.
- For "concept": put a direct question in "question" whose answer IS the inner flag text (e.g. question about the topic, flag ctf{answer_in_snake_case}). This tests topic knowledge.
- Include at least one "concept" challenge so the topic itself is tested, not just decoding.
- labkit: concrete steps, commands, and what to look for — safe, legal, self-contained (local VM / docker / files the learner sets up). No illegal targets."""


def extract_json(text: str) -> dict | None:
    """Tolerant JSON extraction — handles ```json fences and surrounding prose."""
    try:
        return json.loads(text)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return None


def normalize_pack(pack: dict, topic: str) -> dict:
    topic_slug = slugify(topic)
    flashcards = (
        [
            {
                "front": str(c.get("front", ""))[:500],
                "back": str(c.get("back", ""))[:1000],
                "tags": [f"topic:{topic_slug}"]
                + [
                    str(t).lower()[:30]
                    for t in (c.get("tags") or [])
                    if t
                ][:5],
            }
            for c in (pack.get("flashcards") or [])
            if c and c.get("front") and c.get("back")
        ][:10]
    )
    challenges = [
        render_challenge(c, topic, topic_slug)
        for c in (pack.get("challenges") or [])
        if c and c.get("flag")
    ][:4]
    return {
        "topic": topic,
        "topic_slug": topic_slug,
        "flashcards": flashcards,
        "challenges": challenges,
        "labkit": str(pack.get("labkit") or "")[:12000],
    }


async def generate_pack(topic: str) -> dict:
    """Call Groq and return a normalized topic pack."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("AI is not configured (GROQ_API_KEY secret missing).")

    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Topic: {topic}. Respond with JSON only."},
                ],
                "reasoning_effort": "low",
                "temperature": 0.6,
                "max_tokens": 6000,
            },
        )
    if res.status_code >= 400:
        raise RuntimeError(f"Groq error {res.status_code}: {res.text[:200]}")

    data = res.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    pack = extract_json(content)
    if not pack:
        raise RuntimeError("AI returned unparseable JSON.")
    return normalize_pack(pack, topic)
