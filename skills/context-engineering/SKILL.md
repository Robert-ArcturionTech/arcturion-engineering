---
name: context-engineering
description: Use during any non-trivial engineering task to stay fast and cheap — the discipline of spending the smallest, most relevant context to reach a correct result. Covers grounding before grepping, parallel-by-default tool use, research-plan-implement ordering, path-scoped rules, and progressive compaction.
---

# Context engineering — smallest sufficient context

Speed and cost are mostly a function of how much irrelevant context you drag around. Tighten the loop:

## 1. Ground before you grep
Before reading files to find something, consult a code index — it answers "where is X" in milliseconds without burning tokens on full-text scans. This plugin's `codegraph` skill does exactly that:
```bash
CG="${CLAUDE_PLUGIN_ROOT}/skills/codegraph/scripts/codegraph.py"
python3 "$CG" index   --dir <repo>
python3 "$CG" def     <symbol> --dir <repo>
python3 "$CG" callers <fn>     --dir <repo>
```
Only open the files the index points at. Re-grepping the whole tree every session is the most common waste.

## 2. RPI — Research, Plan, Implement (in that order)
No implementation edits until a plan exists and the goal is written as checkable predicates (commands that exit 0 when the goal is met, e.g. `pytest tests/test_x.py`, `grep -q ... file`). A wrong plan executed fast is slower than a right plan. The predicates double as your definition of done.

## 3. Parallel by default
Independent work runs concurrently, not sequentially:
- Issue independent tool calls in one batch (multiple reads/greps at once).
- For 2+ independent sub-tasks, dispatch parallel subagents rather than doing them in series.
Reserve sequential work for genuine dependencies.

## 4. Path-scoped rules
Keep the top-level `CLAUDE.md` lean; push domain detail into path-scoped rules so only the relevant slice loads when working in that area. Propose new rules from observed failure patterns, but have a human review them before wiring — never auto-edit live instruction files.

## 5. Progressive compaction
As a task's context grows, compact: summarize settled decisions, drop raw exploration output once its conclusion is captured, keep only the live working set. The harness compacts automatically; help it by not re-reading what's already established.

## Why
Path-scoped rules, model routing, and compaction are widely reported to cut token use substantially; the practical effect is lower latency and cost per task.
