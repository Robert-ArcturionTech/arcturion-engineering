# arcturion-engineering

A [Claude Code](https://claude.com/claude-code) plugin of small, dependency-free engineering skills: ground yourself in a codebase cheaply, get a cost-capped second opinion on your diff, scaffold new components correctly, and lint your own skills.

Built by Robert Lingoes with AI coding agents (Claude Code / Codex); Robert owns the architecture, requirements and review.

Everything is Python 3 standard library or plain bash. No packages to install.

## Skills

| Skill | What it does |
|---|---|
| [`context-engineering`](skills/context-engineering/SKILL.md) | A discipline for spending the smallest sufficient context: ground before grepping, research-plan-implement ordering, parallel tool use, path-scoped rules, progressive compaction. |
| [`codegraph`](skills/codegraph/SKILL.md) | A local symbol index (regex into SQLite, stored in `.codegraph/index.db`). Instant "where is X defined / who calls it" lookups for Python, TS/JS, Rust, Go, Swift and shell, so the agent opens only the files that matter. |
| [`adversarial-review`](skills/adversarial-review/SKILL.md) | A tool-less, no-session, budget-capped second-model review of a diff or files, returning a `PASS` / `CONCERNS` / `FAIL` JSON verdict. The reviewer harness is pluggable via `AUDIT_SCRIPT`. |
| [`scaffold`](skills/scaffold/SKILL.md) | Starter templates for a background daemon, an MCP server, a skill bundle, and a CLI tool, each with its gotcha-fixes baked in and a passing starter test. |
| [`skill-tester`](skills/skill-tester/SKILL.md) | A lint for skills: frontmatter, dead path references, script syntax and permissions, secret-like strings. Usable as a pre-commit or CI gate. |

## Install

**As a plugin (from GitHub):**

```
/plugin marketplace add ArcturionTechnologies/arcturion-engineering
/plugin install arcturion-engineering@arcturion-engineering
```

**Or copy individual skills** into your user skills directory:

```bash
git clone https://github.com/ArcturionTechnologies/arcturion-engineering.git
cp -R arcturion-engineering/skills/codegraph ~/.claude/skills/
```

When a skill is copied this way, `${CLAUDE_PLUGIN_ROOT}/skills/<name>` in its docs becomes `~/.claude/skills/<name>`.

## Examples

**Find a symbol without grepping the tree**

```bash
CG="${CLAUDE_PLUGIN_ROOT}/skills/codegraph/scripts/codegraph.py"
python3 "$CG" index   --dir .
python3 "$CG" def     build_widget --dir .
python3 "$CG" callers build_widget --dir .
python3 "$CG" stats   --dir .
```

**Get a second-model review of your working-tree diff** (needs the `claude` CLI and credentials; see the skill for setup)

```bash
export CLAUDE_CODE_OAUTH_TOKEN=...      # from `claude setup-token`
python3 "${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/scripts/review.py" --diff --budget 0.50
# {"verdict": "CONCERNS", "findings": [{"severity": "medium", "where": "app.py:41", ...}], "summary": "..."}
```

Use a different reviewer by pointing `AUDIT_SCRIPT` at your own harness script.

**Scaffold a CLI tool whose secret comes from an env var**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/scaffold/scripts/generate.py" cli my_tool --dest ./out
python3 ./out/my_tool/tests/test_my_tool.py
```

**Lint a directory of skills**

```bash
SKILLS_DIR=./skills bash "${CLAUDE_PLUGIN_ROOT}/skills/skill-tester/scripts/test-all.sh"
```

## Tests

```bash
./run_tests.sh
```

Runs each skill's test suite (the adversarial-review tests mock the harness, so they cost nothing) and lints the skills in this repo with `skill-tester`.

## Notes and limits

- `codegraph` is regex-based grounding, not a compiler: roughly right for common declaration forms, and `refs` is the fallback for exotic ones.
- `adversarial-review` sends the diff or files you pass to a hosted model. Don't point it at files containing secrets.
- The `scaffold` daemon template ships a macOS launchd plist; the daemon script itself is portable.

## License

MIT. See [LICENSE](LICENSE).
