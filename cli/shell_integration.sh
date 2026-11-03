#!/usr/bin/env bash
# CTF Flashcards shell integration — resource-efficient line-by-line terminal monitor.
#
# Resource strategy: instead of spawning Python on every command (expensive),
# we append each command to a lightweight buffer file (shell-native, near-zero
# cost). A separate flusher drains the buffer into SQLite in batches.
#
# Source this in your ~/.bashrc or ~/.zshrc:
#   echo 'source /path/to/ctf-flashcards/cli/shell_integration.sh' >> ~/.bashrc
#
# Works with bash and zsh. Fully offline, no server required.

# Avoid double-sourcing
[[ -n "${CTF_FLASHCARDS_LOADED:-}" ]] && return 0
CTF_FLASHCARDS_LOADED=1

# Resolve the CLI directory relative to this script.
CTF_CLI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")" && pwd)"

# Buffer file — shell appends here cheaply; the flusher drains it.
CTF_BUFFER_DIR="${CTF_FLASHCARDS_BUFFER_DIR:-${XDG_RUNTIME_DIR:-/tmp}}"
CTF_BUFFER_FILE="$CTF_BUFFER_DIR/ctf_flashcards_buffer_$$.txt"
CTF_LAST_FLUSH=0
CTF_FLUSH_INTERVAL=60   # seconds between automatic flushes
CTF_MAX_BUFFER_LINES=200 # flush sooner if buffer gets large

# Find a python interpreter (only used by the flusher, not per-command).
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

# Ensure buffer file exists.
: > "$CTF_BUFFER_FILE"

# ---------------------------------------------------------------------------
# Buffer append — runs on every command, but is pure shell (no Python spawn).
# ---------------------------------------------------------------------------
ctf_flashcards_append() {
  local status=$?
  local last="${CTF_LAST_CMD:-${BASH_COMMAND:-}}"
  [[ -z "$last" ]] && return 0
  case "$last" in
    ctf_flashcards_*|history*|fc*) return 0 ;;
  esac
  # Append: exit_code<TAB>command<TAB>timestamp
  printf '%s\t%s\t%s\n' "$status" "$last" "$(date +%s)" >> "$CTF_BUFFER_FILE"
}

# ---------------------------------------------------------------------------
# Flush — drains buffer into SQLite in one Python spawn (batched, efficient).
# Call manually with: ctf_flashcards_flush
# ---------------------------------------------------------------------------
ctf_flashcards_flush() {
  [[ ! -s "$CTF_BUFFER_FILE" ]] && return 0
  [[ -z "$CTF_PYTHON" ]] && return 0
  local tmp
  tmp="$(mktemp)"
  cp "$CTF_BUFFER_FILE" "$tmp"
  : > "$CTF_BUFFER_FILE"
  # Pass the buffer file path via env; the Python side reads and bulk-inserts.
  CTF_FLUSH_FILE="$tmp" "${CTF_PYTHON}" -m cli capture-buffer 2>/dev/null || true
  rm -f "$tmp"
  CTF_LAST_FLUSH=$(date +%s)
}

# Periodic auto-flush: runs before each prompt, cheap time check only.
ctf_flashcards_maybe_flush() {
  local now
  now=$(date +%s)
  local line_count
  line_count=$(wc -l < "$CTF_BUFFER_FILE" 2>/dev/null || echo 0)
  if (( now - CTF_LAST_FLUSH >= CTF_FLUSH_INTERVAL )) || (( line_count >= CTF_MAX_BUFFER_LINES )); then
    ctf_flashcards_flush
  fi
}

# ---------------------------------------------------------------------------
# Error prompt — only when a command just failed. Still cheap (no Python
# spawn unless the user chooses option 1 or 2).
# ---------------------------------------------------------------------------
ctf_flashcards_prompt_on_error() {
  local status=$?
  local last="${CTF_LAST_CMD:-${BASH_COMMAND:-}}"
  [[ -z "$last" ]] && return 0
  case "$last" in
    ctf_flashcards_*|history*|fc*) return 0 ;;
  esac
  (( status == 0 )) && return 0
  echo ""
  echo "[ctf-flashcards] Command failed (exit $status): $last"
  echo "  1) Add to study deck   2) Analyze & fix   3) Skip"
  read -r -p "Choose [1/2/3]: " choice
  case "$choice" in
    1)
      "${CTF_PYTHON}" -m cli capture "$last" --exit-code "$status" --source shell --depth medium 2>/dev/null || true
      ;;
    2)
      "${CTF_PYTHON}" -m cli failed 2>/dev/null || true
      echo ""
      echo "Run:  python -m cli fix <id>   to analyze and fix a failed command."
      ;;
    *) : ;;
  esac
}

# ---------------------------------------------------------------------------
# Bash hook
# ---------------------------------------------------------------------------
if [[ -n "${BASH_VERSION:-}" ]]; then
  ctf_flashcards_precmd() {
    ctf_flashcards_append
    ctf_flashcards_maybe_flush
    ctf_flashcards_prompt_on_error
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
  ctf_flashcards_preexec() { CTF_LAST_CMD="$1"; }
  ctf_flashcards_precmd_zsh() {
    ctf_flashcards_append
    ctf_flashcards_maybe_flush
    ctf_flashcards_prompt_on_error
  }
  autoload -U add-zsh-hook
  add-zsh-hook preexec ctf_flashcards_preexec
  add-zsh-hook precmd ctf_flashcards_precmd_zsh
fi
