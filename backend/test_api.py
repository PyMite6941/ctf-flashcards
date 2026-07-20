"""Integration tests for the CTF Flashcards backend.

Run:  python -m pytest test_api.py -v   (or just: python test_api.py)
Uses a throwaway temp DB so it never touches your real deck.
"""
import os, tempfile, warnings
warnings.filterwarnings("ignore")

# Point the app at a temp DB *before* importing it.
_tmp = tempfile.NamedTemporaryFile(suffix=".sq3", delete=False)
_tmp.close()
os.environ["CTF_DB_PATH"] = _tmp.name

from fastapi.testclient import TestClient
from app.main import app


def run():
    passed = 0
    def check(cond, msg):
        nonlocal passed
        assert cond, "FAIL: " + msg
        passed += 1
        print("  ok:", msg)

    with TestClient(app) as c:
        # health
        check(c.get("/health").json()["ok"] is True, "health ok")

        # create flashcard + challenge
        fc = c.post("/cards", json={"front": "SSH port?", "back": "22", "deck": "net", "tags": ["p"]})
        check(fc.status_code == 201, "create flashcard -> 201")
        ch = c.post("/cards", json={"front": "spot vuln", "back": "sqli", "kind": "challenge", "deck": "web"})
        check(ch.json()["kind"] == "challenge", "challenge kind persisted")
        fid = fc.json()["id"]

        # list + deck filter
        check(len(c.get("/cards").json()) == 2, "list all = 2")
        check(len(c.get("/cards?deck=net").json()) == 1, "deck filter = 1")

        # get + 404
        check(c.get(f"/cards/{fid}").json()["front"] == "SSH port?", "get card by id")
        check(c.get("/cards/nope").status_code == 404, "get missing -> 404")

        # review queue: both new cards due now
        check(len(c.get("/review/queue").json()) == 2, "queue = 2 due")

        # invalid rating rejected
        check(c.post(f"/cards/{fid}/review", json={"rating": 9}).status_code == 422, "rating 9 -> 422")
        check(c.post(f"/cards/{fid}/review", json={"rating": 0}).status_code == 422, "rating 0 -> 422")

        # FSRS reschedules: 'Again'(1) should come back sooner than 'Easy'(4)
        again_due = c.post(f"/cards/{fid}/review", json={"rating": 1}).json()["due"]
        easy_due = c.post(f"/cards/{ch.json()['id']}/review", json={"rating": 4}).json()["due"]
        check(again_due < easy_due, "Again reschedules sooner than Easy")
        check(c.get("/health").json()["reviews"] == 2, "review count = 2")

        # delete + 404
        check(c.delete(f"/cards/{fid}").status_code == 204, "delete -> 204")
        check(c.delete(f"/cards/{fid}").status_code == 404, "delete again -> 404")
        check(len(c.get("/cards").json()) == 1, "1 card left after delete")

        # inbox lifecycle
        item = c.post("/inbox", json={"front": "raw q", "back": "raw a", "source": "log_watcher",
                                      "detail": "sshd fail"}).json()
        iid = item["id"]
        check(item["status"] == "pending", "inbox item pending")
        check(len(c.get("/inbox").json()) == 1, "1 pending in inbox")

        # approve with edits -> lands in deck
        appr = c.post(f"/inbox/{iid}/approve", json={"front": "edited q", "deck": "monitor", "tags": ["ssh"]})
        check(appr.status_code == 201, "approve -> 201")
        check(appr.json()["front"] == "edited q", "approve applied edit")
        check(appr.json()["deck"] == "monitor", "approve set deck")
        check(len(c.get("/inbox").json()) == 0, "inbox empty after approve")
        check(len(c.get("/inbox?status=approved").json()) == 1, "1 approved item")

        # double-approve blocked
        check(c.post(f"/inbox/{iid}/approve", json={}).status_code == 409, "re-approve -> 409")

        # reject flow + missing
        r2 = c.post("/inbox", json={"front": "junk", "back": "junk", "source": "manual"}).json()
        check(c.post(f"/inbox/{r2['id']}/reject").json()["ok"] is True, "reject ok")
        check(len(c.get("/inbox").json()) == 0, "inbox empty after reject")
        check(c.post("/inbox/missing/reject").status_code == 404, "reject missing -> 404")
        check(c.post("/inbox/missing/approve", json={}).status_code == 404, "approve missing -> 404")

        # ----- CTF puzzles -----
        pl = c.get("/puzzles").json()
        check(pl["total"] == 9, "9 puzzles in catalog")
        check("crypto" in pl["categories"], "categories include crypto")
        check(all("flag" not in p for p in pl["puzzles"]), "flag never leaks in list")
        check(pl["solved"] == 0 and pl["points"] == 0, "start unsolved with 0 points")

        # filtering
        check(all(p["category"] == "web" for p in c.get("/puzzles?category=web").json()["puzzles"]),
              "filter puzzles by category=web")
        check(all(p["difficulty"] == "easy" for p in c.get("/puzzles?difficulty=easy").json()["puzzles"]),
              "filter puzzles by difficulty=easy")

        # detail exposes artifact, hides flag + solution until solved
        d = c.get("/puzzles/base64-basement").json()
        check("artifact" in d and "flag" not in d and "solution" not in d, "detail: artifact yes, flag/solution no")
        check(c.get("/puzzles/nope").status_code == 404, "missing puzzle -> 404")

        # wrong flag rejected, no cards unlocked
        cards_before = len(c.get("/cards").json())
        check(c.post("/puzzles/base64-basement/submit", json={"flag": "ctf{wrong}"}).json()["correct"] is False,
              "wrong flag -> correct:false")
        check(len(c.get("/cards").json()) == cards_before, "wrong flag unlocks no cards")

        # correct flag unlocks concept cards into the deck + awards points
        sub = c.post("/puzzles/base64-basement/submit", json={"flag": "ctf{base64_is_just_encoding}"}).json()
        check(sub["correct"] is True and sub["points"] == 50, "correct flag -> 50 points")
        check(len(sub["added_cards"]) == 2, "solve unlocked 2 cards")
        check(len(c.get("/cards").json()) == cards_before + 2, "2 cards added to deck")
        check(c.get("/puzzles/base64-basement").json()["solved"] is True, "puzzle now marked solved")
        check(c.get("/puzzles/base64-basement").json().get("solution"), "solution revealed after solve")
        check(c.get("/health").json()["points"] == 50, "health points = 50")

        # bare-inner submission also accepted (different puzzle)
        check(c.post("/puzzles/hex-dump/submit", json={"flag": "hex_to_ascii"}).json()["correct"] is True,
              "bare inner flag accepted")

        # re-solving is idempotent (no duplicate cards, no double points)
        again = c.post("/puzzles/base64-basement/submit", json={"flag": "ctf{base64_is_just_encoding}"}).json()
        check(again["already_solved"] is True and len(again["added_cards"]) == 0, "re-solve adds no cards")
        check(c.get("/health").json()["points"] == 50 + 50, "points unchanged by re-solve (still base64+hex)")

        # ----- topics / filtering -----
        topics = c.get("/topics").json()
        tag_names = {t["tag"] for t in topics}
        check("base64" in tag_names and "crypto" in tag_names, "unlocked-card tags appear as topics")
        crypto_q = c.get("/review/queue?tag=crypto&limit=100").json()
        check(len(crypto_q) > 0 and all("crypto" in cd["tags"] for cd in crypto_q),
              "review queue filters by topic tag")
        check(all("crypto" in cd["tags"] for cd in c.get("/cards?tag=crypto").json()),
              "cards filter by tag")

        # ----- free-tier daily solve limit (default 3/day) -----
        # So far this identity has 2 new solves (base64 + hex-dump).
        lim = c.get("/limits").json()
        check(lim["pro"] is False and lim["daily_solve_limit"] == 3, "free tier, cap 3/day")
        check(lim["solves_used_today"] == 2 and lim["solves_remaining"] == 1, "2 used, 1 remaining")

        # 3rd new solve is allowed…
        check(c.post("/puzzles/caesar-cipher/submit", json={"flag": "ctf{et_tu_brute_force}"}).json()["correct"],
              "3rd solve allowed")
        check(c.get("/limits").json()["solves_remaining"] == 0, "0 remaining after 3rd")

        # …4th new solve is blocked with 402 upgrade prompt, and is NOT recorded.
        blocked = c.post("/puzzles/binary-message/submit", json={"flag": "ctf{01_to_ascii}"})
        check(blocked.status_code == 402, "4th new solve -> 402")
        check(blocked.json()["detail"]["tier_id"] == "ctf_pro", "402 names the ctf_pro tier")
        check(c.get("/puzzles/binary-message").json()["solved"] is False, "blocked puzzle stays unsolved")

        # Re-solving an ALREADY-captured puzzle is always free (doesn't count).
        check(c.post("/puzzles/base64-basement/submit", json={"flag": "ctf{base64_is_just_encoding}"}).json()["correct"],
              "re-solve of captured puzzle still allowed at limit")

    print(f"\nALL {passed} CHECKS PASSED")


if __name__ == "__main__":
    try:
        run()
    finally:
        os.unlink(_tmp.name)
