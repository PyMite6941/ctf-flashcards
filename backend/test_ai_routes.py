"""Quick verification of the new AI routes on the FastAPI backend."""
import os, tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".sq3", delete=False)
_tmp.close()
os.environ["CTF_DB_PATH"] = _tmp.name

from fastapi.testclient import TestClient
from app.main import app

passed = 0


def check(cond, msg):
    global passed
    assert cond, "FAIL: " + msg
    passed += 1
    print("  ok:", msg)


with TestClient(app) as c:
    # limits includes AI gens fields
    j = c.get("/limits").json()
    check("ai_gens_limit" in j and "ai_gens_remaining" in j and "ai_gens_used_this_month" in j,
          "limits returns AI gen fields")
    check(j["ai_gens_limit"] == 9 and j["ai_gens_remaining"] == 9 and j["ai_gens_used_this_month"] == 0,
          "defaults: 9 limit, 9 remaining, 0 used")

    # packs empty initially
    check(c.get("/ai/packs").json() == [], "ai/packs empty initially")
    check(c.get("/ai/packs/nonexistent").status_code == 404, "get missing pack -> 404")
    check(c.get("/ai/packs/nonexistent/labkit").status_code == 404, "labkit missing -> 404")

    # generate without GROQ_API_KEY -> 502 (AI not configured)
    os.environ.pop("GROQ_API_KEY", None)
    r = c.post("/ai/generate", json={"topic": "SQL injection"})
    check(r.status_code == 502, "ai/generate no key -> 502")
    detail = str(r.json().get("detail", ""))
    check("not configured" in detail.lower(), f"502 says not configured ({detail})")

    # generate with empty topic -> 422
    r = c.post("/ai/generate", json={"topic": ""})
    check(r.status_code == 422, "empty topic -> 422")

    # challenge submit 404 for missing
    check(c.post("/ai/challenges/nope/submit", json={"flag": "ctf{x}"}).status_code == 404,
          "submit missing challenge -> 404")

print(f"\nALL {passed} AI ROUTE CHECKS PASSED")
os.unlink(_tmp.name)
