"""Error analyzer and fix recommender.

When a captured command fails, this module:
  1. Shows the error text
  2. Researches the command locally (man page, --help, which)
  3. Suggests likely fixes based on common error patterns
  4. Lets the user apply a fix and re-run

Fully offline — uses only locally-installed man pages and --help output.
No AI required (the optional AI connector can be added later).
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from typing import Optional

try:
    from .tracker import (
        capture_command, get_command, get_error_text, mark_fixed,
        list_failed_unfixed,
    )
    from .researcher import research
except ImportError:  # allow running as a script
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from tracker import (  # type: ignore
        capture_command, get_command, get_error_text, mark_fixed,
        list_failed_unfixed,
    )
    from researcher import research  # type: ignore


def _run(cmd: list[str], timeout: int = 8) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.stdout + res.stderr
    except Exception:
        return ""


def analyze_error(command_id: int) -> dict:
    """Analyze a failed command and return a fix recommendation."""
    cmd = get_command(command_id)
    if not cmd:
        return {"error": f"Command #{command_id} not found."}

    error_text = get_error_text(command_id) or ""
    info = research(cmd.argv0)

    diagnosis = _diagnose(cmd.argv0, cmd.exit_code, error_text, info)
    fix = _suggest_fix(cmd.argv0, cmd.exit_code, error_text, info, diagnosis)

    return {
        "command_id": command_id,
        "raw": cmd.raw,
        "argv0": cmd.argv0,
        "exit_code": cmd.exit_code,
        "found": cmd.found,
        "error_text": error_text,
        "summary": info.summary,
        "synopsis": info.synopsis,
        "diagnosis": diagnosis,
        "fix": fix,
    }


def _diagnose(argv0: str, exit_code: int, error_text: str, info) -> str:
    """Produce a human-readable diagnosis of why the command failed."""
    err_lower = error_text.lower()

    if not argv0:
        return "Empty command — nothing to run."

    if not info or info.summary.startswith(argv0 + " — command"):
        if exit_code == 127:
            return (
                f"'{argv0}' is not installed or not on your PATH. "
                f"Install it (e.g. via your package manager) or use an absolute path."
            )
        return f"'{argv0}' could not be located on the system."

    if exit_code == 127:
        return f"'{argv0}' not found (exit 127). Check spelling or install it."

    if exit_code == 126:
        return f"'{argv0}' found but not executable (exit 126). Try: chmod +x <path>"

    if "permission denied" in err_lower:
        return "Permission denied. Try running with sudo, or check file ownership/permissions."

    if "command not found" in err_lower:
        return f"'{argv0}' is not installed or not on PATH."

    if "no such file or directory" in err_lower:
        return "A file or directory referenced in the command does not exist. Check the path."

    if "syntax error" in err_lower:
        return "Syntax error in the command. Check quoting, brackets, and flag order."

    if exit_code != 0:
        return f"Command exited with code {exit_code} (non-zero = failure)."

    return "Command completed without a non-zero exit code, but was flagged as failed."


def _suggest_fix(argv0, exit_code, error_text, info, diagnosis) -> list[dict]:
    """Return a list of suggested fixes, each with a description and a command to try."""
    fixes: list[dict] = []
    err_lower = error_text.lower()

    if exit_code == 127:
        fixes.append({
            "description": f"Install '{argv0}' via your system package manager",
            "command": f"# Example: sudo apt install {argv0}   (Debian/Ubuntu)\n# Example: sudo dnf install {argv0}   (Fedora)\n# Example: brew install {argv0}        (macOS)",
            "safe": True,
        })

    if "permission denied" in err_lower:
        fixes.append({
            "description": "Run with elevated privileges",
            "command": f"sudo {argv0}",
            "safe": False,
        })
        fixes.append({
            "description": "Make the script/executable executable",
            "command": f"chmod +x <path-to-{argv0}>",
            "safe": True,
        })

    if "no such file or directory" in err_lower:
        fixes.append({
            "description": "Check the file path exists before running",
            "command": f"ls -la <path-in-command>",
            "safe": True,
        })

    if info.synopsis:
        fixes.append({
            "description": f"Review correct usage for '{argv0}'",
            "command": f"{argv0} --help   or   man {argv0}",
            "safe": True,
        })

    # Always offer to research deeper
    fixes.append({
        "description": f"Read the full man page for '{argv0}'",
        "command": f"man {argv0}",
        "safe": True,
    })

    return fixes


def print_analysis(result: dict) -> None:
    """Pretty-print the analysis to the terminal."""
    print("\n" + "=" * 60)
    print(f"CTF Flashcards — Error Analysis for command #{result['command_id']}")
    print("=" * 60)
    print(f"Command: {result['raw']}")
    print(f"Exit code: {result['exit_code']}  |  Found on system: {result['found']}")
    if result["error_text"]:
        print(f"\nError output:\n  {result['error_text'][:500]}")
    print(f"\nDiagnosis: {result['diagnosis']}")
    print(f"\nCommand summary: {result['summary']}")
    if result["synopsis"]:
        print(f"Usage: {result['synopsis']}")

    print("\nSuggested fixes:")
    for i, f in enumerate(result["fix"], 1):
        tag = " [safe]" if f["safe"] else " [careful: may run sudo]"
        print(f"  {i}. {f['description']}{tag}")
        print(f"     $ {f['command']}")
    print("=" * 60 + "\n")


def apply_fix(command_id: int, fix_index: int) -> bool:
    """Apply a suggested fix by running the command. Returns True if successful."""
    result = analyze_error(command_id)
    if fix_index < 1 or fix_index > len(result["fix"]):
        print("Invalid fix number.")
        return False

    fix = result["fix"][fix_index - 1]
    print(f"\nApplying fix #{fix_index}: {fix['description']}")
    if not fix["safe"]:
        confirm = input("This fix may run with elevated privileges. Continue? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return False

    # Extract the actual command to run (strip comments)
    cmd_line = fix["command"].split("\n")[0].strip()
    if cmd_line.startswith("#") or not cmd_line:
        print("No executable command provided for this fix.")
        return False

    try:
        tokens = shlex.split(cmd_line)
        res = subprocess.run(tokens, capture_output=True, text=True, timeout=30)
        success = res.returncode == 0
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)

        # Re-capture the original command to see if it now works
        orig = get_command(command_id)
        if orig:
            rec = capture_command(orig.raw, exit_code=0 if success else res.returncode,
                                  source="fix-retry")
            if success:
                mark_fixed(command_id, success=True, notes=f"Applied fix #{fix_index}")
                print("\n✓ Fix applied successfully. The original command should now work.")
            else:
                mark_fixed(command_id, success=False, notes=f"Fix #{fix_index} did not resolve it")
                print("\n✗ Fix did not resolve the issue. Try another approach.")
        return success
    except Exception as e:
        print(f"Error applying fix: {e}")
        return False


def analyze_and_fix(command_id: int) -> None:
    """Interactive entry point: analyze a failed command and offer fixes."""
    result = analyze_error(command_id)
    if "error" in result:
        print(result["error"])
        return

    print_analysis(result)

    if not result["fix"]:
        print("No automatic fixes available. Try researching the command manually.")
        return

    choice = input("Apply a fix? Enter fix number, or 'n' to skip: ").strip().lower()
    if choice in ("n", "no", ""):
        print("Skipped.")
        return
    try:
        idx = int(choice)
        apply_fix(command_id, idx)
    except ValueError:
        print("Invalid choice.")


def review_all_failed() -> None:
    """List all failed-unfixed commands and offer to fix each."""
    items = list_failed_unfixed()
    if not items:
        print("No failed commands awaiting a fix.")
        return

    for c in items:
        err = get_error_text(c.id) or ""
        print(f"\n[{c.id}] [FAIL] {c.raw}")
        if err:
            print(f"      error: {err[:200]}")

    choice = input("\nFix which command? Enter ID, or 'all', or 'n': ").strip().lower()
    if choice in ("n", "no", ""):
        print("Skipped.")
        return
    if choice == "all":
        for c in items:
            analyze_and_fix(c.id)
    else:
        try:
            analyze_and_fix(int(choice))
        except ValueError:
            print("Invalid choice.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CTF Error Analyzer")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("analyze", help="analyze a failed command")
    p.add_argument("id", type=int)
    sub.add_parser("review", help="review all failed commands")

    args = parser.parse_args()
    if args.cmd == "analyze":
        analyze_and_fix(args.id)
    elif args.cmd == "review":
        review_all_failed()
    else:
        parser.print_help()
