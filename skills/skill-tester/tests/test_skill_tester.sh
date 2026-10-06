#!/usr/bin/env bash
# Self-test for skill-tester: builds good and bad skills in a temp dir and checks verdicts.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTER="$HERE/../scripts/test-all.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/skill-tester.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
fails=0
check() { # desc, expected_exit, expected_substring, args...
    local desc="$1" want="$2" needle="$3"; shift 3
    local out rc
    out=$(SKILLS_DIR="$TMP" bash "$TESTER" "$@" 2>&1); rc=$?
    if [ "$rc" -eq "$want" ] && printf '%s' "$out" | grep -q -- "$needle"; then
        echo "ok   - $desc"
    else
        echo "FAIL - $desc (exit $rc, wanted $want, needle '$needle')"; printf '%s\n' "$out"; fails=$((fails+1))
    fi
}

mkdir -p "$TMP/good/scripts"
printf -- '---\nname: good\ndescription: A fine skill.\n---\n# good\nRun `scripts/run.sh`.\n' > "$TMP/good/SKILL.md"
printf '#!/usr/bin/env bash\necho hi\n' > "$TMP/good/scripts/run.sh"; chmod +x "$TMP/good/scripts/run.sh"
check "valid skill passes" 0 "PASS (1)" "$TMP/good"

mkdir -p "$TMP/nodesc"
printf -- '---\nname: nodesc\n---\nbody\n' > "$TMP/nodesc/SKILL.md"
check "missing description fails" 1 "missing 'description:'" "$TMP/nodesc"

mkdir -p "$TMP/nofm"
printf '# no frontmatter\n' > "$TMP/nofm/SKILL.md"
check "missing frontmatter fails" 1 "missing frontmatter" "$TMP/nofm"

mkdir -p "$TMP/empty"
check "missing SKILL.md fails" 1 "no SKILL.md" "$TMP/empty"

mkdir -p "$TMP/dead"
printf -- '---\nname: dead\ndescription: d\n---\nSee `scripts/missing.sh`.\n' > "$TMP/dead/SKILL.md"
check "dead ref warns (exit 0)" 0 "dead ref: scripts/missing.sh" "$TMP/dead"

mkdir -p "$TMP/bad"
printf -- '---\nname: bad\ndescription: d\n---\n' > "$TMP/bad/SKILL.md"
printf '#!/usr/bin/env bash\nif then\n' > "$TMP/bad/x.sh"
check "shell syntax error fails" 1 "syntax error" "$TMP/bad"

[ "$fails" -eq 0 ] && echo "ALL PASS" || { echo "$fails failure(s)"; exit 1; }
