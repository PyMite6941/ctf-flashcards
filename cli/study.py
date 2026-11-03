"""Offline study engine — flashcards, quizzes, tests, and practice games.

All modes run against the local command_cards table (populated from captured
commands + man-page research). No server required.
"""

from __future__ import annotations

import json
import random
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

try:
    from .tracker import connect as _connect, now as _now, CommandRecord
    from .researcher import generate_card
except ImportError:  # allow running as a script
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tracker import connect as _connect, now as _now, CommandRecord  # type: ignore
    from researcher import generate_card  # type: ignore


DEPTHS = ("shallow", "medium", "deep")


@dataclass
class StudyCard:
    id: int
    command: str
    front: str
    back: str
    depth: str
    tags: list[str]
    due: str
    reps: int


def _row_to_card(row: sqlite3.Row) -> StudyCard:
    return StudyCard(
        id=row["id"],
        command=row["command"],
        front=row["front"],
        back=row["back"],
        depth=row["depth"],
        tags=json.loads(row["tags"]),
        due=row["due"],
        reps=row["reps"],
    )


def add_card_from_command(command_id: int, depth: str = "medium") -> Optional[StudyCard]:
    """Research a captured command and insert it as a study card."""
    from .tracker import get_command, mark_added

    cmd = get_command(command_id)
    if not cmd:
        return None
    card_data = generate_card(cmd.argv0, depth)

    due = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO command_cards (command_id, command, front, back, depth, tags, reps, due, created_at) "
            "VALUES (?,?,?,?,?,?,0,?,?)",
            (
                command_id,
                cmd.argv0,
                card_data["front"],
                card_data["back"],
                depth,
                json.dumps(card_data["tags"]),
                due,
                _now(),
            ),
        )
        cid = cur.lastrowid
        conn.execute(
            "UPDATE commands SET added = 1, depth = ?, updated_at = ? WHERE id = ?",
            (depth, _now(), command_id),
        )
        row = conn.execute("SELECT * FROM command_cards WHERE id = ?", (cid,)).fetchone()
    return _row_to_card(row)


def add_card_manual(command: str, front: str, back: str, depth: str = "medium",
                    tags: list[str] | None = None) -> StudyCard:
    tags = tags or ["command", command]
    due = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO command_cards (command_id, command, front, back, depth, tags, reps, due, created_at) "
            "VALUES (NULL,?,?,?,?,?,0,?,?)",
            (command, front, back, depth, json.dumps(tags), due, _now()),
        )
        cid = cur.lastrowid
        row = conn.execute("SELECT * FROM command_cards WHERE id = ?", (cid,)).fetchone()
    return _row_to_card(row)


def list_cards(depth: Optional[str] = None, tag: Optional[str] = None,
               due_only: bool = False) -> list[StudyCard]:
    q = "SELECT * FROM command_cards WHERE 1=1"
    params: list[Any] = []
    if depth:
        q += " AND depth = ?"
        params.append(depth)
    if tag:
        q += " AND tags LIKE ?"
        params.append(f'%"{tag}"%')
    if due_only:
        now_iso = datetime.now(timezone.utc).isoformat()
        q += " AND due <= ?"
        params.append(now_iso)
    q += " ORDER BY due ASC, created_at DESC"
    with _connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_row_to_card(r) for r in rows]


def update_rep(card_id: int, correct: bool, response_ms: int,
               session_id: int) -> None:
    """Record a review result and bump reps/due using a simple FSRS-like step."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO study_results (session_id, card_id, correct, response_ms, answered_at) "
            "VALUES (?,?,?,?,?)",
            (session_id, card_id, 1 if correct else 0, response_ms, _now()),
        )
        row = conn.execute("SELECT reps, due FROM command_cards WHERE id = ?", (card_id,)).fetchone()
        reps = (row["reps"] or 0) + 1
        # simple spacing: shallow=1h, medium=1d, deep=3d per rep level
        depth_row = conn.execute("SELECT depth FROM command_cards WHERE id = ?", (card_id,)).fetchone()
        depth = depth_row["depth"] if depth_row else "medium"
        mult = {"shallow": 1, "medium": 1, "deep": 3}.get(depth, 1)
        hours = (2 ** min(reps, 6)) * mult
        due = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        conn.execute(
            "UPDATE command_cards SET reps = ?, due = ? WHERE id = ?",
            (reps, due, card_id),
        )


def start_session(mode: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO study_sessions (mode, started_at, score, total) VALUES (?,?,0,0)",
            (mode, _now()),
        )
        return cur.lastrowid


def end_session(session_id: int, score: int, total: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE study_sessions SET ended_at = ?, score = ?, total = ? WHERE id = ?",
            (_now(), score, total, session_id),
        )


def cards_for_review(depth: Optional[str] = None, limit: int = 20) -> list[StudyCard]:
    """Cards due now, optionally filtered by depth."""
    return list_cards(depth=depth, due_only=True)[:limit]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CTF Study Engine")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="add a captured command as a study card")
    p_add.add_argument("command_id", type=int)
    p_add.add_argument("--depth", choices=DEPTHS, default="medium")

    p_list = sub.add_parser("list", help="list study cards")
    p_list.add_argument("--depth", choices=DEPTHS)
    p_list.add_argument("--tag")
    p_list.add_argument("--due", action="store_true")

    p_manual = sub.add_parser("manual", help="add a manual study card")
    p_manual.add_argument("command")
    p_manual.add_argument("front")
    p_manual.add_argument("back")
    p_manual.add_argument("--depth", choices=DEPTHS, default="medium")

    args = parser.parse_args()
    from .tracker import init_db
    init_db()

    if args.cmd == "add":
        c = add_card_from_command(args.command_id, args.depth)
        print(f"Added card #{c.id}: {c.front}")
    elif args.cmd == "list":
        for c in list_cards(depth=args.depth, tag=args.tag, due_only=args.due):
            tagstr = f" [{c.depth}]" if c.depth else ""
            print(f"[{c.id}]{tagstr} {c.front}  (due={c.due[:10]}, reps={c.reps})")
    elif args.cmd == "manual":
        c = add_card_manual(args.command, args.front, args.back, args.depth)
        print(f"Added manual card #{c.id}: {c.front}")
    else:
        parser.print_help()
