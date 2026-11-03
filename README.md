# CTF Flashcards & Challenges

A cybersecurity **active-recall** learning app, built for RevenueCat's **Shipaton 2026** hackathon (targeting the Next Gen student award).

**Learn by doing.** Solve HackTheBox-style **CTF puzzles** (decode, crack, spot the bug). Each flag you capture unlocks the concepts behind it as spaced-repetition flashcards — *the puzzles fuel the questions.* Every review is then free recall (you type your answer *before* seeing it), self-rated Again/Hard/Good/Easy, and scheduled by **FSRS** — the modern successor to Anki's SM-2 — so cards you struggle with come back in minutes and easy ones in weeks.

> Built from `ctf-flashcards-shipaton-plan.md`. See that plan for the full hackathon rationale.

**🌐 Live** (all Cloudflare): app → https://ctf-flashcards.pages.dev · API → https://ctf-flashcards-api.greshamd27.workers.dev
Free tier = 3 puzzle solves/day + 9 AI generations/month; **Pro = $8/mo** (8 USDC on Base) = unlimited, via [GRID Store](https://grid-store.pages.dev). See `DEPLOYMENT.md`.

---

## The loop

1. **Solve** a CTF puzzle — self-contained, offline-solvable (Base64, Caesar, XOR, JWT `alg:none`, hash cracking, log analysis, SQLi spotting…).
2. **Capture the flag** → the puzzle's concept cards drop into your review deck.
3. **Recall** them over time; **FSRS** reschedules each for the moment you're about to forget it.

Cards are tagged by topic, so you can **filter reviews by topic** (crypto, web, forensics, hashes, …).

## Learn (AI) — name a topic, get taught + tested

The **Learn** tab turns the fixed catalog into an AI tutor (Groq):

1. Enter any topic (SQL injection, JWT attacks, buffer overflows…).
2. AI writes **flashcards** for it (into your deck, tagged with the topic) + **practice challenges** + a **downloadable lab kit**.
3. The challenges stay **locked until you've reviewed every flashcard** for that topic — learn first, then prove it.
4. Solve them in-browser (picoCTF-style). Solvability is guaranteed: the AI picks a challenge type + writes the flag, and the **Worker renders the artifact deterministically** (base64/hex/xor/caesar/binary/reverse), plus `concept` challenges that test the topic directly. The lab kit is for hands-on practice in **your own environment**.

Requires a Groq key: `cd worker && wrangler secret put GROQ_API_KEY` (model defaults to `openai/gpt-oss-120b`).

---

## Architecture

Production is **all Cloudflare**: static frontend on Pages, backend as a Worker on D1, billing through the GRID Store worker. The Python backend is kept for local dev / reference and is a 1:1 match of the Worker.

```
ctf-flashcards/
├── worker/           Cloudflare Worker + D1 — PRODUCTION backend (deployed)
│   ├── src/index.js      routes (fetch handler)
│   ├── src/db.js         D1 storage
│   ├── src/puzzles.js    CTF puzzle catalog
│   ├── src/scheduler.js  FSRS via ts-fsrs
│   ├── src/billing.js    daily free cap + Pro entitlement
│   └── schema.sql        D1 schema
├── backend/          FastAPI + SQLite — local-dev twin of the Worker (py-fsrs)
│   └── app/              main · db · puzzles · scheduler · billing · aigen
├── web/              React + Vite — deployed to Cloudflare Pages
│   └── src/components/   Home · Puzzles · ReviewSession · AddCard · Inbox ·
│                           QuizMode · TestMode · PracticeGame · Analytics ·
│                           Badges · Scenarios · ImportExport · Tutorial ·
│                           DepthToggle · UpgradeModal · AuthControls
├── cli/              Python CLI command tracker (capture + FSRS study deck)
│   ├── __main__.py       CLI entry point
│   ├── tracker.py        SQLite storage + capture
│   ├── researcher.py     man-page research for flashcard generation
│   ├── error_analyzer.py failure diagnosis + fix suggestions
│   └── shell_integration.sh  bash/zsh auto-capture (buffered)
├── monitor/          Opt-in local agent — plugin watchers push candidate cards
│   └── watchers/         base · log_watcher · tool_watcher  (drop in more)
├── docs/             GitHub Pages landing site (deployed via Actions)
└── DOCUMENTATION.md  Full project documentation
```

Web nav: **Home** · **Learn (AI)** · **Puzzles** · **Flashcards** · **Quiz** · **Test** · **Practice Game** · **Analytics** · **Badges** · **Scenarios** · **Import/Export** · **Add** · **Inbox**.

**Build order (from the plan):** shared backend → web app → Capacitor Android/iOS wrap → RevenueCat SDK. The backend stays shared the whole way — no per-platform logic.

---

## Run it locally

### 1. Backend
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload   # serves on http://localhost:8000
python seed.py                  # optional: load starter cyber cards + challenges
```

### 2. Web app
```bash
cd web
npm install
npm run dev                     # http://localhost:5173
# point at a non-default backend with:  VITE_API_URL=http://host:port npm run dev
```

### 3. CLI command tracker

```bash
# From repo root (Windows):
backend\.venv\Scripts\python.exe -m cli init
backend\.venv\Scripts\python.exe -m cli stats
```

### Keyboard Shortcuts (web app)

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` / `Cmd+K` | Jump to Add (capture) tab |
| `?` | Open/reopen tutorial |
| `1-9` | Switch to tab N |

### 4. Local monitor (optional, opt-in)
```bash
cd monitor
python agent.py --demo          # generates fake auth.log + nmap output, pushes to the inbox
# real use:
cp monitor.config.example.json monitor.config.json   # edit paths + enable watchers
python agent.py                 # loops, polling your logs/tool output
```
Candidates never enter the deck directly — they land in the **review inbox** in the web app, where you approve (and edit) or reject them.

### Accounts (Clerk — optional)

Sign-in and "connect account" flows are powered by [Clerk](https://clerk.com), and are **entirely optional**: with no key the app runs in zero-key demo mode (no auth, one shared deck).

To turn accounts on:
1. Create an app at [dashboard.clerk.com](https://dashboard.clerk.com) and enable the social connections you want (Google, GitHub, …) under **User & Authentication → Social Connections**.
2. Copy `web/.env.example` to `web/.env.local` and set `VITE_CLERK_PUBLISHABLE_KEY=pk_test_…`.
3. Restart `npm run dev`. A **Sign in** button appears in the header; once signed in it becomes Clerk's **UserButton**, whose "Manage account" panel is where users link social accounts.

Only the frontend publishable key is used (safe to expose). The deck is still shared for now — per-user decks are a later upgrade. The publishable key lives in `.env.local`, which is gitignored.

---

## The recall loop

1. Card shows a prompt (a question, or a `CHALLENGE:` — spot-the-vuln, decode a hash, read a log line).
2. You type your answer **from memory** first.
3. Reveal the correct answer.
4. Self-rate **Again / Hard / Good / Easy** → FSRS reschedules the card.

Mixing definitional recall with applied challenges (same loop, different retrieval) is deliberate — it strengthens memory beyond plain flashcards.

---

## Content input (plan §6)

- **Manual** — the **Add** tab: flashcards or challenges, by hand.
- **Local monitor (automatic, opt-in)** — watchers generate candidates → review inbox → your approval → deck.

### Adding a watcher
Drop a new file in `monitor/watchers/` implementing the `Watcher` protocol (`name` + `poll() -> Iterable[Candidate]`) from `watchers/base.py`, then register its `type` in `agent.build_watchers`. The core never changes.

---

## Where RevenueCat fits

The RevenueCat SDK powers the paid tier in the **mobile shells** (satisfying the hackathon's in-app-purchase requirement). Natural premium features:

- Additional card packs / topic decks
- Unlocking extra local-monitor watcher plugins
- Removing limits on manual cards / inbox size

The web build shows the premium surface as a placeholder; the SDK is wired in when the app is wrapped with Capacitor (`npx cap add android` / `ios`, with `web/dist` as the `webDir`).

---

## Status

- [x] Backend **live on Cloudflare Workers + D1** (ts-fsrs), full route parity with the Python twin
- [x] Frontend **live on Cloudflare Pages**, wired to the Worker
- [x] Web app: Home dashboard · Puzzles board + solve · topic-filtered Flashcards · Add · Inbox
- [x] 9 self-contained CTF puzzles across 6 categories; solving unlocks concept cards
- [x] Topic (tag) filtering on reviews and cards
- [x] **Free tier: 3 puzzle solves/day**; **Pro $8/mo** via in-page USDC checkout through GRID Store (`ctf_pro` tier live)
- [x] **Learn (AI)**: Groq generates topic flashcards + practice challenges + lab kit; challenges gated behind flashcard review; deterministic (solvable) artifacts
- [x] Optional Clerk sign-in (zero-key demo fallback)
- [x] Local monitor with plugin watchers (log + tool), inbox-safeguarded
- [x] CLI command tracker: capture, pending, failed, add, research, study (flashcard/quiz/test/game)
- [x] Shell integration: buffered auto-capture (no Python spawn per command)
- [x] Tutorial: 5-step onboarding, shows once per user
- [x] Badges: 8 achievements (First Steps, Command Collector, Command Master, streaks, Card Master, Perfect Score, Scenario Solver)
- [x] 57-check backend test suite (`python test_api.py`), every puzzle verified solvable
- [ ] Capacitor Android/iOS shells + RevenueCat (mobile paid tier) — future

## API quick reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + review/points/solved counts |
| GET/POST | `/cards` | list (`?deck=` `?tag=`) / create cards |
| DELETE | `/cards/{id}` | remove a card |
| GET | `/topics` | distinct tags with due/total counts (topic filter) |
| GET | `/review/queue?limit=&tag=` | cards due now, optionally one topic |
| POST | `/cards/{id}/review` | submit a rating (1–4), FSRS reschedules |
| GET | `/puzzles?category=&difficulty=&status=` | challenge board (flags never leaked) |
| GET | `/puzzles/{id}` | puzzle detail + artifact (solution hidden until solved) |
| POST | `/puzzles/{id}/submit` | submit a flag → awards points, unlocks concept cards |
| GET/POST | `/inbox` | list pending / add a candidate |
| POST | `/inbox/{id}/approve` | approve (with edits) → deck |
| POST | `/inbox/{id}/reject` | reject a candidate |
| GET | `/cc/cards` | list command cards (depth/tag/due filters) |
| POST | `/cc/cards` | add a command card |
| POST | `/cc/cards/{id}/review` | review a command card (correct/wrong) |
| GET | `/cc/stats` | command card stats |
| POST | `/ai/generate` | generate AI topic pack |
| GET | `/ai/packs` | list AI topic packs |
| GET | `/badges` | list all badges |
| GET | `/badges/earned` | user's earned badges |
| POST | `/badges/check` | check & award badges |
| GET | `/progress/stats` | aggregate progress stats |
| POST | `/progress/snapshot` | record daily progress |
| GET | `/scenarios` | list command chaining scenarios |
| POST | `/scenarios` | create a scenario |
| POST | `/scenarios/{id}/attempt` | start a scenario attempt |
| POST | `/scenarios/attempts/{id}` | record attempt commands |
| GET | `/export/cards?format=json\|csv\|markdown` | export deck |
| POST | `/import/cards` | import deck (JSON array) |

### Adding a puzzle
Append a dict to `CATALOG` in `backend/app/puzzles.py`: `id`, `title`, `category`, `difficulty`, `points`, `description`, `hint`, `flag`, `artifact` (derive it from the flag with the `_b64`/`_caesar`/`_xor_hex`/… helpers so it can't drift), `solution`, and `cards` (the concept flashcards it unlocks, each with `tags` for topic filtering).
