---
name: codegraph
description: Use to navigate an unfamiliar or large codebase fast and cheaply — look up where a symbol is defined, who references it, and who calls a function, instead of re-grepping the whole tree every session. RAM-light local index (regex into SQLite, grep for refs), zero dependencies, no resident model. Consult it BEFORE opening files to ground your context.
---

# codegraph — ground before you grep

Repeated full-text searches are the most common token/latency waste. codegraph preindexes symbol definitions into a per-project SQLite db so lookups are instant, and only the files it points at need opening.

## Use
```bash
CG="${CLAUDE_PLUGIN_ROOT}/skills/codegraph/scripts/codegraph.py"
python3 "$CG" index   --dir <repo>          # build/update (incremental by mtime)
python3 "$CG" def     <symbol> --dir <repo>  # where is it defined
python3 "$CG" refs    <symbol> --dir <repo>  # everywhere it's referenced (grep)
python3 "$CG" callers <fn>     --dir <repo>  # call sites of a function
python3 "$CG" stats   --dir <repo>          # symbol counts by kind
```
If the skill was copied into `~/.claude/skills/codegraph`, point `CG` at that copy instead.

## How it works (and its limits)
- **Definitions** via per-language regex (Python, TS/JS, Rust, Go, Swift, shell) stored in `<repo>/.codegraph/index.db`. Incremental: only changed files re-scan; deleted files are pruned. Add `.codegraph/` to your `.gitignore`.
- **References/callers** are computed on demand with `grep`.
- RAM-light, 100% local, no tree-sitter grammars, ctags, or resident model required.
- Regex definitions are roughly 90% precise for common forms; for exotic declarations fall back to `refs`. This is grounding, not a compiler.
- Set `CODEGRAPH_DB_DIR` to relocate the index directory (relative to `--dir`, or absolute).

## When
Before reading files to "find X". The `context-engineering` skill makes this the default first move on any non-trivial navigation.

## Verify
`python3 skills/codegraph/tests/test_codegraph.py` (stdlib only).
