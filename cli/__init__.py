"""CTF Flashcards CLI package — offline command learning.

Usage:
    python -m cli init          # init local database
    python -m cli capture "ls -la" 0   # record a command
    python -m cli pending       # review commands not yet in study deck
    python -m cli study         # interactive study (flashcard/quiz/test/game)
    python -m cli research <cmd> [depth]  # man-page research
"""

from .tracker import (
    capture_command, list_unadded, list_commands, get_command,
    mark_added, stats, init_db, CommandRecord,
)
from .researcher import research, generate_card
from .notify import notify_failed, check_and_notify, pending_count, desktop_notify
from .study import (
    add_card_from_command, add_card_manual, list_cards, update_rep,
    start_session, end_session, cards_for_review, StudyCard, DEPTHS,
)
from .ai_connector import is_configured, explain_command, generate_quiz_item

__all__ = [
    "capture_command", "list_unadded", "list_commands", "get_command",
    "mark_added", "stats", "init_db", "CommandRecord",
    "research", "generate_card",
    "notify_failed", "check_and_notify", "pending_count", "desktop_notify",
    "add_card_from_command", "add_card_manual", "list_cards", "update_rep",
    "start_session", "end_session", "cards_for_review", "StudyCard", "DEPTHS",
    "is_configured", "explain_command", "generate_quiz_item",
]
