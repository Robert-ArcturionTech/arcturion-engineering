---
name: skill-tester
description: Lint installed Claude Code skills — check SKILL.md frontmatter, dead path references, script executability and syntax, and hardcoded secret patterns. Use when asked to test, validate, or audit skills, check skill health, or after installing or editing skills.
---

# Skill Tester

A small quality-gate script for a directory of skills (default `~/.claude/skills`). It catches regressions (dead references, broken scripts, malformed frontmatter) before they bite in live use. Reports only; it never modifies skills.

## Checks

| Check | Result if it fails |
|---|---|
| `SKILL.md` exists | FAIL |
| Frontmatter block present (`---` on line 1) | FAIL |
| `name:` in frontmatter | FAIL |
| `description:` in frontmatter | FAIL |
| `.sh` syntax (`bash -n`), `.js`/`.mjs` syntax (`node --check`, if node is installed), `.py` syntax (`py_compile`) | FAIL |
| No secret-like patterns (API key / token prefixes) in any skill file | FAIL |
| Description length under 800 chars | WARN |
| Script files executable and starting with a shebang | WARN |
| Backticked paths that begin with scripts, tests, references or assets in SKILL.md exist (placeholders containing `<`, `$`, `*` or `{` are skipped) | WARN |

Secret detection is deliberately conservative: false positives are acceptable, false negatives are not.

## Usage

```bash
TESTER="${CLAUDE_PLUGIN_ROOT}/skills/skill-tester/scripts/test-all.sh"

bash "$TESTER"                              # every skill under ~/.claude/skills
SKILLS_DIR=./skills bash "$TESTER"          # every skill under a different directory
bash "$TESTER" path/to/one-skill            # a single skill
```

Exit code is 0 when no skill FAILs (warnings do not fail the run) and 1 otherwise, so it works as a pre-commit or CI gate.

## Output

```
Skill Test Report - 2026-01-01 12:00

PASS (3)
  - skill-a
  - skill-b
  - skill-c

WARN (1) - works but issues noted
  - skill-d: dead ref (a path SKILL.md mentions that does not exist)

FAIL (1) - broken, needs fix
  - skill-e: frontmatter missing 'description:'

Total: 5 skills audited
```

## When to run

- After installing or editing a skill
- Before publishing a skill or plugin
- Periodically, to catch silent drift

## Verify

`bash skills/skill-tester/tests/test_skill_tester.sh` builds good and bad skills in a temp dir and checks each verdict.
