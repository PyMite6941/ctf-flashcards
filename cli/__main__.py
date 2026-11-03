"""CLI entry point: `python -m cli <command>`."""

from __future__ import annotations

import argparse
import sys

from .tracker import (
    init_db, stats, list_unadded, list_commands, list_failed_unfixed,
    get_error_text, capture_command, DB_PATH,
)
from .notify import check_and_notify, pending_count
from .researcher import generate_card
from .study import add_card_from_command, list_cards


def _cmd_capture(args: argparse.Namespace) -> int:
    init_db()
    rec = capture_command(
        args.raw,
        exit_code=args.exit_code,
        source=args.source,
        stderr=args.stderr,
    )
    print(f"Captured [{rec.id}] {rec.raw} (ok={rec.ok})")
    if not rec.ok:
        print("  -> command failed or not found.")
        print("  -> Add to study deck:  python -m cli add <id> [--depth shallow|medium|deep]")
        print("  -> Fix the error:      python -m cli fix <id>")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    init_db()
    import json
    print(json.dumps(stats(), indent=2))
    return 0


def _cmd_pending(args: argparse.Namespace) -> int:
    init_db()
    items = list_unadded(limit=args.limit)
    if not items:
        print("No pending commands.")
        return 0
    for c in items:
        flag = "OK" if c.ok else "FAILED"
        print(f"[{c.id}] [{flag}] {c.raw}  (depth={c.depth})")
    print(f"\n{len(items)} pending. Add one:  python -m cli add <id> [--depth shallow|medium|deep]")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    init_db()
    from .study import add_card_from_command
    c = add_card_from_command(args.id, args.depth)
    if not c:
        print("Command not found.")
        return 1
    print(f"Added card #{c.id}: {c.front}")
    print(f"  {c.back[:200]}")
    return 0


def _cmd_research(args: argparse.Namespace) -> int:
    card = generate_card(args.cmd, args.depth)
    import json
    print(json.dumps(card, indent=2))
    return 0


def _cmd_study(args: argparse.Namespace) -> int:
    init_db()
    mode = args.mode
    depth = args.depth
    cards = list_cards(depth=depth, due_only=True)[: args.limit]
    if not cards:
        print("No cards due for review. Add some with:  python -m cli pending")
        return 0

    print(f"\n=== {mode.upper()} study session ({len(cards)} cards) ===\n")
    score = 0
    session_id = None
    try:
        from .study import start_session, end_session, update_rep
        session_id = start_session(mode)
    except Exception:
        session_id = None

    for i, c in enumerate(cards, 1):
        print(f"--- Card {i}/{len(cards)} (depth={c.depth}) ---")
        print(f"Q: {c.front}")
        if mode == "flashcard":
            input("\nPress Enter to reveal answer...")
            print(f"A: {c.back}")
            correct = input("Correct? [y/n] ").strip().lower() in ("y", "yes")
        elif mode == "quiz":
            print(f"\nHint: command = {c.command}")
            ans = input("Your answer: ").strip()
            correct = ans.lower() in c.back.lower()[:40] or c.command.lower() in ans.lower()
            print(f"{'Correct!' if correct else 'Incorrect.'}\nAnswer: {c.back}")
        elif mode == "test":
            print(f"\nCommand context: {c.command}")
            ans = input("Type the command/answer: ").strip()
            correct = ans.lower() == c.command.lower()
            print(f"{'Correct!' if correct else 'Incorrect.'}\nExpected: {c.command}")
        elif mode == "game":
            print(f"\nType this command as fast as you can: {c.command}")
            start = __import__("time").time()
            ans = input("> ").strip()
            elapsed = __import__("time").time() - start
            correct = ans == c.command
            print(f"{'Correct!' if correct else 'Incorrect.'} ({elapsed:.1f}s)")
            if correct:
                score += 1
        else:
            correct = True

        if session_id is not None:
            try:
                from .study import update_rep
                update_rep(c.id, correct, 0, session_id)
            except Exception:
                pass
        if correct:
            score += 1
        print()

    if session_id is not None:
        try:
            from .study import end_session
            end_session(session_id, score, len(cards))
        except Exception:
            pass
    print(f"Session complete: {score}/{len(cards)} correct.")
    return 0


