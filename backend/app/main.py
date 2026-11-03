"""CTF Flashcards — shared backend API.

FastAPI + SQLite. One backend serves the web app and both Capacitor mobile shells.
Core loop: recall -> reveal -> self-rate (Again/Hard/Good/Easy) -> FSRS reschedules.

Run:  uvicorn app.main:app --reload  (from the backend/ directory)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import aigen, billing, db, puzzles, scheduler

app = FastAPI(title="CTF Flashcards API", version="0.2.0")

# Web dev server + Capacitor shells all hit this from a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------- schemas -----------------------------

class CardIn(BaseModel):
    front: str = Field(..., min_length=1)
    back: str = Field(..., min_length=1)
    kind: str = "flashcard"  # 'flashcard' | 'challenge'
    deck: str = "default"
    tags: list[str] = []


class ReviewIn(BaseModel):
    rating: int = Field(..., ge=1, le=4)  # 1=Again 2=Hard 3=Good 4=Easy


class InboxIn(BaseModel):
    front: str = Field(..., min_length=1)
    back: str = Field(..., min_length=1)
    kind: str = "flashcard"
    source: str = "manual"
    detail: str = ""


class InboxApprove(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None
    kind: Optional[str] = None
    deck: str = "default"
    tags: list[str] = []


class FlagIn(BaseModel):
    flag: str = Field(..., min_length=1)


# ----------------------------- cards -----------------------------

@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "reviews": db.review_count(),
        "points": db.total_points(),
        "solved": len(db.solved_ids()),
        "puzzles": len(puzzles.CATALOG),
    }


@app.post("/cards", status_code=201)
def create_card(card: CardIn) -> dict:
    fsrs, due = scheduler.new_card_state()
    return db.insert_card(card.front, card.back, card.kind, card.deck, card.tags, fsrs, due)


@app.get("/cards")
def get_cards(deck: Optional[str] = None, tag: Optional[str] = None) -> list[dict]:
    return db.list_cards(deck, tag)


@app.get("/topics")
def get_topics() -> list[dict]:
    """Distinct tags across the deck with due/total counts — powers topic filtering."""
    return db.topics()


@app.get("/cards/{cid}")
def get_card(cid: str) -> dict:
    card = db.get_card(cid)
    if not card:
        raise HTTPException(404, "card not found")
    return card


@app.delete("/cards/{cid}", status_code=204)
def remove_card(cid: str) -> None:
    if not db.get_card(cid):
        raise HTTPException(404, "card not found")
    db.delete_card(cid)


# ----------------------------- review queue -----------------------------

@app.get("/review/queue")
def review_queue(limit: int = 20, tag: Optional[str] = None) -> list[dict]:
    """Cards that are due now, soonest first. Optionally filtered to one topic (tag)."""
    return db.due_cards(_now_iso(), limit, tag)


@app.post("/cards/{cid}/review")
def submit_review(cid: str, body: ReviewIn) -> dict:
    card = db.get_card(cid)
    if not card:
        raise HTTPException(404, "card not found")
    new_fsrs, due = scheduler.review(card["fsrs"], body.rating)
    db.update_card_fsrs(cid, new_fsrs, due)
    db.insert_review(cid, body.rating)
    return db.get_card(cid)  # type: ignore[return-value]


# ----------------------------- CTF puzzles -----------------------------
# HackTheBox-style challenges. Solving one unlocks its concept cards, which flow
# straight into the review deck — the puzzles fuel the flashcards.

@app.get("/puzzles")
def list_puzzles(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    status: Optional[str] = None,  # 'solved' | 'unsolved'
) -> dict:
    solved = db.solved_ids()
    return {
        "puzzles": puzzles.list_puzzles(solved, category, difficulty, status),
        "categories": puzzles.categories(),
        "points": db.total_points(),
        "solved": len(solved),
        "total": len(puzzles.CATALOG),
    }


@app.get("/puzzles/{pid}")
def get_puzzle(pid: str) -> dict:
    p = puzzles.get_puzzle(pid, db.is_solved(pid))
    if not p:
        raise HTTPException(404, "puzzle not found")
    return p


@app.get("/limits")
def get_limits(request: Request, x_license: str | None = Header(default=None)) -> dict:
    """Free-tier status for the caller: remaining daily solves + Pro entitlement."""
    ent = billing.verify_license(x_license)
    used = db.solves_today(billing.today(), billing.client_identity(request))
    cap = billing.FREE_DAILY_SOLVES
    # Monthly AI generation metering (free tier only; Pro = unlimited).
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    identity = billing.client_identity(request)
    ai_used = db.ai_gens_this_month(month, identity)
    ai_cap = billing.FREE_MONTHLY_AI_GENS
    return {
        "pro": ent["pro"],
        "tier": ent["tier"],
        "daily_solve_limit": cap,
        "solves_used_today": used,
        "solves_remaining": None if ent["pro"] else max(0, cap - used),
        "ai_gens_limit": ai_cap,
        "ai_gens_used_this_month": ai_used,
        "ai_gens_remaining": None if ent["pro"] else max(0, ai_cap - ai_used),
        "price_usdc": 8,
        "tier_id": "ctf_pro",
    }


@app.post("/puzzles/{pid}/submit")
def submit_flag(
    pid: str,
    body: FlagIn,
    request: Request,
    x_license: str | None = Header(default=None),
) -> dict:
    correct, puzzle = puzzles.check_flag(pid, body.flag)
    if puzzle is None:
        raise HTTPException(404, "puzzle not found")
    if not correct:
        return {"correct": False}

    already = db.is_solved(pid)

    # Free-tier gate: only NEW captures count against the daily cap; re-solving an
    # already-captured puzzle is always free. Pro licenses bypass entirely.
    if not already:
        ent = billing.verify_license(x_license)
        if not ent["pro"]:
            identity = billing.client_identity(request)
            used = db.solves_today(billing.today(), identity)
            if used >= billing.FREE_DAILY_SOLVES:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "daily_limit_reached",
                        "message": f"Free tier is {billing.FREE_DAILY_SOLVES} puzzle solves per day. "
                        f"Upgrade to Pro ($8/mo) for unlimited.",
                        "daily_solve_limit": billing.FREE_DAILY_SOLVES,
                        "tier_id": "ctf_pro",
                        "price_usdc": 8,
                    },
                )
            db.bump_solves_today(billing.today(), identity)

    db.record_solve(pid, puzzle["points"])

    # Unlock the concept cards into the review deck (dedup so re-solving is a no-op).
    added = []
    for card in puzzle["cards"]:
        if db.card_exists_by_front(card["front"]):
            continue
        fsrs, due = scheduler.new_card_state()
        tags = card.get("tags", []) or [puzzle["category"]]
        db.insert_card(card["front"], card["back"], "flashcard", puzzle["category"], tags, fsrs, due)
        added.append(card["front"])

    return {
        "correct": True,
        "already_solved": already,
        "points": puzzle["points"],
        "total_points": db.total_points(),
        "solution": puzzle["solution"],
        "added_cards": added,
    }


# ----------------------------- AI topic packs -----------------------------
# Learn (AI) feature — ported from the Cloudflare Worker so the FastAPI
# backend and the Worker stay behavior-identical. Groq generates flashcards
# + practice challenges for a topic; solving a challenge awards points like
# a static puzzle.


def _strip_gen_challenge(c: dict, solved: bool) -> dict:
    """Public view of a generated challenge — never leak the flag."""
    out = {
        "id": c["id"],
        "topic_slug": c["topic_slug"],
        "title": c["title"],
        "category": c["category"],
        "difficulty": c["difficulty"],
        "points": c["points"],
        "description": c["description"],
        "hint": c["hint"],
        "artifact": c["artifact"],
        "challenge_type": c["challenge_type"],
        "solved": solved,
    }
    if solved:
        out["solution"] = c["solution"]
    return out


@app.post("/ai/generate", status_code=201)
async def generate_pack(
    request: Request,
    x_license: str | None = Header(default=None),
) -> dict:
    """Generate an AI topic pack: flashcards into the deck + practice
    challenges (locked until the flashcards are reviewed) + a lab kit."""
    try:
        body = await request.json()  # type: ignore[attr-defined]
    except Exception:
        body = {}
    topic = (body.get("topic") or "").strip() if isinstance(body, dict) else ""
    if not topic:
        raise HTTPException(422, "topic required")
    if len(topic) > 120:
        raise HTTPException(422, "topic too long")

    # Free tier: cap AI generations per month. Pro = unlimited.
    ent = billing.verify_license(x_license)
    identity = billing.client_identity(request)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if not ent["pro"]:
        used = db.ai_gens_this_month(month, identity)
        cap = billing.FREE_MONTHLY_AI_GENS
        if used >= cap:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "ai_limit_reached",
                    "message": f"Free tier is {cap} AI generations per month. Upgrade to Pro ($8/mo) for unlimited.",
                    "ai_gens_limit": cap,
                    "tier_id": "ctf_pro",
                    "price_usdc": 8,
                },
            )

    # Generate via Groq (may raise → FastAPI turns it into a 502).
    try:
        pack = await aigen.generate_pack(topic)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))

    if not pack["flashcards"] and not pack["challenges"]:
        raise HTTPException(502, "AI returned an empty pack — try rephrasing the topic.")

    # Add flashcards to the deck (dedup by front), tagged with the topic.
    added = 0
    for c in pack["flashcards"]:
        if db.card_exists_by_front(c["front"]):
            continue
        fsrs, due = scheduler.new_card_state()
        tags = c.get("tags", []) or [f"topic:{pack['topic_slug']}"]
        db.insert_card(c["front"], c["back"], "flashcard", pack["topic_slug"], tags, fsrs, due)
        added += 1

    # Replace any prior challenges for this topic, then store the new ones.
    db.delete_gen_challenges_for_slug(pack["topic_slug"])
    for ch in pack["challenges"]:
        db.insert_gen_challenge(ch)
    db.upsert_pack(
        pack["topic"],
        pack["topic_slug"],
        pack["labkit"],
        len(pack["flashcards"]),
        len(pack["challenges"]),
    )

    # Count the generation against the free monthly quota (only on success).
    if not ent["pro"]:
        db.bump_ai_gens(month, identity)

    return {
        "topic": pack["topic"],
        "topic_slug": pack["topic_slug"],
        "cards_added": added,
        "flashcards": len(pack["flashcards"]),
        "challenges": len(pack["challenges"]),
        "has_labkit": len(pack["labkit"]) > 0,
    }


@app.get("/ai/packs")
def list_packs() -> list[dict]:
    packs = db.list_packs()
    out = []
    for p in packs:
        prog = db.topic_card_progress(p["topic_slug"])
        out.append({**p, "progress": prog})
    return out


@app.get("/ai/packs/{slug}")
def get_pack(slug: str) -> dict:
    pack = db.get_pack(slug)
    if not pack:
        raise HTTPException(404, "pack not found")
    prog = db.topic_card_progress(slug)
    solved = db.solved_ids()
    challenges = [
        _strip_gen_challenge(c, c["id"] in solved)
        for c in db.gen_challenges_for_slug(slug)
    ]
    return {**pack, "progress": prog, "unlocked": prog["done"], "challenges": challenges}


@app.get("/ai/packs/{slug}/labkit")
def get_labkit(slug: str):
    pack = db.get_pack(slug)
    if not pack:
        raise HTTPException(404, "pack not found")
    from fastapi.responses import Response

    return Response(
        content=pack["labkit"] or f"# {slug}\n\n(no lab kit)",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-labkit.md"'},
    )


@app.post("/ai/challenges/{cid}/submit")
def submit_gen_challenge(
    cid: str,
    body: FlagIn,
    request: Request,
    x_license: str | None = Header(default=None),
) -> dict:
    """Submit a flag for a practice challenge. Gated behind finishing the
    topic's flashcards (423 if locked)."""
    c = db.get_gen_challenge(cid)
    if not c:
        raise HTTPException(404, "challenge not found")
    # Gate: the topic's flashcards must be finished first.
    prog = db.topic_card_progress(c["topic_slug"])
    if not prog["done"]:
        raise HTTPException(423, {"error": "locked", "message": "Finish this topic's flashcards first."})

    sub = body.flag.strip().lower()
    if not sub.startswith("ctf{") and not sub.endswith("}"):
        sub = f"ctf{{{sub}}}"
    if sub != c["flag"].lower():
        return {"correct": False}

    already = db.is_solved(c["id"])
    db.record_solve(c["id"], c["points"])
    return {
        "correct": True,
        "already_solved": already,
        "points": c["points"],
        "total_points": db.total_points(),
        "solution": c["solution"],
    }


