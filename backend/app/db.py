"""SQLite storage layer.

Single shared database backing the web app, both mobile (Capacitor) wrappers, and
the local monitor's review inbox. Keep all raw SQL in this module — everything else
talks to the typed helpers below.
"""

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Optional

DB_PATH = os.environ.get(
    "CTF_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "ctf_flashcards.sq3"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT PRIMARY KEY,
    front       TEXT NOT NULL,           -- the prompt / question / challenge
    back        TEXT NOT NULL,           -- the answer / solution / explanation
    kind        TEXT NOT NULL DEFAULT 'flashcard',  -- 'flashcard' | 'challenge'
    deck        TEXT NOT NULL DEFAULT 'default',
    tags        TEXT NOT NULL DEFAULT '[]',         -- JSON array
    fsrs        TEXT NOT NULL,           -- serialized FSRS card state (JSON)
    due         TEXT NOT NULL,           -- ISO8601, denormalized from fsrs for cheap queries
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id          TEXT PRIMARY KEY,
    card_id     TEXT NOT NULL,
    rating      INTEGER NOT NULL,        -- 1=Again 2=Hard 3=Good 4=Easy
    reviewed_at REAL NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inbox (
    id          TEXT PRIMARY KEY,
    front       TEXT NOT NULL,
    back        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'flashcard',
    source      TEXT NOT NULL,           -- which watcher/tool produced it
    detail      TEXT NOT NULL DEFAULT '',-- raw context (log line, scan snippet, ...)
    status      TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    created_at  REAL NOT NULL
);

-- Solved puzzles (the HackTheBox-style challenge catalog lives in puzzles.py;
-- this only tracks which the user has captured, plus points earned).
CREATE TABLE IF NOT EXISTS solves (
    puzzle_id   TEXT PRIMARY KEY,
    solved_at   REAL NOT NULL,
    points      INTEGER NOT NULL DEFAULT 0
);

-- Free-tier metering: how many NEW puzzle solves an identity (IP, or Clerk user
-- when signed in) has made on a given UTC day. A valid Pro license bypasses this.
CREATE TABLE IF NOT EXISTS daily_usage (
    day         TEXT NOT NULL,   -- 'YYYY-MM-DD' UTC
    identity    TEXT NOT NULL,   -- client IP or user id
    solves      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, identity)
);

CREATE INDEX IF NOT EXISTS idx_cards_due    ON cards(due);
CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox(status);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> float:
    return time.time()


def _row_to_card(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "front": row["front"],
        "back": row["back"],
        "kind": row["kind"],
        "deck": row["deck"],
        "tags": json.loads(row["tags"]),
        "fsrs": json.loads(row["fsrs"]),
        "due": row["due"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------- cards ----------

def insert_card(
    front: str,
    back: str,
    kind: str,
    deck: str,
    tags: list[str],
    fsrs: dict[str, Any],
    due: str,
) -> dict[str, Any]:
    cid = new_id()
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO cards (id, front, back, kind, deck, tags, fsrs, due, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cid, front, back, kind, deck, json.dumps(tags), json.dumps(fsrs), due, ts, ts),
        )
    return get_card(cid)  # type: ignore[return-value]


def get_card(cid: str) -> Optional[dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (cid,)).fetchone()
    return _row_to_card(row) if row else None


def list_cards(deck: Optional[str] = None, tag: Optional[str] = None) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if deck:
        where.append("deck = ?")
        params.append(deck)
    if tag:
        # tags is a JSON array like ["crypto","hashes"]; match the quoted token.
        where.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    query = "SELECT * FROM cards"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_card(r) for r in rows]


def due_cards(now_iso: str, limit: int, tag: Optional[str] = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM cards WHERE due <= ?"
    params: list[Any] = [now_iso]
    if tag:
        query += " AND tags LIKE ?"
        params.append(f'%"{tag}"%')
    query += " ORDER BY due ASC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_card(r) for r in rows]


def card_exists_by_front(front: str) -> bool:
    """Cheap dedup so re-solving a puzzle doesn't duplicate its concept cards."""
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM cards WHERE front = ? LIMIT 1", (front,)).fetchone()
    return row is not None


def topics() -> list[dict[str, Any]]:
    """Distinct tags across the deck with a due/total count, for topic filtering."""
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    counts: dict[str, dict[str, int]] = {}
    with connect() as conn:
        rows = conn.execute("SELECT tags, due FROM cards").fetchall()
    for r in rows:
        is_due = r["due"] <= now_iso
        for t in json.loads(r["tags"]):
            slot = counts.setdefault(t, {"total": 0, "due": 0})
            slot["total"] += 1
            if is_due:
                slot["due"] += 1
    return [
        {"tag": t, "total": c["total"], "due": c["due"]}
        for t, c in sorted(counts.items())
    ]


def update_card_fsrs(cid: str, fsrs: dict[str, Any], due: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE cards SET fsrs = ?, due = ?, updated_at = ? WHERE id = ?",
            (json.dumps(fsrs), due, now(), cid),
        )


def delete_card(cid: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM cards WHERE id = ?", (cid,))


# ---------- reviews ----------

def insert_review(card_id: str, rating: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO reviews (id, card_id, rating, reviewed_at) VALUES (?,?,?,?)",
            (new_id(), card_id, rating, now()),
        )


def review_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]


# ---------- inbox ----------

def insert_inbox(front: str, back: str, kind: str, source: str, detail: str) -> dict[str, Any]:
    iid = new_id()
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO inbox (id, front, back, kind, source, detail, status, created_at)"
            " VALUES (?,?,?,?,?,?, 'pending', ?)",
            (iid, front, back, kind, source, detail, ts),
        )
        row = conn.execute("SELECT * FROM inbox WHERE id = ?", (iid,)).fetchone()
    return dict(row)


def list_inbox(status: str = "pending") -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM inbox WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_inbox(iid: str) -> Optional[dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM inbox WHERE id = ?", (iid,)).fetchone()
    return dict(row) if row else None


def set_inbox_status(iid: str, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE inbox SET status = ? WHERE id = ?", (status, iid))


# ---------- solves ----------

def record_solve(puzzle_id: str, points: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO solves (puzzle_id, solved_at, points) VALUES (?,?,?)",
            (puzzle_id, now(), points),
        )


def is_solved(puzzle_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM solves WHERE puzzle_id = ? LIMIT 1", (puzzle_id,)
        ).fetchone()
    return row is not None


def solved_ids() -> set[str]:
    with connect() as conn:
        rows = conn.execute("SELECT puzzle_id FROM solves").fetchall()
    return {r["puzzle_id"] for r in rows}


def total_points() -> int:
    with connect() as conn:
        return conn.execute("SELECT COALESCE(SUM(points), 0) FROM solves").fetchone()[0]


# ---------- free-tier daily metering ----------

def solves_today(day: str, identity: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT solves FROM daily_usage WHERE day = ? AND identity = ?",
            (day, identity),
        ).fetchone()
    return row["solves"] if row else 0


def bump_solves_today(day: str, identity: str) -> int:
    """Increment and return the new daily solve count for this identity."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO daily_usage (day, identity, solves) VALUES (?, ?, 1) "
            "ON CONFLICT(day, identity) DO UPDATE SET solves = solves + 1",
            (day, identity),
        )
        row = conn.execute(
            "SELECT solves FROM daily_usage WHERE day = ? AND identity = ?",
            (day, identity),
        ).fetchone()
    return row["solves"]
