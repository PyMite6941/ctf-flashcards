"""Seed the deck with a handful of starter cybersecurity cards and challenges.

Run once against a running API:  python seed.py  [http://localhost:8000]
Safe to skip — the app works fine with an empty deck.
"""

import sys
import urllib.request
import json

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

CARDS = [
    # --- flashcards: free recall, not multiple choice ---
    ("What port does HTTPS use by default?", "TCP 443", "flashcard", "networking", ["ports"]),
    ("What does the CIA triad stand for?",
     "Confidentiality, Integrity, Availability", "flashcard", "concepts", ["fundamentals"]),
    ("Which HTTP header mitigates clickjacking?",
     "X-Frame-Options (or Content-Security-Policy frame-ancestors)", "flashcard", "web", ["headers"]),
    ("What is the difference between a hash and encryption?",
     "Hashing is one-way (no key, not reversible); encryption is two-way (reversible with a key).",
     "flashcard", "crypto", ["fundamentals"]),
    ("What nmap flag runs a SYN 'stealth' scan?",
     "-sS", "flashcard", "tools", ["nmap"]),
    ("What is the purpose of a salt in password hashing?",
     "A unique random value per password so identical passwords hash differently, defeating rainbow tables.",
     "flashcard", "crypto", ["passwords"]),

    # --- challenges: apply the knowledge, same recall->reveal->rate loop ---
    ("CHALLENGE: Spot the flaw — `query = \"SELECT * FROM users WHERE name = '\" + name + \"'\"`",
     "SQL injection: `name` is concatenated straight into the query. Fix with parameterized queries / prepared statements.",
     "challenge", "web", ["sqli"]),
    ("CHALLENGE: Decode this Base64 — `Y3RmezBrX3RoYXRzX2Jhc2U2NH0=`",
     "ctf{0k_thats_base64}", "challenge", "crypto", ["encoding"]),
    ("CHALLENGE: A log line reads `sshd: Failed password for root from 203.0.113.9 port 22 ssh2` repeated 400x in 1 min. What is it?",
     "An SSH brute-force / password-spray attempt. Mitigate: disable root SSH, use keys, rate-limit (fail2ban).",
     "challenge", "blue-team", ["logs"]),
    ("CHALLENGE: What kind of hash is `5f4dcc3b5aa765d61d8327deb882cf99` and what does it hash?",
     "32 hex chars = MD5. This is the well-known MD5 of the string 'password'.",
     "challenge", "crypto", ["hashes"]),
]


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main() -> None:
    for front, back, kind, deck, tags in CARDS:
        post("/cards", {"front": front, "back": back, "kind": kind, "deck": deck, "tags": tags})
    print(f"Seeded {len(CARDS)} cards into {BASE}")


if __name__ == "__main__":
    main()
