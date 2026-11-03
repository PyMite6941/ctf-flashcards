"""Terminal command tracker — unlimited line-by-line capture.

Captures *anything* typed or pasted into a terminal (no whitelist, no limits):
every command line, every exit code, every error. Works with any shell tool
(Claude Code, Qwen Code, Hydra, git, nmap, custom scripts…).

On a failed command it asks whether you want to:
  - add it to the study deck, or
  - analyze/fix the error (local man-page + --help research, no AI required).

Everything is stored locally in SQLite. No server, no network required.
"""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

def _default_db_path() -> str:
    """Where the command DB lives when CTF_CLI_DB is not set.

    A DB inside the package dir is wiped on every npm upgrade and is often
    read-only for global installs, so default to a per-user data dir. An
    existing legacy DB next to this file is still honoured so source-checkout
    users keep their history.
    """
    legacy = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands.db")
    if os.path.exists(legacy):
        return legacy
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or base
    return os.path.join(base, "ctf-flashcards", "commands.db")


DB_PATH = os.environ.get("CTF_CLI_DB") or _default_db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS commands (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw           TEXT NOT NULL,           -- full command line as typed/pasted
    argv0         TEXT NOT NULL DEFAULT '',-- first token (the command/tool)
    args          TEXT NOT NULL DEFAULT '[]',
    exit_code     INTEGER NOT NULL,
    ok            INTEGER NOT NULL DEFAULT 0,          -- 1 if exit 0
    found         INTEGER NOT NULL DEFAULT 1,          -- 1 if command exists on PATH/builtin
    added         INTEGER NOT NULL DEFAULT 0,          -- 1 if added to study deck
    fixed         INTEGER NOT NULL DEFAULT 0,          -- 1 if user fixed the error
    depth         TEXT NOT NULL DEFAULT 'medium',      -- shallow | medium | deep
    source        TEXT NOT NULL DEFAULT 'shell',       -- shell | manual | paste | monitor
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

CREATE TABLE IF NOT EXISTS error_fixes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id    INTEGER NOT NULL,
    error_text    TEXT NOT NULL,          -- stderr / failure output
    fix_attempted INTEGER NOT NULL DEFAULT 0,
    fix_success   INTEGER NOT NULL DEFAULT 0,
    notes         TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    FOREIGN KEY (command_id) REFERENCES commands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mode          TEXT NOT NULL,           -- flashcard | quiz | test | game
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

CREATE INDEX IF NOT EXISTS idx_commands_created ON commands(created_at);
CREATE INDEX IF NOT EXISTS idx_commands_ok ON commands(ok);
CREATE INDEX IF NOT EXISTS idx_commands_added ON commands(added);
CREATE INDEX IF NOT EXISTS idx_cc_due ON command_cards(due);
CREATE INDEX IF NOT EXISTS idx_cc_depth ON command_cards(depth);
"""


@dataclass
class CommandRecord:
    id: Optional[int]
    raw: str
    argv0: str
    args: list[str]
    exit_code: int
    ok: bool
    found: bool
    added: bool
    fixed: bool
    depth: str
    source: str
    created_at: float


def _now() -> float:
    return time.time()


# Exposed for sibling modules.
now = _now


def connect() -> sqlite3.Connection:
    parent = os.path.dirname(DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Migration for older schemas: ensure 'found' and 'fixed' columns exist.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(commands)").fetchall()}
        if "found" not in cols:
            conn.execute("ALTER TABLE commands ADD COLUMN found INTEGER NOT NULL DEFAULT 1")
        if "fixed" not in cols:
            conn.execute("ALTER TABLE commands ADD COLUMN fixed INTEGER NOT NULL DEFAULT 0")
        cc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(command_cards)").fetchall()}
        if "command" not in cc_cols:
            conn.execute("ALTER TABLE command_cards ADD COLUMN command TEXT NOT NULL DEFAULT ''")


def capture_command(
    raw: str,
    exit_code: int = 0,
    source: str = "shell",
    depth: str = "medium",
    stderr: str = "",
) -> CommandRecord:
    """Record *any* command line that was typed/pasted into a terminal.

    No restrictions on what can be captured — argv0 is just the first token.
    'ok' is True only if exit_code == 0 AND the command exists.
    """
    tokens = shlex.split(raw) if raw and raw.strip() else []
    argv0 = tokens[0] if tokens else ""
    args = tokens[1:]

    found = _command_found(argv0)
    ok = (exit_code == 0) and found

    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO commands (raw, argv0, args, exit_code, ok, found, added, fixed, depth, source, created_at, updated_at) "
            "VALUES (?,?,?,?,?,0,0,?,?,?,?,?)",
            (raw, argv0, json.dumps(args), exit_code, 1 if ok else 0, 1 if found else 0,
             depth, source, _now(), _now()),
        )
        cid = cur.lastrowid
        # If it failed, record an error slot so the UI can ask to fix it.
        if not ok and stderr:
            conn.execute(
                "INSERT INTO error_fixes (command_id, error_text, fix_attempted, fix_success, notes, created_at) "
                "VALUES (?,?,0,0,'',?)",
                (cid, stderr[:4000], _now()),
            )
        row = conn.execute("SELECT * FROM commands WHERE id = ?", (cid,)).fetchone()
    return _row_to_command(row)


def _command_found(cmd: str) -> bool:
    """Check whether a command resolves to a PATH executable or shell builtin."""
    if not cmd:
        return False
    builtins = {
        "cd", "pwd", "export", "unset", "alias", "unalias", "source", "exit",
        "history", "jobs", "fg", "bg", "kill", "wait", "type", "help", "true",
        "false", "echo", "printf", "read", "test", "[", "eval", "exec", "set",
        "shift", "trap", "umask", "alias", "dirs", "pushd", "popd", "disown",
        "command", "builtin",
    }
    if cmd in builtins:
        return True
    import shutil
    return shutil.which(cmd) is not None


def _row_to_command(row: sqlite3.Row) -> CommandRecord:
    return CommandRecord(
        id=row["id"],
        raw=row["raw"],
        argv0=row["argv0"],
        args=json.loads(row["args"]),
        exit_code=row["exit_code"],
        ok=bool(row["ok"]),
        found=bool(row["found"]),
        added=bool(row["added"]),
        fixed=bool(row["fixed"]),
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


def list_failed_unfixed(limit: int = 50) -> list[CommandRecord]:
    """Commands that failed and haven't been fixed yet, newest first."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.* FROM commands c
               JOIN error_fixes e ON e.command_id = c.id
               WHERE c.ok = 0 AND e.fix_success = 0
               ORDER BY c.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [_row_to_command(r) for r in rows]


def mark_fixed(command_id: int, success: bool = True, notes: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE commands SET fixed = 1, updated_at = ? WHERE id = ?",
            (_now(), command_id),
        )
        conn.execute(
            "UPDATE error_fixes SET fix_attempted = 1, fix_success = ?, notes = ?, created_at = ? "
            "WHERE command_id = ? AND fix_success = 0",
            (1 if success else 0, notes, _now(), command_id),
        )


def get_error_text(command_id: int) -> Optional[str]:
    with connect() as conn:
        row = conn.execute(
            "SELECT error_text FROM error_fixes WHERE command_id = ? AND fix_success = 0 ORDER BY created_at DESC LIMIT 1",
            (command_id,),
        ).fetchone()
    return row["error_text"] if row else None


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
        unfixed = conn.execute(
            "SELECT COUNT(*) FROM commands c JOIN error_fixes e ON e.command_id=c.id "
            "WHERE c.ok=0 AND e.fix_success=0"
        ).fetchone()[0]
        fixed = conn.execute("SELECT COUNT(*) FROM commands WHERE fixed = 1").fetchone()[0]
    return {
        "total": total,
        "added": added,
        "unadded": unadded,
        "failed": failed,
        "unfixed": unfixed,
        "fixed": fixed,
    }


def recent(limit: int = 30) -> list[CommandRecord]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM commands ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_command(r) for r in rows]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CTF Command Tracker")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="initialize the local database")
    sub.add_parser("stats", help="show command stats")
    sub.add_parser("recent", help="show recent commands").add_argument("--limit", type=int, default=30)
    sub.add_parser("pending", help="list commands not yet added to study deck").add_argument("--limit", type=int, default=50)
    sub.add_parser("failed", help="list failed commands not yet fixed").add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    init_db()

    if args.cmd == "init":
        print(f"Database initialized at {DB_PATH}")
    elif args.cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif args.cmd == "recent":
        for c in recent(args.limit):
            flag = "OK " if c.ok else "FAIL"
            found = "" if c.found else " [not found]"
            print(f"[{c.id}] [{flag}{found}] {c.raw}")
    elif args.cmd == "pending":
        for c in list_unadded(args.limit):
            flag = "OK " if c.ok else "FAIL"
            print(f"[{c.id}] [{flag}] {c.raw}  (depth={c.depth})")
    elif args.cmd == "failed":
        for c in list_failed_unfixed(args.limit):
            err = get_error_text(c.id)
            print(f"[{c.id}] [FAIL] {c.raw}")
            if err:
                print(f"      error: {err[:200]}")
    else:
        parser.print_help()
