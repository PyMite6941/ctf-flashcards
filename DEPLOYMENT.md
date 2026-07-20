# Deploying CTF Flashcards

**Everything is live on Cloudflare** (same account as GRID Store, `3f8d84ab…`).

| Piece | URL / resource |
|---|---|
| **Frontend** (Cloudflare Pages) | https://ctf-flashcards.pages.dev |
| **Backend API** (Worker + D1) | https://ctf-flashcards-api.greshamd27.workers.dev |
| **D1 database** | `ctf-flashcards` (`5d1eced8-d2a4-4cad-8f08-b505f8a47cf5`) |
| **Payments / licenses** | your existing `grid-store-worker` (now has a `ctf_pro` tier) |

Billing runs entirely through GRID Store — no new payment infra. A Pro purchase is a USDC-on-Base payment verified on-chain by `grid-store-worker`, recorded in the same Supabase `licenses` table.

---

## Architecture (all Cloudflare)

```
Browser ──▶ ctf-flashcards.pages.dev            (Pages: React/Vite static)
                │ VITE_API_URL
                ▼
        ctf-flashcards-api.greshamd27.workers.dev   (Worker: routes + FSRS via ts-fsrs)
                │            │
                ▼            ▼ X-License / entitlement
             D1 (ctf-flashcards)   grid-store-worker /verify  ──▶ Supabase licenses
```

The backend is a full port of the Python app (`backend/app`) — same routes, same behaviour — with SQLite→D1 and py-fsrs→ts-fsrs. Source: `worker/`.

---

## Redeploying

### Backend (Worker + D1)
```bash
cd portfolio/ctf-flashcards/worker
npm install
# schema changes only:
npx wrangler d1 execute ctf-flashcards --remote --file=schema.sql
npx wrangler deploy
# one-time (or after a reset) seed of starter cards:
curl -X POST https://ctf-flashcards-api.greshamd27.workers.dev/admin/seed
```
Vars in `wrangler.toml`: `GRID_STORE_WORKER_URL`, `CTF_FREE_DAILY_SOLVES` (default 3).
Optional secret to lock `/admin/seed`: `npx wrangler secret put ADMIN_KEY`.

### Frontend (Pages)
```bash
cd portfolio/ctf-flashcards/web
npm install && npm run build              # uses .env.production (VITE_API_URL = the Worker)
npx wrangler pages deploy dist --project-name ctf-flashcards --branch main
```
To enable Clerk sign-in on the hosted site, add `VITE_CLERK_PUBLISHABLE_KEY` in
Pages → Settings → Environment variables (or `.env.production`) and rebuild.

### Pro tier (GRID Store worker)
The `ctf_pro` tier (8 USDC / 31 days) lives in `portfolio/store/web-store/worker/index.js`.
```bash
cd portfolio/store/web-store && npx wrangler deploy
```
Additive — the Expense-Tracker `pro`/`max` tiers are untouched; existing secrets/bindings persist.

---

## How a Pro purchase works

1. Free user hits the 3-solves/day cap → the in-page checkout opens (no redirect).
2. They send **8 USDC on Base** to the store wallet, paste tx hash + email.
3. App → `grid-store-worker /redeem` (`tier: ctf_pro`) → verifies on-chain → mints a 31-day JWT → records it in Supabase → returns the license.
4. App stores it, sends `X-License` on API calls; the Worker verifies via `grid-store-worker /verify` → unlimited solves.

Crypto can't auto-charge, so "monthly" = pay 8 USDC for 31 days, renew by paying again (same model as Expense Tracker Pro).

---

## Status

- [x] Backend ported to **Cloudflare Workers + D1** and deployed (ts-fsrs, full route parity)
- [x] Frontend deployed to **Cloudflare Pages**, wired to the Worker
- [x] `ctf_pro` tier deployed to the GRID Store worker (real purchases verify on-chain)
- [x] Free tier: 3 puzzle solves/day, enforced in the Worker (keyed by `CF-Connecting-IP`)
- [x] In-page USDC checkout; entitlement verified through GRID Store `/verify`
- [x] Starter deck seeded; end-to-end verified live

### Notes
- The original **FastAPI backend** (`backend/`) is retained for local dev / reference; production runs the Worker.
- The daily limit is keyed by client IP (no per-user accounts yet — Clerk is sign-in-only). Per-user metering would key by Clerk user id instead.