# ----------------------------- command cards (CLI learning) -----------------------------
# Offline command study cards. Captured by the CLI tool, researchable from man
# pages, and reviewable through flashcard / quiz / test / game modes.


class CCCardIn(BaseModel):
    command: str = Field(..., min_length=1)
    front: str = Field(..., min_length=1)
    back: str = Field(..., min_length=1)
    depth: str = "medium"
    tags: list[str] = []


class CCReviewIn(BaseModel):
    correct: bool


@app.get("/cc/cards")
def cc_list_cards_route(depth: Optional[str] = None, tag: Optional[str] = None,
                        due_only: bool = False) -> list[dict]:
    db.cc_init()
    return db.cc_list_cards(depth, tag, due_only)


@app.get("/cc/stats")
def cc_stats_route() -> dict:
    db.cc_init()
    return db.cc_stats()


@app.post("/cc/cards", status_code=201)
def cc_add_card_route(card: CCCardIn) -> dict:
    db.cc_init()
    return db.cc_add_card(card.command, card.front, card.back, card.depth, card.tags)


@app.post("/cc/cards/{cid}/review")
def cc_review_route(cid: int, body: CCReviewIn) -> dict:
    db.cc_init()
    card = None
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM command_cards WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise HTTPException(404, "card not found")
    db.cc_update_rep(cid, body.correct)
    return {"ok": True, "correct": body.correct}


# ----------------------------- review inbox -----------------------------

@app.post("/inbox", status_code=201)
def add_to_inbox(item: InboxIn) -> dict:
    return db.insert_inbox(item.front, item.back, item.kind, item.source, item.detail)


@app.get("/inbox")
def get_inbox(status: str = "pending") -> list[dict]:
    return db.list_inbox(status)


@app.post("/inbox/{iid}/approve", status_code=201)
def approve_inbox(iid: str, edit: InboxApprove) -> dict:
    item = db.get_inbox(iid)
    if not item:
        raise HTTPException(404, "inbox item not found")
    if item["status"] != "pending":
        raise HTTPException(409, f"item already {item['status']}")
    fsrs, due = scheduler.new_card_state()
    card = db.insert_card(
        edit.front or item["front"],
        edit.back or item["back"],
        edit.kind or item["kind"],
        edit.deck,
        edit.tags,
        fsrs,
        due,
    )
    db.set_inbox_status(iid, "approved")
    return card


@app.post("/inbox/{iid}/reject")
def reject_inbox(iid: str) -> dict:
    item = db.get_inbox(iid)
    if not item:
        raise HTTPException(404, "inbox item not found")
    db.set_inbox_status(iid, "rejected")
    return {"ok": True}
