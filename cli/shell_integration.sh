#!/usr/bin/env bash
# CTF Flashcards shell integration — line-by-line terminal monitor.
#
# Source this in your ~/.bashrc or ~/.zshrc to auto-capture EVERY command
# you type or paste (no whitelist, no limits):
#
#   echo 'source /path/to/ctf-flashcards/cli/shell_integration.sh' >> ~/.bashrc
#
# After each command:
#   - The command line + exit code are logged to the local SQLite DB.
#   - If it failed (exit != 0 or command not found), you're prompted to:
#       * add it to your study deck (flashcard/quiz/test/game), or
#       * analyze and fix the error (local man-page research, no AI required).
#
# Works with any shell tool — bash, zsh, git, nmap, Claude Code, Qwen Code,
# Hydra, custom scripts, etc. Fully offline, no server required.

# Avoid double-sourcing
[[ -n "${CTF_FLASHCARDS_LOADED:-}" ]] && return 0
CTF_FLASHCARDS_LOADED=1

# Resolve the CLI directory relative to this script.
CTF_CLI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")" && pwd)"

# Find a python interpreter (prefer the project venv if present).
if [[ -x "${CTF_CLI_DIR}/../backend/.venv/Scripts/python.exe" ]]; then
  CTF_PYTHON="${CTF_CLI_DIR}/../backend/.venv/Scripts/python.exe"
elif [[ -x "${CTF_CLI_DIR}/../backend/.venv/bin/python" ]]; then
  CTF_PYTHON="${CTF_CLI_DIR}/../backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  CTF_PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  CTF_PYTHON="python"
else
  CTF_PYTHON=""
fi

# ---------------------------------------------------------------------------
# Capture + error handling — shared by bash and zsh
# ---------------------------------------------------------------------------

ctf_flashcards_handle() {
  local status=$?
  local last="${CTF_LAST_CMD:-${BASH_COMMAND:-}}"

  # Skip empty, our own hooks, history, and the capture call itself.
  [[ -z "$last" ]] && return 0
  case "$last" in
    ctf_flashcards_*|history*|fc*) return 0 ;;
  esac

  # 1. Line-by-line log: capture EVERY command (success or failure).
  "${CTF_PYTHON}" -m cli capture "$last" --exit-code "$status" --source shell 2>/dev/null || true

  # 2. If it failed, prompt the user.
  if [[ $status -ne 0 ]]; then
    echo ""
    echo "[ctf-flashcards] Command failed (exit $status): $last"
    echo "  1) Add to study deck"
    echo "  2) Analyze & fix the error"
    echo "  3) Skip"
    read -r -p "Choose [1/2/3]: " choice
    case "$choice" in
      1)
        # Add to study deck at medium depth (user can adjust depth later).
        "${CTF_PYTHON}" -m cli add --id -1 --depth medium 2>/dev/null || true
        ;;
      2)
        "${CTF_PYTHON}" -m cli failed 2>/dev/null || true
        echo ""
        echo "Run:  python -m cli fix <id>   to analyze and fix a failed command."
        ;;
      3)
        : # skip
        ;;
    esac
  fi
}

# ---------------------------------------------------------------------------
# Bash hook
# ---------------------------------------------------------------------------
if [[ -n "${BASH_VERSION:-}" ]]; then
  ctf_flashcards_precmd() {
    ctf_flashcards_handle
  }
  if [[ -z "${PROMPT_COMMAND:-}" ]]; then
    PROMPT_COMMAND="ctf_flashcards_precmd"
  else
    PROMPT_COMMAND="ctf_flashcards_precmd; ${PROMPT_COMMAND}"
  fi
fi

# ---------------------------------------------------------------------------
# Zsh hook
# ---------------------------------------------------------------------------
if [[ -n "${ZSH_VERSION:-}" ]]; then
  ctf_flashcards_preexec() {
    CTF_LAST_CMD="$1"
  }
  ctf_flashcards_precmd_zsh() {
    ctf_flashcards_handle
  }
  autoload -U add-zsh-hook
  add-zsh-hook preexec ctf_flashcards_preexec
  add-zsh-hook precmd ctf_flashcards_precmd_zsh
fi
