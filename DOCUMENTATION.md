# CTF Flashcards — Documentation

Active-recall cybersecurity training. Capture terminal commands, review them with
spaced repetition (FSRS), quiz yourself, track progress, and earn badges — all
offline, no server required.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Features](#features)
3. [Quick Start](#quick-start)
4. [Backend (FastAPI + SQLite)](#backend-fastapi--sqlite)
5. [Frontend (React + Vite)](#frontend-react--vite)
6. [CLI Command Tracker](#cli-command-tracker)
7. [Shell Integration (Buffered Auto-Capture)](#shell-integration-buffered-auto-capture)
8. [Learning & Teaching Features](#learning--teaching-features)
9. [Accessibility & Ease of Use](#accessibility--ease-of-use)
10. [Resource Efficiency](#resource-efficiency)
11. [Deployment](#deployment)
12. [Verification](#verification)
13. [Troubleshooting](#troubleshooting)

---

## Project Structure

```
ctf-flashcards/
├── backend/                 # FastAPI + SQLite (local-dev twin)
│   ├── app/
│   │   ├── main.py          # API routes
│   │   ├── db.py            # All SQL + storage helpers
│   │   ├── puzzles.py       # CTF puzzle catalog (9 offline challenges)
│   │   ├── scheduler.py     # FSRS scheduling (only file importing fsrs)
│   │   ├── billing.py       # Free-tier/Pro metering via GRID Store worker
│   │   └── aigen.py         # AI topic pack generation (Groq)
│   ├── test_api.py          # Backend integration tests (57 checks)
│   ├── test_ai_routes.py    # AI route tests (9 checks)
│   ├── seed.py              # Seed starter cards
│   └── requirements.txt
├── web/                     # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx          # Tab router, keyboard shortcuts, tutorial state
│   │   ├── lib/api.js       # Backend client
│   │   ├── lib/clerk.js     # Optional Clerk auth
│   │   ├── lib/license.js   # Pro license (GRID Store)
│   │   ├── components/
│   │   │   ├── Home.jsx
│   │   │   ├── ReviewSession.jsx   # FSRS flashcard review
│   │   │   ├── Puzzles.jsx         # CTF puzzle board
│   │   │   ├── Learn.jsx           # AI topic packs
│   │   │   ├── AddCard.jsx         # Manual card entry
│   │   │   ├── Inbox.jsx           # Review inbox
│   │   │   ├── QuizMode.jsx        # Multiple-choice quizzes
│   │   │   ├── TestMode.jsx        # Timed recall tests
│   │   │   ├── PracticeGame.jsx    # Typing speed/accuracy game
│   │   │   ├── Analytics.jsx       # Progress heatmap + stats
│   │   │   ├── Badges.jsx          # Achievements
│   │   │   ├── Scenarios.jsx       # Command chaining challenges
│   │   │   ├── ImportExport.jsx    # JSON/CSV/Markdown deck I/O
│   │   │   ├── Tutorial.jsx        # 5-step onboarding
│   │   │   ├── DepthToggle.jsx     # Shallow/Medium/Deep detail
│   │   │   ├── UpgradeModal.jsx    # Pro checkout
│   │   │   └── AuthControls.jsx    # Clerk sign-in
│   │   └── styles.css          # Dark theme + accessibility styles
│   └── vite.config.js
├── cli/                     # Python CLI command tracker
│   ├── __main__.py          # CLI entry point (init/stats/capture/add/...)
│   ├── tracker.py           # SQLite storage + capture
│   ├── researcher.py        # Man-page research for flashcard generation
│   ├── error_analyzer.py    # Failure diagnosis + fix suggestions
│   ├── shell_integration.sh # Bash/zsh auto-capture (buffered)
│   └── commands.db          # Local SQLite (gitignored)
├── worker/                  # Cloudflare Worker + D1 (production twin)
├── docs/                    # GitHub Pages landing site
├── .github/workflows/pages.yml  # GitHub Actions deploy
└── CLAUDE.md                # Project plan & conventions
```

---

## Features

### Core Recall Loop
- **Flashcards**: Free recall — type your answer before revealing, then rate Again/Hard/Good/Easy. FSRS reschedules each card.
- **Puzzles**: 9 offline-solvable CTF challenges (Base64, Caesar, MD5, hex, binary, XOR, JWT, SQL injection, log analysis). Solving unlocks concept cards into your deck.
- **Inbox**: Candidate cards from the local monitor land here. Nothing enters the deck without explicit approval.

### Learning & Teaching Features
- **Tutorial**: 5-step interactive onboarding. Shows once per user (localStorage).
- **Quiz**: Multiple-choice questions about command cards.
- **Test**: Timed recall — type the command against the clock.
- **Practice Game**: Type commands for speed + accuracy with streak tracking.
- **Analytics**: 30-day review heatmap, accuracy %, active days, time spent.
- **Badges**: 8 achievements (First Steps, Command Collector, Command Master, streaks, Perfect Score, Scenario Solver).
- **Scenarios**: Multi-step terminal challenges with objectives and hints.
- **Import/Export**: JSON, CSV (Anki-compatible), Markdown.

### Depth Levels
Each flashcard can be viewed at **shallow** (one-liner), **medium** (usage + key flags), or **deep** (full man-page detail). Choose per-tab or per-card.

### Personal Notes
Add notes to any card for your own memory aids.

---

## Quick Start

### Prerequisites
- Python 3.11+ with the `backend/.venv` virtualenv (fastapi, uvicorn, fsrs, httpx)
- Node.js/npm with `web/node_modules` installed

### 1. Start the Backend

```bash
cd backend
# Activate the project venv (Windows)
backend\.venv\Scripts\activate
# Or on Linux/Mac:
source backend/.venv/bin/activate

# Initialize the database
uvicorn app.main:app --reload
# Health check: http://localhost:8000/health
```

### 2. Start the Frontend

```bash
cd web
npm install        # first time only
npm run dev        # :5173
# Open: http://localhost:5173
```

### 3. Initialize the CLI

```bash
# From repo root, using the backend venv python
backend\.venv\Scripts\python.exe -m cli init
backend\.venv\Scripts\python.exe -m cli stats
```

### 4. Enable Shell Auto-Capture (optional)

Source the shell integration in your `~/.bashrc` or `~/.zshrc`:

```bash
echo 'source /path/to/ctf-flashcards/cli/shell_integration.sh' >> ~/.bashrc
source ~/.bashrc
```

Every command you type is logged to a buffer and flushed to SQLite in batches (no Python spawn per command).

---

## Backend (FastAPI + SQLite)

The backend is the single source of truth. All routes are in `backend/app/main.py`, all SQL in `backend/app/db.py`.

### Key Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/health` | GET | Health check + stats |
| `/cards` | GET/POST | List/create flashcards |
| `/cards/{id}/review` | POST | Submit FSRS rating (1-4) |
| `/review/queue` | GET | Due cards for review |
| `/topics` | GET | Topic tags with due/total counts |
| `/puzzles` | GET | CTF puzzle catalog |
| `/puzzles/{id}/submit` | POST | Submit a flag |
| `/limits` | GET | Free-tier/Pro status |
| `/ai/generate` | POST | Generate AI topic pack |
| `/ai/packs` | GET | List AI topic packs |
| `/cc/cards` | GET/POST | Command cards (list/add) |
| `/cc/cards/{id}/review` | POST | Review a command card |
| `/cc/stats` | GET | Command card stats |
| `/badges` | GET | List all badges |
| `/badges/earned` | GET | User's earned badges |
| `/progress/snapshot` | POST | Record daily progress |
| `/progress/stats` | GET | Aggregate progress stats |
| `/scenarios` | GET/POST | Command chaining scenarios |
| `/export/cards` | GET | Export deck (JSON/CSV/Markdown) |
| `/import/cards` | POST | Import deck (JSON array) |

### Free Tier
- 3 puzzle solves/day, 9 AI generations/month (per IP or per Clerk user when signed in)
- Pro ($8/mo, USDC on Base via GRID Store) lifts both caps

---

## Frontend (React + Vite)

Build output goes to `web/dist/` (what Capacitor wraps for mobile).

### Navigation Tabs
Home → Learn (AI) → Puzzles → Flashcards → Quiz → Test → Practice Game → Analytics → Badges → Scenarios → Import/Export → Add → Inbox

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+K` (or `Cmd+K`) | Jump to Add (capture) tab |
| `?` | Open/reopen tutorial |
| `1-9` | Switch to tab N |

### Lazy Loading
Analytics, Badges, Scenarios, and Import/Export are code-split with `React.lazy` + `Suspense` — they're not in the initial bundle.

---

## CLI Command Tracker

All commands run from the repo root using the backend venv Python:

```bash
backend\.venv\Scripts\python.exe -m cli init        # Initialize DB
backend\.venv\Scripts\python.exe -m cli stats        # Show stats
backend\.venv\Scripts\python.exe -m cli capture "ls -la" --exit-code 0   # Record a command
backend\.venv\Scripts\python.exe -m cli pending        # List commands not in deck
backend\.venv\Scripts\python.exe -m cli failed         # List failed commands needing fixes
backend\.venv\Scripts\python.exe -m cli add 1 --depth medium   # Add command #1 as study card
backend\.venv\Scripts\python.exe -m cli cards            # List study cards
backend\.venv\Scripts\python.exe -m cli research ls medium   # Man-page research for 'ls'
backend\.venv\Scripts\python.exe -m cli study quiz           # Quiz session
backend\.venv\Scripts\python.exe -m cli study test           # Timed recall test
backend\.venv\Scripts\python.exe -m cli study game           # Typing game
```

### Subcommands
| Command | Description |
|---------|-------------|
| `init` | Initialize the local SQLite database |
| `stats` | Show command capture stats |
| `recent` | Show recent commands (--limit N) |
| `pending` | List commands not yet in study deck |
| `failed` | List failed commands not yet fixed |
| `capture` | Record a command line (raw, --exit-code, --source, --stderr) |
| `capture-buffer` | Bulk-insert from shell buffer (internal, used by shell integration) |
| `add <id>` | Add a captured command to the study deck (--depth shallow\|medium\|deep) |
| `research <cmd>` | Research a command from man pages (--depth shallow\|medium\|deep) |
| `study <mode>` | Interactive study (flashcard\|quiz\|test\|game) |
| `cards` | List study cards (--depth, --tag, --due) |
| `fix <id>` | Analyze and fix a failed command |

---

## Shell Integration (Buffered Auto-Capture)

Source `cli/shell_integration.sh` in your `.bashrc` or `.zshrc`.

**Resource strategy**: Instead of spawning Python on every command (expensive), each command is appended to a buffer file using pure shell. A flusher drains the buffer into SQLite in batches (every 60s or 200 lines).

**On command failure**: You're prompted to (1) add to study deck, (2) analyze & fix the error, or (3) skip. No Python spawns unless you choose option 1 or 2.

```bash
# Manual flush
ctf_flashcards_flush
```

---

## Learning & Teaching Features

### Tutorial (5 steps)
1. Welcome — overview of the app
2. Capture a command — verified by checking `cc/stats` total > 0
3. Add to study deck — verified by checking due cards > 0
4. Review like flashcards — user self-confirms
5. Quiz yourself — user self-confirms
6. Done — points to Analytics and Badges

### Badges (8 total)
| Badge | Criterion |
|-------|-----------|
| First Steps | Capture 1 command |
| Command Collector | Capture 25 commands |
| Command Master | Capture 100 commands |
| 3-Day Streak | Review 3 days in a row |
| Week Warrior | Review 7 days in a row |
| Card Master | Master 10 cards (reps >= 3) |
| Perfect Score | Score 100% on a session |
| Scenario Solver | Complete a command chaining scenario |

### Scenarios
Multi-step terminal challenges. Each has a title, description, objective, setup commands, expected patterns (matched by substring), hints, and difficulty. Attempts track commands run and completion status.

---

## Accessibility & Ease of Use

- **Focus indicators**: `*:focus-visible` shows a 2px accent outline for keyboard navigation
- **Tooltips**: `data-tip` attribute on any element shows a tooltip on hover
- **Empty states**: Clear icon + heading + call-to-action on empty decks/lists
- **Responsive nav**: Tab bar scrolls horizontally on mobile; depth toggle stacks
- **Mobile layout**: Full-width inputs, stacked tutorial buttons
- **Form polish**: Full-width inputs with focus states, disabled button states
- **Card polish**: Consistent borders, radii, heading colors, muted text

---

## Resource Efficiency

| Area | Technique | Impact |
|------|-----------|--------|
| Shell capture | Buffer file + batch flush | No Python spawn per command |
| Frontend bundling | `React.lazy` + `Suspense` code splitting | Analytics/Badges/Scenarios/ImportExport are separate chunks (~1-3KB gz each) |
| Backend DB | SQLite WAL mode | Concurrent reads/writes, lower I/O |
| CLI flush | Bulk insert in one transaction | Fewer DB transactions |

---

## Deployment

### GitHub Pages (docs site)
The `docs/` folder deploys via GitHub Actions on pushes to `main`. See `.github/workflows/pages.yml`. Live at `https://pymite6941.github.io/ctf-flashcards/`.

### Production Backend (Cloudflare Worker + D1)
Source in `worker/`. Behavior-identical twin of `backend/`. Deploy with `wrangler deploy`.

### Frontend (Cloudflare Pages)
Build `web/` with `.env.production`. Deploy via `wrangler pages deploy`.

---

## Verification

Run all checks before claiming the work is done:

```bash
# 1. Backend tests
cd backend
backend\.venv\Scripts\python.exe test_api.py
# Criterion: ALL 57 CHECKS PASSED, exit 0

# 2. AI route tests
backend\.venv\Scripts\python.exe test_ai_routes.py
# Criterion: ALL 9 AI ROUTE CHECKS PASSED, exit 0

# 3. Frontend build
cd ../web
npm run build
# Criterion: exits 0, emits dist/ assets

# 4. CLI init + stats
backend\.venv\Scripts\python.exe -m cli init
backend\.venv\Scripts\python.exe -m cli stats
# Criterion: exits 0

# 5. Git tree
git status --short
# Criterion: clean, or only intended changes
```

### Pitfalls
- **System `python3` on Windows** is a Microsoft Store stub missing project packages. Always invoke `backend/.venv/Scripts/python.exe` directly.
- **pytest may be absent** from the venv. Test files have `__main__` runners — run `python test_api.py` directly.
- **Inline `python -c` probes** can be blocked on Windows. Write a probe file instead.
- **FastAPI startup event** (`db.init_db()`) only fires when `TestClient` is used as a context manager.
- **git push over HTTPS** may fail (no anonymous write access / network timeout). Use `git config credential.helper "!gh auth git-credential"`.
- **Ratings are ints 1=Again 2=Hard 3=Good 4=Easy** everywhere — keep API, DB, UI, and FSRS aligned.
- **Monitor console output must stay ASCII** (Windows cp1252 crashes on unicode).

---

## What's NOT Included (Centralized Teaching Removed)

Study groups/classes were removed per project direction. There is no centralized teaching or multi-user classroom feature. All features work for individual, offline use.

---

## License

MIT License — see `LICENSE`.
