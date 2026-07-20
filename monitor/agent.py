"""Local monitor agent.

A toggleable, on/off local process (separate from the web/mobile app) that runs a
set of plugin watchers and pushes their candidate cards into the app's review
inbox — never straight into the deck (plan §5 safeguard).

Usage:
    python agent.py --once            # single pass, then exit
    python agent.py                   # loop, polling every --interval seconds
    python agent.py --demo            # seed a fake log + scan and prove the pipeline

Config: monitor.config.json (see monitor.config.example.json).
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from typing import Iterable

from watchers import Candidate, LogWatcher, ToolWatcher

HERE = os.path.dirname(__file__)
_seen_keys: set[str] = set()


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        return {
            "api_url": "http://localhost:8000",
            "interval_seconds": 30,
            "watchers": [],
        }
    with open(path) as f:
        return json.load(f)


def build_watchers(cfg: dict) -> list:
    built = []
    for w in cfg.get("watchers", []):
        if not w.get("enabled", True):
            continue
        if w["type"] == "log":
            built.append(LogWatcher(w["path"]))
        elif w["type"] == "tool":
            built.append(ToolWatcher(w["path"]))
        else:
            print(f"[monitor] unknown watcher type: {w['type']}")
    return built


def push(api_url: str, source: str, c: Candidate) -> bool:
    """Send a candidate to the review inbox. Returns True if accepted."""
    body = json.dumps(
        {"front": c.front, "back": c.back, "kind": c.kind, "source": source, "detail": c.detail}
    ).encode()
    req = urllib.request.Request(
        api_url.rstrip("/") + "/inbox", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status in (200, 201)
    except Exception as e:  # network hiccup shouldn't crash the loop
        print(f"[monitor] push failed: {e}")
        return False


def run_pass(watchers: Iterable, api_url: str) -> int:
    pushed = 0
    for w in watchers:
        for cand in w.poll():
            key = cand.dedup_key or (w.name + cand.front)
            if key in _seen_keys:
                continue
            _seen_keys.add(key)
            if push(api_url, w.name, cand):
                pushed += 1
                print(f"[monitor] {w.name} -> inbox: {cand.front[:70]}")
    return pushed


def write_demo_fixtures() -> dict:
    """Create sample log + nmap files so the pipeline can be shown end-to-end."""
    logp = os.path.join(HERE, "_demo_auth.log")
    scanp = os.path.join(HERE, "_demo_scan.txt")
    with open(logp, "w") as f:
        f.write(
            "Jul 19 06:11:02 host sshd[2211]: Failed password for root from 203.0.113.9 port 40122 ssh2\n"
            "Jul 19 06:11:03 host sshd[2213]: Failed password for invalid user admin from 203.0.113.9 port 40130 ssh2\n"
        )
    with open(scanp, "w") as f:
        f.write(
            "Nmap scan report for 10.0.0.5\n"
            "PORT     STATE SERVICE VERSION\n"
            "22/tcp   open  ssh     OpenSSH 8.9p1\n"
            "80/tcp   open  http    nginx 1.24.0\n"
        )
    return {"api_url": "http://localhost:8000", "interval_seconds": 30, "watchers": [
        {"type": "log", "path": logp, "enabled": True},
        {"type": "tool", "path": scanp, "enabled": True},
    ]}


def main() -> None:
    ap = argparse.ArgumentParser(description="CTF Flashcards local monitor")
    ap.add_argument("--config", default=os.path.join(HERE, "monitor.config.json"))
    ap.add_argument("--once", action="store_true", help="one pass then exit")
    ap.add_argument("--demo", action="store_true", help="generate fixtures and run once")
    ap.add_argument("--interval", type=int, default=None, help="override poll interval (s)")
    args = ap.parse_args()

    cfg = write_demo_fixtures() if args.demo else load_config(args.config)
    api_url = cfg.get("api_url", "http://localhost:8000")
    interval = args.interval or cfg.get("interval_seconds", 30)
    watchers = build_watchers(cfg)

    if not watchers:
        print("[monitor] no watchers enabled. Edit monitor.config.json or run --demo.")
        return

    print(f"[monitor] {len(watchers)} watcher(s) active -> {api_url}/inbox")

    if args.once or args.demo:
        n = run_pass(watchers, api_url)
        print(f"[monitor] pushed {n} candidate(s) to the review inbox.")
        return

    try:
        while True:
            run_pass(watchers, api_url)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[monitor] stopped.")


if __name__ == "__main__":
    main()
