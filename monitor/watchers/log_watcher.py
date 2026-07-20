"""log_watcher — tails system/security logs for noteworthy events.

Turns things you actually encounter (failed logins, firewall drops) into
candidate study cards. Reads a log file incrementally; on Linux point it at
/var/log/auth.log, on Windows export events to a text file or adapt the source.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Iterable

from .base import Candidate

# (compiled pattern, builder(match) -> Candidate) — extend freely.
_RULES = [
    (
        re.compile(r"Failed password for (?:invalid user )?(\S+) from (\S+)", re.I),
        lambda m: Candidate(
            front=f"CHALLENGE: repeated `Failed password for {m.group(1)} from {m.group(2)}` in your auth log. What is happening and how do you respond?",
            back="Likely SSH brute-force / password spray. Response: disable password auth (keys only), block the source IP, rate-limit with fail2ban, and alert if it targets privileged accounts.",
            kind="challenge",
        ),
    ),
    (
        re.compile(r"(UFW BLOCK|firewall).*SRC=(\S+).*DPT=(\d+)", re.I),
        lambda m: Candidate(
            front=f"A firewall dropped inbound traffic from {m.group(2)} to port {m.group(3)}. What service usually runs there and why might it be probed?",
            back=f"Port {m.group(3)} was blocked — look up the common service for it and treat repeated probes as reconnaissance/scanning.",
            kind="flashcard",
        ),
    ),
]


class LogWatcher:
    name = "log_watcher"

    def __init__(self, path: str) -> None:
        self.path = path
        self._offset = 0  # byte offset already consumed

    def poll(self) -> Iterable[Candidate]:
        if not os.path.exists(self.path):
            return []
        out: list[Candidate] = []
        with open(self.path, "r", errors="ignore") as f:
            f.seek(self._offset)
            for line in f:
                for pattern, build in _RULES:
                    m = pattern.search(line)
                    if m:
                        cand = build(m)
                        cand.detail = line.strip()[:300]
                        cand.dedup_key = hashlib.sha1(
                            (self.name + "|" + line.strip()).encode()
                        ).hexdigest()
                        out.append(cand)
                        break
            self._offset = f.tell()
        return out
