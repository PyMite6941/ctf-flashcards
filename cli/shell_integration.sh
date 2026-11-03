#!/usr/bin/env bash
# CTF Flashcards shell integration.
# Source this in your ~/.bashrc or ~/.zshrc to auto-capture commands:
#
#   echo 'source /path/to/ctf-flashcards/cli/shell_integration.sh' >> ~/.bashrc
#
# After each command, if it failed or wasn't found, you'll be asked whether
# to add it to your study deck.

# Avoid double-sourcing
[[ -n "${CTF_FLASHCARDS_LOADED:-}" ]] && return 0
CTF_FLASHCARDS_LOADED=1

# Resolve the CLI directory relative to this script.
CTF_CLI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

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

# Only hook interactive shells.
ctf_flashcards_precmd() {
  local status=$?
  # Bash provides $BASH_COMMAND for the last command executed.
  local last="${BASH_COMMAND:-}"
  # Skip empty, our own hooks, and history commands.
  [[ -z "$last" ]] && return 0
  case "$last" in
    ctf_flashcards_precmd*|ctf_flashcards_prompt*|history*|fc*) return 0 ;;
  esac

  if [[ -n "$CTF_PYTHON" && -f "${CTF_CLI_DIR}/__main__.py" ]]; then
    # Run non-interactively: capture the command, then prompt if it failed.
    "${CTF_PYTHON}" -m cli capture "$last" --exit-code "$status" --source shell 2>/dev/null || true
    if [[ $status -ne 0 ]]; then
      echo ""
      echo "[ctf-flashcards] Last command failed: $last"
      read -r -p "Add to study deck? [y/N] " choice
      if [[ "$choice" =~ ^[Yy]$ ]]; then
        "${CTF_PYTHON}" -m cli add --id -1 --depth medium 2>/dev/null || true
      fi
    fi
  fi
}

# Bash: use PROMPT_COMMAND (runs before each prompt).
if [[ -n "${BASH_VERSION:-}" ]]; then
  if [[ -z "${PROMPT_COMMAND:-}" ]]; then
    PROMPT_COMMAND="ctf_flashcards_precmd"
  else
    PROMPT_COMMAND="ctf_flashcards_precmd; ${PROMPT_COMMAND}"
  fi
fi

# Zsh: use preexec/precmd hooks.
if [[ -n "${ZSH_VERSION:-}" ]]; then
  ctf_flashcards_preexec() {
    # capture command before it runs; we report outcome in precmd
    CTF_LAST_CMD="$1"
  }
  ctf_flashcards_precmd_zsh() {
    local status=$?
    local last="${CTF_LAST_CMD:-}"
    [[ -z "$last" ]] && return 0
    if [[ -n "$CTF_PYTHON" && -f "${CTF_CLI_DIR}/__main__.py" ]]; then
      "${CTF_PYTHON}" -m cli capture "$last" --exit-code "$status" --source shell 2>/dev/null || true
      if [[ $status -ne 0 ]]; then
        echo ""
        echo "[ctf-flashcards] Last command failed: $last"
        read -r -p "Add to study deck? [y/N] " choice
        if [[ "$choice" =~ ^[Yy]$ ]]; then
          "${CTF_PYTHON}" -m cli add --id -1 --depth medium 2>/dev/null || true
        fi
      fi
    fi
  }
  autoload -U add-zsh-hook
  add-zsh-hook preexec ctf_flashcards_preexec
  add-zsh-hook precmd ctf_flashcards_precmd_zsh
fi
