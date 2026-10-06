---
name: adversarial-review
description: Use to get a fresh-eyes second-model code review on a diff or set of files — before shipping changes that touch 3+ files, new infrastructure, looping/recurring code, or refactors/migrations. Runs through a tool-less, no-session, budget-capped Claude CLI harness and returns a PASS/CONCERNS/FAIL JSON verdict.
---

# Adversarial review — cheap fresh eyes

A second model reviewing your work catches what you can't see in your own code. This wraps a small, cost-capped harness so review is one command, machine-readable, and bounded in spend.

## When to run
3+ files changed · new infrastructure · looping/recurring code · refactor or migration · anything load-bearing or end-to-end. Run it, fix the findings, then re-run your tests.

## Use
```bash
REVIEW="${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/scripts/review.py"

# Review the working-tree diff against HEAD
python3 "$REVIEW" --diff --budget 0.50

# Review specific files
python3 "$REVIEW" --files path/a.py path/b.ts
```

Returns a JSON verdict:
```json
{"verdict": "PASS|CONCERNS|FAIL",
 "findings": [{"severity": "high|medium|low", "where": "file:line", "issue": "...", "fix": "..."}],
 "summary": "one line"}
```
Exit 0 = PASS, 1 = CONCERNS/FAIL (act on findings), 2 = setup error.

## Setup
The bundled harness (`scripts/audit.sh`) shells out to the Claude Code CLI (`claude`) headlessly. Headless runs do not share an interactive login, so provide credentials in the environment:
- `export CLAUDE_CODE_OAUTH_TOKEN=...` (create one with `claude setup-token`), **or**
- `export ANTHROPIC_API_KEY=...` and `export AUDIT_MODE=api-key-bare`.

Optional: `AUDIT_MODEL` (default `sonnet`), `REVIEW_TIMEOUT` seconds (default 600).

## Pluggable harness
Set `AUDIT_SCRIPT=/path/to/your/harness.sh` to use a different reviewer (another model, another CLI, an internal gateway). It is run as `bash $AUDIT_SCRIPT --model M --budget USD --prompt-file FILE` and must print the reviewer's reply on stdout, either as plain text containing the JSON verdict or as a Claude `--output-format json` envelope.

## Wiring into a loop
Use it as a gate for high-stakes tasks, e.g. in a pre-push hook or CI step:
```bash
python3 "$REVIEW" --diff --budget 0.50   # non-zero exit blocks the push
```

## Failure modes
- **Exit 2 (setup error)** — harness missing, `claude` not on PATH, or no credentials. Do not fall back to self-review silently; report the block.
- **Spend or rate limit hit** — the cloud call can die mid-run, sometimes after partial output. Treat truncated or absent JSON as NO verdict. Re-run later; never parse a partial as PASS.
- **Budget cap exceeded** (`--max-budget-usd`) — the harness aborts. Raise `--budget` deliberately; don't loop-retry.
- **Malformed JSON from the reviewer** — exit code may still be 0 from the harness. Always validate the verdict parses before acting on it (`review.py` exits 1 and prints the raw reply when it can't).

## Safety
- The bundled harness is tool-less (`--tools ""`), uses `--no-session-persistence` and `--max-budget-usd`, and runs from a fresh temp directory. Only the diff/files you pass (truncated to 120k chars) are sent to the model, so don't review files containing secrets.
- No local model is loaded; the cost is capped API spend, not local RAM.
- Tests mock the harness, so `python3 skills/adversarial-review/tests/test_review.py` costs nothing.
