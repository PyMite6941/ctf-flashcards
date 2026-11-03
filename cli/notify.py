"""Wrong-command notifications.

When a tracked command fails (exit != 0 or command not found), we surface a
prompt asking the user whether they want to add it to their study deck.
Works in a terminal (stdout) and, on Linux, via desktop notifications.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from typing import Optional

try:
    from .tracker import capture_command, list_unadded, mark_added
except ImportError:  # allow running as a script
    from tracker import capture_command, list_unadded, mark_added  # type: ignore


def notify_failed(raw: str, exit_code: int) -> Optional[int]:
    """Show a notification for a failed command. Returns the new command id
    if the user chose to add it, else None."""
    print(f"\n[ctf-flashcards] Command failed (exit {exit_code}): {raw}")
    choice = input("Add to study deck? [y/N] ").strip().lower()
    if choice in ("y", "yes"):
        rec = capture_command(raw, exit_code=exit_code, source="shell")
        print(f"  -> added as command #{rec.id} (depth=medium). Run 'ctf study' to learn it.")
        return rec.id
    else:
        # still record it so we can track failures, just not added to deck
        capture_command(raw, exit_code=exit_code, source="shell")
        print("  -> not added.")
        return None


def desktop_notify(title: str, body: str) -> None:
    """Send a desktop notification if notify-send is available (Linux)."""
    if subprocess.run(["which", "notify-send"], capture_output=True).returncode == 0:
        subprocess.run(["notify-send", title, body], capture_output=True)


def check_and_notify(raw: str, exit_code: int) -> Optional[int]:
    """If a command looks wrong/failed, notify and offer to add it."""
    tokens = shlex.split(raw) if raw.strip() else []
    argv0 = tokens[0] if tokens else ""
    if not argv0:
        return None
    # Only bother if it actually failed or the command doesn't exist
    import shutil

    exists = argv0 in {
        "cd", "pwd", "export", "unset", "alias", "unalias", "source", "exit",
        "history", "jobs", "fg", "bg", "kill", "wait", "type", "help", "true",
        "false", "echo", "printf", "read", "test", "[", "eval", "exec", "set",
        "shift", "trap", "umask",
    } or shutil.which(argv0) is not None

    if exit_code != 0 or not exists:
        desktop_notify("CTF Flashcards — command failed", raw)
        return notify_failed(raw, exit_code)
    return None


def pending_count() -> int:
    from .tracker import init_db

    init_db()
    return len(list_unadded())


if __name__ == "__main__":
    # quick manual test
    notify_failed("nonexistentcommand foo bar", 127)
