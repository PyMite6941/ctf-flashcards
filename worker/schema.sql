-- CTF Flashcards — D1 schema. Mirrors the SQLite backend (app/db.py).
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT PRIMARY KEY,
    front       TEXT NOT NULL,
    back        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'flashcard',
    deck        TEXT NOT NULL DEFAULT 'default',
    tags        TEXT NOT NULL DEFAULT '[]',
    fsrs        TEXT NOT NULL,
    due         TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id          TEXT PRIMARY KEY,
    card_id     TEXT NOT NULL,
    rating      INTEGER NOT NULL,
    reviewed_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inbox (
    id          TEXT PRIMARY KEY,
    front       TEXT NOT NULL,
    back        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'flashcard',
    source      TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS solves (
    puzzle_id   TEXT PRIMARY KEY,
    solved_at   REAL NOT NULL,
    points      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS daily_usage (
    day         TEXT NOT NULL,
    identity    TEXT NOT NULL,
    solves      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, identity)
);
CREATE INDEX IF NOT EXISTS idx_cards_due    ON cards(due);
CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox(status);
