# CLAUDE.md — CTF Flashcards

Cybersecurity active-recall app for RevenueCat **Shipaton 2026** (Next Gen student award). Built from `Downloads/ctf-flashcards-shipaton-plan.md`.

## Shape

Three parts, **one shared backend** serves web + (via Capacitor) both mobile shells:

- `backend/` — FastAPI + SQLite. `app/db.py` owns all SQL (cards/reviews/solves/inbox + tag/topic filters); `app/puzzles.py` is the CTF puzzle catalog; `app/scheduler.py` is the **only** file that imports the `fsrs` library (isolates version quirks); `app/main.py` is the routes. DB file `ctf_flashcards.sq3` is local scratch (gitignored).
- `web/` — React + Vite. Nav: **Home** (dashboard) · **Puzzles** (board + solve view) · **Flashcards** (`ReviewSession`, topic-filtered) · **Add** · **Inbox**. Core recall loop in `src/components/ReviewSession.jsx`. `src/lib/api.js` is the backend client; base URL from `VITE_API_URL`. Build output `dist/` is what Capacitor wraps.
- `monitor/` — opt-in local agent, **separate process**. `watchers/` are plugins implementing the `Watcher` protocol in `watchers/base.py`. Candidates go to the review **inbox**, never straight to the deck.

## CTF puzzles (the flagship feature)

`app/puzzles.py` holds a static `CATALOG` of 9 self-contained, offline-solvable challenges across 6 categories (crypto/web/forensics/reversing/network/misc). **Each artifact is derived from the flag at import time** via stdlib transforms (`_b64`/`_caesar`/`_spaced_hex`/`_xor_hex`/`_binary`/`_b64url`) so puzzle data can never drift out of sync with its answer. Flags never leak to clients (`_strip_flag`); solution + cards are revealed only after a correct submit. **Solving a puzzle unlocks its `cards` into the deck** (deduped by `front`) — puzzles fuel the flashcards. Add a puzzle by appending to `CATALOG`; verify with `test_api.py` (every puzzle is asserted solvable).

Topic filtering: cards carry `tags`; `GET /topics` aggregates them with due-counts; `GET /review/queue?tag=` and `GET /cards?tag=` filter via `tags LIKE '%"tag"%'`.

## Learn (AI topic packs) — Worker only so far

`worker/src/aigen.js` calls **Groq** (`GROQ_API_KEY` secret; model `GROQ_MODEL` default `openai/gpt-oss-120b`, `reasoning_effort: low`) to generate a topic pack: flashcards + practice challenges + a markdown lab kit. **Solvability is guaranteed** — the model outputs a challenge `type` + `flag`; the Worker renders the artifact deterministically via `RENDERERS` (base64/rot13/caesar/hex/binary/xor/reverse) or `concept` (artifact = the question, flag = the answer). JSON parsing is tolerant (`extractJson` strips fences/prose — do NOT rely on `response_format`, gpt-oss support is uncertain). Flow: `POST /ai/generate {topic}` → flashcards into deck (tagged `topic:<slug>`, deck=`<slug>`) + challenges in `gen_challenges` D1 table + pack in `gen_packs`. Challenges are **gated**: `db.topicCardProgress` unlocks them only once every `topic:<slug>` card has FSRS `reps>=1` (all reviewed). Solves recorded in the shared `solves` table (points count). Endpoints: `/ai/packs`, `/ai/packs/:slug`, `/ai/packs/:slug/labkit` (downloadable md), `/ai/challenges/:id/submit`. Frontend: **Learn** tab (`web/src/components/Learn.jsx`). **DIVERGENCE:** the FastAPI twin (`backend/`) does NOT yet have the AI feature — sync it if parity is needed. A live interactive sandbox (real vuln box per topic) is intentionally out of scope (needs container infra).

## Billing / Pro tier (routes through GRID Store)

Free tier = **3 puzzle solves/day** (`CTF_FREE_DAILY_SOLVES`), enforced server-side in `submit_flag`, keyed by client IP (`billing.client_identity`, uses `CF-Connecting-IP` in prod) in the `daily_usage` table. Only **new** captures count; re-solving a captured puzzle is free; Pro bypasses. Over the cap → HTTP **402** with an upgrade payload.

