"""Shared watcher interface.

Every data source is a swappable module implementing `Watcher`. New sources drop
in as new files under watchers/ — the core never has to change (plan §5).

A watcher's job is narrow: look at some real security activity and yield
*candidate cards* (question/answer pairs). It never writes to the real deck — the
runner pushes candidates into the review inbox, where you approve or reject them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class Candidate:
    """A proposed flashcard, pending human approval in the review inbox."""

    front: str                      # the prompt / question
    back: str                       # the suggested answer / explanation
    kind: str = "flashcard"         # 'flashcard' | 'challenge'
    detail: str = ""                # raw context (the log line, scan snippet, ...)
    dedup_key: str = ""             # stable key so we don't re-propose the same thing


class Watcher(Protocol):
    """Interface every watcher module must satisfy."""

    name: str

    def poll(self) -> Iterable[Candidate]:
        """Return any new candidate cards since the last poll."""
        ...
