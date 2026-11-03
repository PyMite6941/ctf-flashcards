"""CTF Command Tracker — offline command capture, research, and study.

Captures commands typed in your terminal (via shell integration), checks them
against local man pages / which, notifies you on failures so you can add them
to a study deck, and lets you study via flashcards, quizzes, tests, and games.

Designed to work fully offline. An AI agent connector is optional.
"""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

DB_PATH = os.environ.get(
    "CTF_CLI_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS commands (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw           TEXT NOT NULL,           -- full command line as typed
    argv0         TEXT NOT NULL,           -- first token (the command)
    args          TEXT NOT NULL DEFAULT '[]',
    exit_code     INTEGER NOT NULL,
    ok            INTEGER NOT NULL DEFAULT 0,   -- 1 if exit 0 and command exists
    added         INTEGER NOT NULL DEFAULT 0,   -- 1 if added to study deck
    depth         TEXT NOT NULL DEFAULT 'medium',
    source        TEXT NOT NULL DEFAULT 'shell',-- 'shell' | 'manual' | 'research'
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS command_cards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id    INTEGER,          -- nullable: NULL for manually-added cards
    command       TEXT NOT NULL DEFAULT '',
    front         TEXT NOT NULL,
    back          TEXT NOT NULL,
    depth         TEXT NOT NULL DEFAULT 'medium',
    tags          TEXT NOT NULL DEFAULT '[]',
    reps          INTEGER NOT NULL DEFAULT 0,
    due           TEXT NOT NULL,
    created_at    REAL NOT NULL,
    FOREIGN KEY (command_id) REFERENCES commands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mode          TEXT NOT NULL,           -- 'flashcard' | 'quiz' | 'test' | 'game'
    started_at    REAL NOT NULL,
    ended_at      REAL,
    score         INTEGER DEFAULT 0,
    total         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS study_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL,
    card_id       INTEGER NOT NULL,
    correct       INTEGER NOT NULL,
    response_ms   INTEGER NOT NULL,
    answered_at   REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES study_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (card_id) REFERENCES command_cards(id) ON DELETE CASCADE
);
"""


@dataclass
class CommandRecord:
    id: Optional[int]
    raw: str
    argv0: str
    args: list[str]
    exit_code: int
    ok: bool
    added: bool
    depth: str
    source: str
    created_at: float


def _now() -> float:
    return time.time()


# Exposed for sibling modules.
now = _now


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Migration: add 'command' column to command_cards if missing.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(command_cards)").fetchall()}
        if "command" not in cols:
            conn.execute("ALTER TABLE command_cards ADD COLUMN command TEXT NOT NULL DEFAULT ''")


def capture_command(
    raw: str,
    exit_code: int = 0,
    source: str = "shell",
    depth: str = "medium",
) -> CommandRecord:
    """Record a command that was typed in the terminal.

    Determines 'ok' by checking whether argv0 resolves to an existing
    executable or shell builtin, and whether exit_code == 0.
    """
    tokens = shlex.split(raw) if raw.strip() else []
    argv0 = tokens[0] if tokens else ""
    args = tokens[1:]

    ok = _command_exists(argv0) and exit_code == 0

    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO commands (raw, argv0, args, exit_code, ok, added, depth, source, created_at, updated_at) "
            "VALUES (?,?,?,?,?,0,?,?,?,?)",
            (raw, argv0, json.dumps(args), exit_code, 1 if ok else 0, depth, source, _now(), _now()),
        )
        cid = cur.lastrowid
        row = conn.execute("SELECT * FROM commands WHERE id = ?", (cid,)).fetchone()
    return _row_to_command(row)


def _command_exists(cmd: str) -> bool:
    if not cmd:
        return False
    # Shell builtins
    builtins = {
        "cd", "pwd", "export", "unset", "alias", "unalias", "source", "exit",
        "history", "jobs", "fg", "bg", "kill", "wait", "type", "help", "true",
        "false", "echo", "printf", "read", "test", "[", "eval", "exec", "set",
        "shift", "trap", "umask", "alias",
    }
    if cmd in builtins:
        return True
    return shutil_which(cmd) is not None


def shutil_which(cmd: str) -> Optional[str]:
    # Avoid importing shutil at module top for minimal footprint
    import shutil

    return shutil.which(cmd)


def _row_to_command(row: sqlite3.Row) -> CommandRecord:
    return CommandRecord(
        id=row["id"],
        raw=row["raw"],
        argv0=row["argv0"],
        args=json.loads(row["args"]),
        exit_code=row["exit_code"],
        ok=bool(row["ok"]),
        added=bool(row["added"]),
        depth=row["depth"],
        source=row["source"],
        created_at=row["created_at"],
    )


def list_unadded(limit: int = 50) -> list[CommandRecord]:
    """Commands not yet added to a study deck, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM commands WHERE added = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_command(r) for r in rows]


def mark_added(command_id: int, depth: str = "medium") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE commands SET added = 1, depth = ?, updated_at = ? WHERE id = ?",
            (depth, _now(), command_id),
        )


def list_commands(added_only: bool = True, limit: int = 100) -> list[CommandRecord]:
    with connect() as conn:
        q = "SELECT * FROM commands"
        params: list[Any] = []
        if added_only:
            q += " WHERE added = 1"
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    return [_row_to_command(r) for r in rows]


def get_command(command_id: int) -> Optional[CommandRecord]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM commands WHERE id = ?", (command_id,)).fetchone()
    return _row_to_command(row) if row else None


def stats() -> dict[str, Any]:
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        added = conn.execute("SELECT COUNT(*) FROM commands WHERE added = 1").fetchone()[0]
        unadded = conn.execute("SELECT COUNT(*) FROM commands WHERE added = 0").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM commands WHERE ok = 0").fetchone()[0]
    return {
        "total": total,
        "added": added,
        "unadded": unadded,
        "failed": failed,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CTF Command Tracker")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="initialize the local database")
    sub.add_parser("stats", help="show command stats")
    sub.add_parser("pending", help="list commands not yet added to study deck")
    sub.add_parser("list", help="list tracked commands")

    args = parser.parse_args()
    init_db()

    if args.cmd == "init":
        print(f"Database initialized at {DB_PATH}")
    elif args.cmd == "stats":
        s = stats()
        print(json.dumps(s, indent=2))
    elif args.cmd == "pending":
        for c in list_unadded():
            print(f"[{c.id}] {c.raw}  (ok={c.ok}, depth={c.depth})")
    elif args.cmd == "list":
        for c in list_commands():
            print(f"[{c.id}] {c.raw}  (ok={c.ok}, added={c.added})")
    else:
        parser.print_help()
