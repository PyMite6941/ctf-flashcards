"""FSRS scheduling wrapper.

Uses py-fsrs (the Free Spaced Repetition Scheduler) rather than the older SM-2.
This module is the *only* place that touches the FSRS library, so the rest of the
app deals in plain dicts and never has to care about library version quirks.
"""

from __future__ import annotations

from typing import Any

from fsrs import Card, Rating, Scheduler

# One shared scheduler with library defaults is fine for a single-user app.
_scheduler = Scheduler()

# Rating ints used across the API / DB: 1=Again 2=Hard 3=Good 4=Easy
_RATING_BY_INT = {
    1: Rating.Again,
    2: Rating.Hard,
    3: Rating.Good,
    4: Rating.Easy,
}


def new_card_state() -> tuple[dict[str, Any], str]:
    """Fresh FSRS state for a brand-new card. Returns (fsrs_dict, due_iso)."""
    card = Card()
    return card.to_dict(), card.due.isoformat()


def review(fsrs_dict: dict[str, Any], rating: int) -> tuple[dict[str, Any], str]:
    """Apply a self-rating to an existing card. Returns (new_fsrs_dict, due_iso)."""
    if rating not in _RATING_BY_INT:
        raise ValueError(f"rating must be 1-4, got {rating}")
    card = Card.from_dict(fsrs_dict)
    card, _log = _scheduler.review_card(card, _RATING_BY_INT[rating])
    return card.to_dict(), card.due.isoformat()
