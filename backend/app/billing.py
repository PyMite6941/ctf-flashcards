"""Free-tier metering + Pro entitlement.

Free users get a limited number of NEW puzzle solves per UTC day. A Pro license
lifts the cap. Payment + license issuance happen entirely in the GRID Store
(USDC on Base -> 31-day JWT, recorded in Supabase); here we only *verify* a
license, and we do it by calling the GRID Store worker's /verify endpoint — so
entitlement is checked through the same system that took the payment. No shared
secret needed on this side.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# --- config (env-overridable) ---
FREE_DAILY_SOLVES = int(os.environ.get("CTF_FREE_DAILY_SOLVES", "3"))
FREE_MONTHLY_AI_GENS = int(os.environ.get("CTF_FREE_MONTHLY_AI_GENS", "9"))
GRID_STORE_WORKER = os.environ.get(
    "GRID_STORE_WORKER_URL", "https://grid-store-worker.greshamd27.workers.dev"
)
# Only this app's own tier unlocks CTF Pro (keeps it separate from the other
# GRID Store products like Expense Tracker's pro/max).
PRO_TIERS = {"ctf_pro"}

# Small in-process cache so we don't hit the worker on every solve.
_CACHE_TTL = 300  # seconds
_cache: dict[str, tuple[float, dict]] = {}


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def client_identity(request) -> str:
    """Best-effort per-user key. Cloudflare sets CF-Connecting-IP in production."""
    h = request.headers
    ip = (
        h.get("cf-connecting-ip")
        or (h.get("x-forwarded-for", "").split(",")[0].strip())
        or (request.client.host if request.client else "unknown")
    )
    return ip or "unknown"


def verify_license(token: Optional[str]) -> dict:
    """Return {'pro': bool, 'tier': str|None, 'expired': bool}. Never raises."""
    if not token:
        return {"pro": False, "tier": None, "expired": False}
    token = token.strip()

    cached = _cache.get(token)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]

    result = {"pro": False, "tier": None, "expired": False}
    try:
        req = urllib.request.Request(
            GRID_STORE_WORKER.rstrip("/") + "/verify",
            data=json.dumps({"token": token}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
        tier = (data.get("tier") or "").lower()
        result = {
            "pro": bool(data.get("valid")) and tier in PRO_TIERS,
            "tier": tier or None,
            "expired": bool(data.get("expired")),
        }
    except Exception:
        # Fail closed on entitlement (treat as free) but never break the request.
        result = {"pro": False, "tier": None, "expired": False}

    _cache[token] = (time.time(), result)
    return result
