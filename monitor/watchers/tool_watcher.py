"""tool_watcher — parses output from tools you run yourself (nmap, etc.).

Feed it a file that a tool wrote (e.g. `nmap -oN scan.txt target`) and it turns
open-port findings into candidate cards, so the things you discover become the
things you review.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Iterable

from .base import Candidate

# nmap normal-output port line, e.g. "22/tcp   open  ssh   OpenSSH 8.9p1"
_NMAP_PORT = re.compile(r"^(\d+)/(tcp|udp)\s+open\s+(\S+)(?:\s+(.*))?$", re.M)


class ToolWatcher:
    name = "tool_watcher"

    def __init__(self, path: str) -> None:
        self.path = path
        self._seen: set[str] = set()

    def poll(self) -> Iterable[Candidate]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", errors="ignore") as f:
            text = f.read()

        out: list[Candidate] = []
        for port, proto, service, version in _NMAP_PORT.findall(text):
            key = hashlib.sha1(f"{self.name}|{port}/{proto}|{service}".encode()).hexdigest()
            if key in self._seen:
                continue
            self._seen.add(key)
            ver = (version or "").strip()
            out.append(
                Candidate(
                    front=f"Your scan found {service} open on {port}/{proto}"
                    + (f" ({ver})" if ver else "")
                    + ". What is this service and what's one common risk to check?",
                    back=f"{service} on {port}/{proto}"
                    + (f", version {ver}. " if ver else ". ")
                    + "Verify it should be exposed, check for known CVEs on that version, and confirm auth/hardening.",
                    kind="flashcard",
                    detail=f"{port}/{proto} open {service} {ver}".strip(),
                    dedup_key=key,
                )
            )
        return out