def _cmd_cards(args: argparse.Namespace) -> int:
    init_db()
    cards = list_cards(depth=args.depth, tag=args.tag, due_only=args.due)
    if not cards:
        print("No study cards.")
        return 0
    for c in cards:
        print(f"[{c.id}][{c.depth}] {c.front}  (due={c.due[:10]}, reps={c.reps})")
    return 0


def _cmd_failed(args: argparse.Namespace) -> int:
    init_db()
    items = list_failed_unfixed(limit=args.limit)
    if not items:
        print("No failed commands awaiting a fix.")
        return 0
    for c in items:
        err = get_error_text(c.id)
        print(f"[{c.id}] [FAIL] {c.raw}")
        if err:
            print(f"      error: {err[:200]}")
    print(f"\n{len(items)} failed command(s). Fix one:  python -m cli fix <id>")
    return 0


def _cmd_fix(args: argparse.Namespace) -> int:
    init_db()
    from .error_analyzer import analyze_and_fix
    analyze_and_fix(args.id)
    return 0


def _cmd_capture_buffer(args: argparse.Namespace) -> int:
    """Bulk-insert commands from a buffer file (used by shell flush)."""
    import os
    init_db()
    buf_path = os.environ.get("CTF_FLASH_FILE", "")
    if not buf_path or not os.path.exists(buf_path):
        return 0
    count = 0
    with open(buf_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            exit_code, raw, _ts = parts[0], parts[1], parts[2]
            try:
                ec = int(exit_code)
            except ValueError:
                ec = 0
            capture_command(raw, exit_code=ec, source="shell")
            count += 1
    try:
        os.unlink(buf_path)
    except OSError:
        pass
    if count:
        print(f"Flushed {count} commands from buffer.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ctf", description="CTF Flashcards CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="initialize the local database")
    sub.add_parser("stats", help="show command stats")

    p_cap = sub.add_parser("capture", help="record a command")
    p_cap.add_argument("raw")
    p_cap.add_argument("--exit-code", type=int, default=0)
    p_cap.add_argument("--source", default="shell")
    p_cap.add_argument("--stderr", default="", help="stderr / error output if the command failed")

    sub.add_parser("pending", help="list commands not yet in study deck").add_argument(
        "--limit", type=int, default=50)

    p_failed = sub.add_parser("failed", help="list failed commands not yet fixed")
    p_failed.add_argument("--limit", type=int, default=50)

    p_fix = sub.add_parser("fix", help="analyze and fix a failed command")
    p_fix.add_argument("id", type=int)

    p_capture_buffer = sub.add_parser(
        "capture-buffer", help="bulk-insert from shell buffer (internal)"
    )

    p_add = sub.add_parser("add", help="add a captured command to study deck")
    p_add.add_argument("id", type=int)
    p_add.add_argument("--depth", choices=("shallow", "medium", "deep"), default="medium")

    p_res = sub.add_parser("research", help="research a command from man pages")
    p_res.add_argument("cmd")
    p_res.add_argument("--depth", choices=("shallow", "medium", "deep"), default="medium")

    p_study = sub.add_parser("study", help="interactive study session")
    p_study.add_argument("mode", choices=("flashcard", "quiz", "test", "game"), default="flashcard", nargs="?")
    p_study.add_argument("--depth", choices=("shallow", "medium", "deep"))
    p_study.add_argument("--limit", type=int, default=20)

    p_cards = sub.add_parser("cards", help="list study cards")
    p_cards.add_argument("--depth", choices=("shallow", "medium", "deep"))
    p_cards.add_argument("--tag")
    p_cards.add_argument("--due", action="store_true")

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 1

    handlers = {
        "init": _cmd_init,
        "stats": _cmd_stats,
        "pending": _cmd_pending,
        "capture": _cmd_capture,
        "capture-buffer": _cmd_capture_buffer,
        "failed": _cmd_failed,
        "fix": _cmd_fix,
        "add": _cmd_add,
        "research": _cmd_research,
        "study": _cmd_study,
        "cards": _cmd_cards,
    }
    return handlers[args.cmd](args)


def _cmd_init(args: argparse.Namespace) -> int:
    import os
    init_db()
    print(f"Database initialized at {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
