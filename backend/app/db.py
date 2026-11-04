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

-- AI-generated topic packs + practice challenges
CREATE TABLE IF NOT EXISTS gen_packs (
    id              TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,
    topic_slug      TEXT NOT NULL UNIQUE,
    labkit          TEXT NOT NULL DEFAULT '',
    card_count      INTEGER NOT NULL DEFAULT 0,
    challenge_count INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS gen_challenges (
    id             TEXT PRIMARY KEY,
    topic_slug     TEXT NOT NULL,
    title          TEXT NOT NULL,
    category       TEXT NOT NULL DEFAULT 'ai',
    difficulty     TEXT NOT NULL,
    points         INTEGER NOT NULL,
    description    TEXT NOT NULL,
    hint           TEXT NOT NULL,
    artifact       TEXT NOT NULL,
    flag           TEXT NOT NULL,
    solution       TEXT NOT NULL,
    challenge_type TEXT NOT NULL,
    created_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gen_challenges_slug ON gen_challenges(topic_slug);

-- Free-tier AI metering: generations per identity per UTC month (Pro = unlimited)
CREATE TABLE IF NOT EXISTS monthly_ai (
    month     TEXT NOT NULL,   -- 'YYYY-MM' UTC
    identity  TEXT NOT NULL,
    gens      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (month, identity)
);
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


# ---------- AI topic packs + practice challenges ----------

def upsert_pack(
    topic: str,
    topic_slug: str,
    labkit: str,
    card_count: int,
    challenge_count: int,
) -> None:
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO gen_packs (id, topic, topic_slug, labkit, card_count, challenge_count, created_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(topic_slug) DO UPDATE SET topic=excluded.topic, labkit=excluded.labkit, "
            "card_count=excluded.card_count, challenge_count=excluded.challenge_count",
            (new_id(), topic, topic_slug, labkit, card_count, challenge_count, ts),
        )


def insert_gen_challenge(challenge: dict) -> str:
    cid = new_id()
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO gen_challenges (id, topic_slug, title, category, difficulty, points, description, hint, artifact, flag, solution, challenge_type, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cid,
                challenge["topic_slug"],
                challenge["title"],
                challenge.get("category", "ai"),
                challenge["difficulty"],
                challenge["points"],
                challenge["description"],
                challenge["hint"],
                challenge["artifact"],
                challenge["flag"],
                challenge["solution"],
                challenge["challenge_type"],
                ts,
            ),
        )
    return cid


def delete_gen_challenges_for_slug(topic_slug: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM gen_challenges WHERE topic_slug = ?", (topic_slug,))


def list_packs() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM gen_packs ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_pack(topic_slug: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM gen_packs WHERE topic_slug = ?", (topic_slug,)
        ).fetchone()
    return dict(row) if row else None


def gen_challenges_for_slug(topic_slug: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM gen_challenges WHERE topic_slug = ? ORDER BY created_at ASC",
            (topic_slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_gen_challenge(challenge_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM gen_challenges WHERE id = ?", (challenge_id,)
        ).fetchone()
    return dict(row) if row else None


def topic_card_progress(topic_slug: str) -> dict:
    """A topic's flashcards are 'finished' once every card tagged topic:<slug>
    has been reviewed at least once (FSRS reps >= 1). Returns {total, reviewed, done}."""
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT fsrs FROM cards WHERE tags LIKE ?", (f'%\"topic:{topic_slug}\"%',)
        ).fetchall()
    total = len(rows)
    reviewed = 0
    for r in rows:
        try:
            if json.loads(r["fsrs"]).get("reps", 0) >= 1:
                reviewed += 1
        except Exception:
            pass
    return {"total": total, "reviewed": reviewed, "done": total > 0 and reviewed >= total}


# ---------- free-tier monthly AI metering ----------

def ai_gens_this_month(month: str, identity: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT gens FROM monthly_ai WHERE month = ? AND identity = ?",
            (month, identity),
        ).fetchone()
    return row["gens"] if row else 0


def bump_ai_gens(month: str, identity: str) -> int:
    """Increment and return the new monthly AI generation count for this identity."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO monthly_ai (month, identity, gens) VALUES (?, ?, 1) "
            "ON CONFLICT(month, identity) DO UPDATE SET gens = gens + 1",
            (month, identity),
        )
        row = conn.execute(
            "SELECT gens FROM monthly_ai WHERE month = ? AND identity = ?",
            (month, identity),
        ).fetchone()
    return row["gens"]


# ---------- command cards (offline CLI command learning) ----------

def cc_init() -> None:
    """Ensure command card tables exist (shared with the CLI tool)."""
    with connect() as conn:
        conn.executescript(
            """
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
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cc_due ON command_cards(due);
CREATE INDEX IF NOT EXISTS idx_cc_depth ON command_cards(depth);
"""
        )


def cc_list_cards(depth: Optional[str] = None, tag: Optional[str] = None,
                  due_only: bool = False) -> list[dict[str, Any]]:
    cc_init()
    q = "SELECT * FROM command_cards WHERE 1=1"
    params: list[Any] = []
    if depth:
        q += " AND depth = ?"
        params.append(depth)
    if tag:
        q += " AND tags LIKE ?"
        params.append(f'%"{tag}"%')
    if due_only:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        q += " AND due <= ?"
        params.append(now_iso)
    q += " ORDER BY due ASC, created_at DESC"
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def cc_add_card(command: str, front: str, back: str, depth: str = "medium",
                tags: list[str] | None = None) -> dict[str, Any]:
    cc_init()
    tags = tags or ["command", command]
    from datetime import datetime, timezone
    due = datetime.now(timezone.utc).isoformat()
    ts = now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO command_cards (command_id, command, front, back, depth, tags, reps, due, created_at) "
            "VALUES (NULL,?,?,?,?,?,0,?,?)",
            (command, front, back, depth, json.dumps(tags), due, ts),
        )
        cid = cur.lastrowid
        row = conn.execute("SELECT * FROM command_cards WHERE id = ?", (cid,)).fetchone()
    return dict(row)


def cc_update_rep(card_id: int, correct: bool) -> None:
    cc_init()
    from datetime import datetime, timezone, timedelta
    with connect() as conn:
        conn.execute(
            "UPDATE command_cards SET reps = reps + 1 WHERE id = ?", (card_id,)
        )
        row = conn.execute("SELECT depth, reps FROM command_cards WHERE id = ?", (card_id,)).fetchone()
        depth = row["depth"] if row else "medium"
        reps = (row["reps"] if row else 0) + 1
        mult = {"shallow": 1, "medium": 1, "deep": 3}.get(depth, 1)
        hours = (2 ** min(reps, 6)) * mult
        due = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        conn.execute(
            "UPDATE command_cards SET due = ? WHERE id = ?", (due, card_id),
        )


def cc_stats() -> dict[str, Any]:
    cc_init()
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM command_cards").fetchone()[0]
        by_depth = {}
        for d in ("shallow", "medium", "deep"):
            r = conn.execute(
                "SELECT COUNT(*) FROM command_cards WHERE depth = ?", (d,)
            ).fetchone()
            by_depth[d] = r[0]
    return {"total": total, "by_depth": by_depth}


# ---------- badges / achievements (learning gamification) ----------

def badges_init() -> None:
    """Ensure badge tables exist and seed default badges."""
    with connect() as conn:
        conn.executescript(
            """
CREATE TABLE IF NOT EXISTS badges (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL,
    icon           TEXT NOT NULL DEFAULT '🏅',
    criterion_type TEXT NOT NULL,
    criterion_value INTEGER NOT NULL DEFAULT 1,
    created_at     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS user_badges (
    user_id   TEXT NOT NULL,
    badge_id  TEXT NOT NULL,
    earned_at REAL NOT NULL,
    PRIMARY KEY (user_id, badge_id),
    FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE
);
"""
        )
        # Seed default badges if empty
        count = conn.execute("SELECT COUNT(*) FROM badges").fetchone()[0]
        if count == 0:
            ts = now()
            defaults = [
                ("first_command", "First Steps", "Capture your first terminal command", "🎯",
                 "commands_captured", 1, ts),
                ("command_collector", "Command Collector", "Capture 25 commands", "📦",
                 "commands_captured", 25, ts),
                ("command_master", "Command Master", "Capture 100 commands", "🧠",
                 "commands_captured", 100, ts),
                ("streak_3", "3-Day Streak", "Review cards 3 days in a row", "🔥",
                 "streak", 3, ts),
                ("streak_7", "Week Warrior", "Review cards 7 days in a row", "💪",
                 "streak", 7, ts),
                ("cards_mastered", "Card Master", "Master 10 cards (reps >= 3)", "🃏",
                 "cards_mastered", 10, ts),
                ("perfect_score", "Perfect Score", "Score 100% on a study session", "⭐",
                 "perfect_score", 1, ts),
                ("scenario_solved", "Scenario Solver", "Complete a command chaining scenario", "🧩",
                 "scenario_solved", 1, ts),
            ]
            for bid, name, desc, icon, ctype, cval, cts in defaults:
                conn.execute(
                    "INSERT INTO badges (id, name, description, icon, criterion_type, criterion_value, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (bid, name, desc, icon, ctype, cval, cts),
                )


def badges_list() -> list[dict]:
    badges_init()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM badges ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def badges_earned(user_id: str = "local") -> list[dict]:
    badges_init()
    with connect() as conn:
        rows = conn.execute(
            """SELECT b.*, ub.earned_at FROM user_badges ub
               JOIN badges b ON b.id = ub.badge_id
               WHERE ub.user_id = ?
               ORDER BY ub.earned_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def badge_earn(user_id: str, badge_id: str) -> None:
    """Award a badge to a user (idempotent)."""
    badges_init()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) "
            "VALUES (?,?,?)",
            (user_id, badge_id, now()),
        )


def badge_check_and_award(user_id: str, criterion_type: str, value: int) -> list[str]:
    """Check criteria against earned progress; return newly earned badge ids."""
    badges_init()
    newly: list[str] = []
    with connect() as conn:
        rows = conn.execute("SELECT * FROM badges WHERE criterion_type = ?", (criterion_type,)).fetchall()
        for r in rows:
            badge_id = r["id"]
            already = conn.execute(
                "SELECT 1 FROM user_badges WHERE user_id = ? AND badge_id = ?",
                (user_id, badge_id),
            ).fetchone()
            if already:
                continue
            if value >= r["criterion_value"]:
                conn.execute(
                    "INSERT INTO user_badges (user_id, badge_id, earned_at) VALUES (?,?,?)",
                    (user_id, badge_id, now()),
                )
                newly.append(badge_id)
    return newly


# ---------- progress snapshots (analytics / heatmap) ----------

def progress_init() -> None:
    """Ensure the progress_snapshots table exists."""
    with connect() as conn:
        conn.executescript(
            """
CREATE TABLE IF NOT EXISTS progress_snapshots (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL,
    date              TEXT NOT NULL,
    cards_reviewed    INTEGER NOT NULL DEFAULT 0,
    correct_count     INTEGER NOT NULL DEFAULT 0,
    total_count       INTEGER NOT NULL DEFAULT 0,
    minutes_spent     INTEGER NOT NULL DEFAULT 0,
    commands_captured INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, date)
);
"""
        )


def progress_record_snapshot(user_id: str, date: str, cards_reviewed: int,
                             correct_count: int, total_count: int,
                             minutes_spent: int, commands_captured: int) -> None:
    """Upsert a daily progress snapshot."""
    progress_init()
    with connect() as conn:
        conn.execute(
            "INSERT INTO progress_snapshots (id, user_id, date, cards_reviewed, correct_count, total_count, minutes_spent, commands_captured) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id, date) DO UPDATE SET "
            "cards_reviewed = cards_reviewed + excluded.cards_reviewed, "
            "correct_count = correct_count + excluded.correct_count, "
            "total_count = total_count + excluded.total_count, "
            "minutes_spent = minutes_spent + excluded.minutes_spent, "
            "commands_captured = commands_captured + excluded.commands_captured",
            (new_id(), user_id, date, cards_reviewed, correct_count, total_count, minutes_spent, commands_captured),
        )


def progress_get_snapshots(user_id: str = "local", days: int = 30) -> list[dict]:
    progress_init()
    from datetime import datetime, timezone, timedelta
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM progress_snapshots
               WHERE user_id = ? AND date >= ? AND date <= ?
               ORDER BY date ASC""",
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def progress_stats(user_id: str = "local") -> dict:
    progress_init()
    with connect() as conn:
        total_reviewed = conn.execute(
            "SELECT COALESCE(SUM(cards_reviewed), 0) FROM progress_snapshots WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        total_correct = conn.execute(
            "SELECT COALESCE(SUM(correct_count), 0) FROM progress_snapshots WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        total_minutes = conn.execute(
            "SELECT COALESCE(SUM(minutes_spent), 0) FROM progress_snapshots WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        days_active = conn.execute(
            "SELECT COUNT(*) FROM progress_snapshots WHERE user_id = ? AND cards_reviewed > 0",
            (user_id,),
        ).fetchone()[0]
    accuracy = round((total_correct / total_reviewed * 100), 1) if total_reviewed else 0
    return {
        "cards_reviewed": total_reviewed,
        "correct_count": total_correct,
        "accuracy": accuracy,
        "minutes_spent": total_minutes,
        "days_active": days_active,
    }


# ---------- command chaining scenarios ----------

def scenario_init() -> None:
    """Ensure scenario tables exist."""
    with connect() as conn:
        conn.executescript(
            """
CREATE TABLE IF NOT EXISTS command_scenarios (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    description    TEXT NOT NULL,
    objective      TEXT NOT NULL,
    setup_commands TEXT NOT NULL DEFAULT '[]',
    expected_patterns TEXT NOT NULL DEFAULT '[]',
    hints          TEXT NOT NULL DEFAULT '[]',
    difficulty     TEXT NOT NULL DEFAULT 'medium',
    tags           TEXT NOT NULL DEFAULT '[]',
    created_at     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS scenario_attempts (
    id             TEXT PRIMARY KEY,
    scenario_id    TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    completed      INTEGER NOT NULL DEFAULT 0,
    commands_run   TEXT NOT NULL DEFAULT '[]',
    started_at     REAL NOT NULL,
    completed_at   REAL,
    FOREIGN KEY (scenario_id) REFERENCES command_scenarios(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sa_scenario ON scenario_attempts(scenario_id);
CREATE INDEX IF NOT EXISTS idx_sa_user ON scenario_attempts(user_id);
"""
        )


def scenario_list(difficulty: Optional[str] = None) -> list[dict]:
    scenario_init()
    q = "SELECT * FROM command_scenarios WHERE 1=1"
    params: list[Any] = []
    if difficulty:
        q += " AND difficulty = ?"
        params.append(difficulty)
    q += " ORDER BY created_at ASC"
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def scenario_get(scenario_id: str) -> Optional[dict]:
    scenario_init()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM command_scenarios WHERE id = ?", (scenario_id,)
        ).fetchone()
    return dict(row) if row else None


def scenario_create(title: str, description: str, objective: str,
                    setup_commands: list[str], expected_patterns: list[str],
                    hints: list[str], difficulty: str = "medium",
                    tags: list[str] | None = None) -> str:
    scenario_init()
    sid = new_id()
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO command_scenarios (id, title, description, objective, setup_commands, expected_patterns, hints, difficulty, tags, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sid, title, description, objective,
             json.dumps(setup_commands), json.dumps(expected_patterns),
             json.dumps(hints), difficulty, json.dumps(tags or []), ts),
        )
    return sid


def scenario_attempt_start(scenario_id: str, user_id: str = "local") -> str:
    scenario_init()
    aid = new_id()
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO scenario_attempts (id, scenario_id, user_id, completed, commands_run, started_at) "
            "VALUES (?,?,?,0,'[]',?)",
            (aid, scenario_id, user_id, ts),
        )
    return aid


def scenario_attempt_record(attempt_id: str, commands_run: list[str],
                            completed: bool = False) -> None:
    scenario_init()
    with connect() as conn:
        conn.execute(
            "UPDATE scenario_attempts SET commands_run = ?, completed = ?, completed_at = ? WHERE id = ?",
            (json.dumps(commands_run), 1 if completed else 0,
             now() if completed else None, attempt_id),
        )
        if completed:
            badge_check_and_award("local", "scenario_solved", 1)


def scenario_attempts_for_user(user_id: str = "local") -> list[dict]:
    scenario_init()
    with connect() as conn:
        rows = conn.execute(
            """SELECT sa.*, cs.title FROM scenario_attempts sa
               JOIN command_scenarios cs ON cs.id = sa.scenario_id
               WHERE sa.user_id = ?
               ORDER BY sa.started_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- personal card notes ----------

def notes_init() -> None:
    """Ensure the card_notes table exists."""
    with connect() as conn:
        conn.executescript(
            """
CREATE TABLE IF NOT EXISTS card_notes (
    card_id    TEXT NOT NULL,
    user_id    TEXT NOT NULL DEFAULT 'local',
    note       TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (card_id, user_id)
);
"""
        )


def notes_get(card_id: str, user_id: str = "local") -> Optional[str]:
    notes_init()
    with connect() as conn:
        row = conn.execute(
            "SELECT note FROM card_notes WHERE card_id = ? AND user_id = ?",
            (card_id, user_id),
        ).fetchone()
    return row["note"] if row else None


def notes_set(card_id: str, note: str, user_id: str = "local") -> None:
    notes_init()
    with connect() as conn:
        conn.execute(
            "INSERT INTO card_notes (card_id, user_id, note, updated_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(card_id, user_id) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at",
            (card_id, user_id, note, now()),
        )
