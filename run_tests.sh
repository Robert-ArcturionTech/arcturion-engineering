#!/usr/bin/env bash
# Run every skill's test suite plus a self-lint of the skills. Exit non-zero on any failure.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rc=0
for t in "$ROOT"/skills/*/tests/test_*.py; do
    echo "== $t"
    python3 "$t" || rc=1
done
echo "== skills/skill-tester/tests/test_skill_tester.sh"
bash "$ROOT/skills/skill-tester/tests/test_skill_tester.sh" || rc=1
echo "== self-lint"
SKILLS_DIR="$ROOT/skills" bash "$ROOT/skills/skill-tester/scripts/test-all.sh" || rc=1
find "$ROOT" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
[ $rc -eq 0 ] && echo "ALL TESTS PASSED" || echo "TESTS FAILED"
exit $rc