**Pro = $8/mo = 8 USDC / 31 days**, sold through the existing **GRID Store** infra — NOT a separate payment system. `portfolio/store/web-store/worker/index.js` got a new `ctf_pro` tier (8 USDC, 31 days, additive — deploy with `wrangler deploy`). In-page checkout `web/src/components/UpgradeModal.jsx` (ported from the store's `CryptoModal`) pays USDC-on-Base to the store wallet → calls the **same worker `/redeem`** → license recorded in the same Supabase `licenses` table. The license JWT is stored in localStorage (`web/src/lib/license.js`), sent as `X-License` header; backend verifies it via the worker's **`/verify`** (`app/billing.py`) — no shared secret on the CTF side. Crypto can't auto-charge, so "monthly" = renewable 31-day license. Deploy/hosting: see `DEPLOYMENT.md`.

## Hosting — LIVE on Cloudflare (deployed 2026-07-20)

- **Frontend:** Cloudflare Pages — https://ctf-flashcards.pages.dev (project `ctf-flashcards`). Build `web/` with `.env.production` (VITE_API_URL → the Worker). Redeploy: `wrangler pages deploy dist --project-name ctf-flashcards --branch main`.
- **Backend:** Cloudflare **Worker + D1** — https://ctf-flashcards-api.greshamd27.workers.dev. Source in **`worker/`** — a full port of `backend/app` (SQLite→D1, py-fsrs→**ts-fsrs**). D1 db `ctf-flashcards` (`5d1eced8-…`). Redeploy: `cd worker && wrangler deploy`; schema `wrangler d1 execute ctf-flashcards --remote --file=schema.sql`; seed `POST /admin/seed`. The two backends (`worker/` and `backend/`) must stay behavior-identical.
- **Payments:** `ctf_pro` tier is deployed to the live `grid-store-worker`. Client IP for metering comes from `CF-Connecting-IP`.

`backend/` (FastAPI) is retained as the local-dev twin; production is the Worker.

## Accounts (Clerk — optional, frontend-only)

Clerk sign-in is **gated behind `VITE_CLERK_PUBLISHABLE_KEY`** (set in `web/.env.local`). `src/lib/clerk.js` exports `hasClerk`; `main.jsx` mounts `<ClerkProvider>` only when a key exists, else renders `<App>` bare (zero-key demo mode — the app must always run without a key). `src/components/AuthControls.jsx` (SignInButton / UserButton) is rendered in the header **only when `hasClerk`** — never call Clerk hooks/components outside the provider. Scope is **sign-in UI only, shared deck** — backend + DB are untouched, no per-user data. Per-user decks (add `user_id` + verify Clerk JWT server-side) is a deliberate future upgrade. Never hardcode the key; `.env.local` is gitignored.

## Run

```bash
# backend  (from backend/)
uvicorn app.main:app --reload           # :8000 ; python seed.py to load starter cards
# web      (from web/)
npm run dev                             # :5173
# monitor  (from monitor/)
python agent.py --demo                  # proves the log+scan -> inbox pipeline
```

## Gotchas

- The package is **`fsrs`** on PyPI (imports as `fsrs`), *not* `py-fsrs` despite the plan's wording. `Card.to_dict()`/`from_dict()` + `Scheduler.review_card()` are the API used.
- Ratings are ints **1=Again 2=Hard 3=Good 4=Easy** everywhere (API, DB, FSRS, UI) — keep them aligned.
- Monitor console output must stay ASCII (Windows cp1252 console crashes on `→`/unicode).
- FastAPI startup event (which calls `db.init_db()`) only fires when `TestClient` is used as a context manager — remember that in tests.
- Nothing enters the real deck without explicit inbox approval — that safeguard is the point, don't bypass it.

## Roadmap (not built yet)

Capacitor Android → Google Play, Capacitor iOS (demo in video), RevenueCat SDK + paywall in the mobile shells (premium = extra decks / more watcher plugins / higher limits).
