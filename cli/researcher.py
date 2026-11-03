"""Command researcher — offline extraction from man pages, whatis, apropos.

Resolves a command to accurate documentation using only locally-installed
resources (man pages, whatis, apropos, --help output). No network required.
Results feed flashcard front/back generation at configurable depth.
"""

from __future__ import annotations

import re
import subprocess
import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CommandInfo:
    name: str
    summary: str          # one-line description (from whatis / NAME section)
    synopsis: str         # usage line
    description: str      # full description
    flags: list[str]      # common flags extracted from man page
    examples: list[str]   # example commands
    see_also: list[str]   # related commands
    source: str           # 'man' | 'help' | 'fallback'
    raw_man: str          # full man text (truncated) for deep mode


def _run(cmd: list[str], timeout: int = 8) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.stdout or ""
    except Exception:
        return ""


def _strip_man_formatting(text: str) -> str:
    # crude de-formatting: remove backspace overstrikes common in man output
    text = re.sub(r".\x08", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_section(man_text: str, section: str) -> str:
    """Pull a section (NAME, SYNOPSIS, DESCRIPTION) from man output."""
    pattern = rf"(?i)^{re.escape(section)}\s*\n(.*?)(?=\n[A-Z][A-Z ]+\s*\n|\Z)"
    m = re.search(pattern, man_text, re.S | re.M)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_flags(man_text: str) -> list[str]:
    """Extract common option flags from SYNOPSIS/DESCRIPTION."""
    flags: set[str] = set()
    # match -letter or --long-option patterns
    for m in re.finditer(r"-\s*([A-Za-z])(?![A-Za-z])|--([A-Za-z][A-Za-z0-9_-]*)", man_text):
        if m.group(1):
            flags.add("-" + m.group(1))
        elif m.group(2):
            flags.add("--" + m.group(2))
    # limit to most common-looking ones
    ordered = sorted(flags, key=lambda f: len(f))
    return ordered[:30]


def _extract_examples(man_text: str) -> list[str]:
    examples: list[str] = []
    # look for lines that look like commands (start with $ or are indented code)
    for line in man_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("$ "):
            examples.append(stripped[2:])
        elif re.match(r"^[a-z][a-z0-9_-]*\s+-", stripped) and len(stripped) < 100:
            examples.append(stripped)
    return examples[:10]


def research(name: str, depth: str = "medium") -> CommandInfo:
    """Research a command offline. Returns a CommandInfo."""
    name = name.strip()
    if not name:
        name = "unknown"

    # 1. Try man page
    man_text = _run(["man", name])
    source = "fallback"
    summary = ""
    synopsis = ""
    description = ""
    raw_man = ""

    if man_text.strip():
        source = "man"
        raw_man = _strip_man_formatting(man_text)[:20000]
        summary_block = _extract_section(raw_man, "NAME")
        # NAME section is "name - description"
        if " - " in summary_block:
            summary = summary_block.split(" - ", 1)[1].strip()
        else:
            summary = summary_block.strip()
        synopsis = _extract_section(raw_man, "SYNOPSIS")
        description = _extract_section(raw_man, "DESCRIPTION")
        if not summary:
            # fallback: whatis
            summary = _run(["whatis", name]).split("\n")[0] if _run(["whatis", name]) else ""
    else:
        # 2. Try whatis
        whatis = _run(["whatis", name])
        if whatis.strip():
            source = "help"
            summary = whatis.strip().split("\n")[0]
        # 3. Try --help
        help_text = _run([name, "--help"], timeout=5)
        if help_text.strip() and source == "fallback":
            source = "help"
            synopsis = help_text.splitlines()[0] if help_text.splitlines() else ""
            description = help_text[:2000]
            flags = _extract_flags(help_text)
            return CommandInfo(
                name=name,
                summary=summary or f"No description available for {name}.",
                synopsis=synopsis,
                description=description,
                flags=flags,
                examples=_extract_examples(help_text),
                see_also=[],
                source=source,
                raw_man=help_text,
            )

    flags = _extract_flags(raw_man)
    examples = _extract_examples(raw_man)

    if not summary:
        summary = f"{name} — command (no local man page found)."
    if not synopsis:
        synopsis = name
    if not description:
        description = summary

    return CommandInfo(
        name=name,
        summary=summary,
        synopsis=synopsis,
        description=description,
        flags=flags,
        examples=examples,
        see_also=[],
        source=source,
        raw_man=raw_man,
    )


def generate_card(command_name: str, depth: str = "medium") -> dict[str, Any]:
    """Generate a flashcard front/back for a command at the given depth."""
    info = research(command_name, depth)

    if depth == "shallow":
        front = f"What does `{info.name}` do?"
        back = info.summary
    elif depth == "deep":
        front = f"Explain `{info.name}` in depth — usage, flags, and purpose."
        parts = [
            f"**Summary:** {info.summary}",
            f"**Usage:** `{info.synopsis}`",
            f"**Description:** {info.description}",
            f"**Flags:** {', '.join(info.flags) if info.flags else '(none documented)'}",
        ]
        if info.examples:
            parts.append("**Examples:**\n" + "\n".join(f"  $ {e}" for e in info.examples[:5]))
        back = "\n\n".join(parts)
    else:  # medium
        flags_str = ", ".join(info.flags[:8]) if info.flags else "common flags"
        front = f"How do you use `{info.name}`? (common flags: {flags_str})"
        back = (
            f"{info.summary}\n\n"
            f"**Usage:** `{info.synopsis}`\n\n"
            f"**Key flags:** {flags_str}\n"
        )
        if info.examples:
            back += "\n**Example:**\n  $ " + info.examples[0]

    tags = ["command", info.name, f"depth:{depth}"]
    return {
        "front": front,
        "back": back,
        "tags": tags,
        "command": info.name,
        "depth": depth,
        "source": info.source,
    }


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "ls"
    depth = sys.argv[2] if len(sys.argv) > 2 else "medium"
    card = generate_card(target, depth)
    print(json.dumps(card, indent=2))
