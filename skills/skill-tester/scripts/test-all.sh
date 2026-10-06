#!/usr/bin/env bash
# skill-tester: lint Claude Code skills. Reports only; never modifies skills.
#
# Usage:
#   test-all.sh                 # lint every skill dir under $SKILLS_DIR
#   test-all.sh path/to/skill   # lint one skill dir
# Env:
#   SKILLS_DIR  directory containing skill folders (default: ~/.claude/skills)
# Exit: 0 if no skill FAILs, 1 otherwise.

set -u

SKILLS_DIR="${SKILLS_DIR:-$HOME/.claude/skills}"
PASS=()
WARN=()
FAIL=()

check_skill() {
    local dir="$1"
    local name
    name=$(basename "$dir")
    local skill_md="$dir/SKILL.md"
    local issues=()
    local failures=()

    if [ ! -f "$skill_md" ]; then
        FAIL+=("$name: no SKILL.md")
        return
    fi

    # Frontmatter: must open with --- and have name + description inside the block
    local fm
    fm=$(awk 'NR==1 && $0!="---"{exit} NR>1 && $0=="---"{exit} NR>1{print}' "$skill_md")
    head -1 "$skill_md" | grep -q '^---$' || failures+=("SKILL.md missing frontmatter")
    printf '%s\n' "$fm" | grep -q '^name:' || failures+=("frontmatter missing 'name:'")
    printf '%s\n' "$fm" | grep -q '^description:' || failures+=("frontmatter missing 'description:'")

    # Description length (bloat warning)
    local desc_len
    desc_len=$(printf '%s\n' "$fm" | awk '/^description:/{sub(/^description: */, ""); print length; exit}')
    if [ -n "${desc_len:-}" ] && [ "$desc_len" -gt 800 ] 2>/dev/null; then
        issues+=("description >800 chars")
    fi

    # Scripts: executable bit, shebang, syntax
    local script script_name
    while IFS= read -r -d '' script; do
        script_name="$(basename "$script")"
        [ -x "$script" ] || issues+=("$script_name not executable")
        head -1 "$script" | grep -qE '^#!' || issues+=("$script_name missing shebang")
        case "$script" in
            *.sh) bash -n "$script" 2>/dev/null || failures+=("$script_name syntax error") ;;
            *.mjs|*.js)
                if command -v node >/dev/null 2>&1; then
                    node --check "$script" 2>/dev/null || failures+=("$script_name syntax error")
                fi ;;
            *.py)
                if command -v python3 >/dev/null 2>&1; then
                    python3 -m py_compile "$script" 2>/dev/null || failures+=("$script_name syntax error")
                fi ;;
        esac
    done < <(find "$dir" -type f \( -name '*.sh' -o -name '*.mjs' -o -name '*.js' -o -name '*.py' \) \
                  -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -print0 2>/dev/null)
    find "$dir" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

    # Dead refs: paths in backticks that start with scripts/, tests/, references/ or assets/
    local ref
    while IFS= read -r ref; do
        [ -n "$ref" ] || continue
        case "$ref" in *'<'*|*'$'*|*'*'*|*'{'*) continue ;; esac   # placeholders / globs / variables
        [ -e "$dir/$ref" ] || issues+=("dead ref: $ref")
    done < <(grep -oE '`(scripts|tests|references|assets)/[A-Za-z0-9_./-]+`' "$skill_md" | tr -d '`' | sort -u)

    # Secret patterns (conservative: false positives OK, false negatives not)
    if grep -rqE '(sk-[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z_-]{35}|xox[bp]-[0-9]+-[0-9]+-[0-9]+|ghp_[A-Za-z0-9]{36})' "$dir" 2>/dev/null; then
        failures+=("hardcoded secret pattern detected")
    fi

    if [ "${#failures[@]}" -gt 0 ]; then
        FAIL+=("$name: $(IFS=';'; echo "${failures[*]}")")
    elif [ "${#issues[@]}" -gt 0 ]; then
        WARN+=("$name: $(IFS=';'; echo "${issues[*]}")")
    else
        PASS+=("$name")
    fi
}

if [ $# -gt 0 ] && [ -d "$1" ]; then
    check_skill "${1%/}"
else
    for d in "$SKILLS_DIR"/*/; do
        [ -d "$d" ] && check_skill "${d%/}"
    done
fi

echo "Skill Test Report - $(date '+%Y-%m-%d %H:%M')"
echo

echo "PASS (${#PASS[@]})"
for s in ${PASS[@]+"${PASS[@]}"}; do echo "  - $s"; done
echo

if [ "${#WARN[@]}" -gt 0 ]; then
    echo "WARN (${#WARN[@]}) - works but issues noted"
    for s in "${WARN[@]}"; do echo "  - $s"; done
    echo
fi

if [ "${#FAIL[@]}" -gt 0 ]; then
    echo "FAIL (${#FAIL[@]}) - broken, needs fix"
    for s in "${FAIL[@]}"; do echo "  - $s"; done
    echo
fi

TOTAL=$((${#PASS[@]} + ${#WARN[@]} + ${#FAIL[@]}))
echo "Total: $TOTAL skills audited"

[ "${#FAIL[@]}" -eq 0 ] || exit 1
