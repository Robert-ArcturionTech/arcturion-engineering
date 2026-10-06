---
name: scaffold
description: Use when starting a NEW component that follows a common pattern — a background daemon, an MCP server, a Claude Code skill bundle, or a CLI tool. Generates the boilerplate with the hard-won gotcha-fixes already baked in (runtime-vs-source, optional load gate, pid-lock identity check, /health, env-var-only secrets) plus a passing starter test, so you start correct instead of re-learning the same lessons.
---

# scaffold — start correct, not from scratch

Stamps out small, dependency-free patterns so new components inherit fixes that are easy to forget. Every generated artifact ships with a green starter test.

## Use
```bash
GEN="${CLAUDE_PLUGIN_ROOT}/skills/scaffold/scripts/generate.py"
python3 "$GEN" daemon my_daemon --dest <dir> --port 8795
python3 "$GEN" mcp    my_server --dest <dir>
python3 "$GEN" skill  my_skill  --dest <dir>
python3 "$GEN" cli    my_tool   --dest <dir>
# then: python3 <dir>/my_daemon/tests/test_my_daemon.py
```
`NAME` must be a valid Python identifier.

## What each kind bakes in
- **daemon** — `/health` endpoint on localhost, an optional load gate (set `<NAME>_LOAD_CHECK` to an executable that exits 2 to mean "skip heavy work"), a pid lock that is idempotent and reclaims stale locks, SIGTERM cleanup, and a macOS launchd plist (bootout, then bootstrap) with a **runtime != source** warning. Lock and state live under `$XDG_STATE_HOME` (default `~/.local/state/<name>/`), overridable with `<NAME>_STATE_DIR`. The plist is macOS-specific; on Linux wrap the script in a systemd unit.
- **mcp** — stdio JSON-RPC 2.0 server, zero deps, `initialize` / `tools/list` / `tools/call` with an example tool; notifications ignored.
- **skill** — a `SKILL.md`, a starter script, and a tests folder, matching the plugin skill layout.
- **cli** — argparse tool whose secrets come ONLY from plain environment variables (`<NAME>_API_TOKEN`), never hardcoded and never accepted as command-line arguments; includes a test for the present and missing cases.

## Failure modes
- **Template drift**: the baked-in gotcha-fixes are copies of lessons learned elsewhere. When you discover a better pattern (e.g. a stronger pid-lock check), patch the template in the same pass.
- **Starter test fails on a fresh scaffold**: that's a template bug, not a you-bug — fix the template, don't patch only the generated copy.
- **Runtime != source**: generating into a source dir and running from it skips the deploy step the scaffold assumes; copy to the install path before wiring a launch agent.

## Verify
The generator is covered by a meta-test that generates each kind and runs its starter test: `python3 skills/scaffold/tests/test_scaffold.py`.
