#!/usr/bin/env bash
# Minimal, cost-capped, tool-less second-model audit harness.
#
# Runs the Claude Code CLI headlessly with: no tools, no session persistence,
# JSON output, a hard USD budget cap, from a fresh temp directory (never your repo).
# review.py calls this by default; set AUDIT_SCRIPT to swap in your own harness.
#
# Usage:
#   audit.sh [--model MODEL] [--budget USD] --prompt-file FILE
#   audit.sh [--model MODEL] [--budget USD] PROMPT...
#
# Auth (headless `claude -p` does not share an interactive login):
#   - Export CLAUDE_CODE_OAUTH_TOKEN (create one with `claude setup-token`), or
#   - Export ANTHROPIC_API_KEY and set AUDIT_MODE=api-key-bare.
# Tokens are read from the environment only; this script never stores or prints them.
set -euo pipefail

model="${AUDIT_MODEL:-sonnet}"
mode="${AUDIT_MODE:-local-auth}"
budget="0.25"
prompt=""
prompt_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)       model="${2:?missing value for --model}"; shift 2 ;;
    --budget)      budget="${2:?missing value for --budget}"; shift 2 ;;
    --prompt-file) prompt_file="${2:?missing value for --prompt-file}"; shift 2 ;;
    -h|--help)     sed -n '2,17p' "$0"; exit 0 ;;
    --)            shift; prompt="${*:-}"; break ;;
    -*)            echo "Unknown option: $1" >&2; exit 2 ;;
    *)             prompt="${prompt}${prompt:+ }$1"; shift ;;
  esac
done

if [[ -n "$prompt_file" ]]; then
  [[ -f "$prompt_file" ]] || { echo "Prompt file not found: $prompt_file" >&2; exit 2; }
  prompt="$(<"$prompt_file")"
fi
[[ -n "${prompt// }" ]] || { echo "Missing audit prompt." >&2; exit 2; }
command -v claude >/dev/null 2>&1 || { echo "Claude Code CLI (claude) not found on PATH." >&2; exit 127; }

workdir="$(mktemp -d "${TMPDIR:-/tmp}/adversarial-review.XXXXXX")"
trap 'rm -rf "$workdir"' EXIT

args=(-p "$prompt" --model "$model" --tools "" --no-session-persistence
      --output-format json --max-budget-usd "$budget")

case "$mode" in
  local-auth)
    [[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]] || {
      echo "CLAUDE_CODE_OAUTH_TOKEN is not set (create one with: claude setup-token)," >&2
      echo "or use AUDIT_MODE=api-key-bare with ANTHROPIC_API_KEY." >&2
      exit 1
    }
    (cd "$workdir" && claude --setting-sources local "${args[@]}") ;;
  api-key-bare)
    [[ -n "${ANTHROPIC_API_KEY:-}" ]] || { echo "ANTHROPIC_API_KEY is not set." >&2; exit 1; }
    (cd "$workdir" && claude --bare "${args[@]}") ;;
  *) echo "Unknown AUDIT_MODE: $mode (use local-auth or api-key-bare)" >&2; exit 2 ;;
esac
