#!/usr/bin/env python3
"""Adversarial code review via a budget-capped, tool-less second-model harness.

Builds a structured review prompt over a git diff (or explicit files), runs it
through a harness script (default: the bundled audit.sh, which calls the Claude
Code CLI tool-less, no-session, with --max-budget-usd and JSON output), and parses
a machine-readable verdict. Review runs in the cloud, so it costs a (capped) few
cents but no local RAM.

The harness is pluggable: set AUDIT_SCRIPT to any executable-by-bash script that
accepts `--model M --budget USD --prompt-file FILE` and prints the reviewer's
reply (or a Claude JSON envelope containing it) on stdout.

Usage:
  review.py --diff [--against HEAD] [--budget 0.50] [--model sonnet]
  review.py --files a.py b.ts [...]
Exit: 0 verdict PASS, 1 CONCERNS/FAIL, 2 setup error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_AUDIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.sh")
AUDIT_SCRIPT = os.environ.get("AUDIT_SCRIPT") or DEFAULT_AUDIT_SCRIPT

PROMPT_TEMPLATE = """You are a senior staff engineer performing an adversarial code review. \
Review ONLY the diff/code below. Hunt for: logic errors, off-by-one and boundary bugs, \
unhandled errors / silently-swallowed exceptions, infinite-loop or unbounded-recursion risk, \
race conditions, resource leaks (files/processes/handles), dependency fragility, injection / \
path-traversal / secret-leak security issues, and incorrect assumptions. Be specific and \
skeptical; do not praise. If the code is sound, say so plainly.

Respond with ONLY a fenced ```json block of this exact shape:
{{"verdict": "PASS|CONCERNS|FAIL", "findings": [{{"severity": "high|medium|low", "where": "file:line or symbol", "issue": "...", "fix": "..."}}], "summary": "one line"}}

CODE UNDER REVIEW:
{code}
"""


def collect_diff(against: str) -> str:
    try:
        r = subprocess.run(["git", "diff", against], capture_output=True, text=True, timeout=30)
        return r.stdout
    except Exception as e:  # noqa: BLE001
        return f"(could not collect diff: {e})"


def collect_files(files) -> str:
    chunks = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                chunks.append(f"# FILE: {f}\n{fh.read()}")
        except OSError as e:
            chunks.append(f"# FILE: {f} (unreadable: {e})")
    return "\n\n".join(chunks)


def extract_verdict(envelope_text: str) -> dict | None:
    """Parse the claude --output-format json envelope, then the reviewer's inner JSON."""
    text = envelope_text
    try:
        env = json.loads(envelope_text)
        text = env.get("result") or env.get("response") or envelope_text
        if isinstance(text, (dict, list)):
            text = json.dumps(text)
    except ValueError:
        pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL) or re.search(
        r"(\{.*\})", text, re.DOTALL
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--against", default="HEAD")
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--budget", default="0.50")
    ap.add_argument("--model", default="sonnet")
    # Wall-clock cap on the harness subprocess. A single tool-less cloud review of a
    # large diff (near the 120k-char prompt cap) can run past 5 min. Default 600s,
    # overridable via env or flag.
    ap.add_argument("--timeout", type=int,
                    default=int(os.environ.get("REVIEW_TIMEOUT", "600")),
                    help="Harness subprocess timeout in seconds (default 600, env REVIEW_TIMEOUT).")
    args = ap.parse_args()

    if args.files:
        code = collect_files(args.files)
    elif args.diff:
        code = collect_diff(args.against)
    else:
        print("Specify --diff or --files", file=sys.stderr)
        return 2
    if not code.strip() or code.strip().startswith("(could not"):
        print(f"Nothing to review: {code.strip()[:120]}", file=sys.stderr)
        return 2
    if not os.path.exists(AUDIT_SCRIPT):
        print(f"Audit harness not found: {AUDIT_SCRIPT}", file=sys.stderr)
        return 2

    prompt = PROMPT_TEMPLATE.format(code=code[:120000])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(prompt)
        pf = tf.name
    try:
        r = subprocess.run(
            ["bash", AUDIT_SCRIPT, "--model", args.model, "--budget", str(args.budget),
             "--prompt-file", pf],
            capture_output=True, text=True, timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"Audit harness timed out after {args.timeout}s (review too large for the window; "
              f"raise --timeout or env REVIEW_TIMEOUT, or split the diff).", file=sys.stderr)
        return 2
    finally:
        os.unlink(pf)

    if r.returncode != 0:
        # The harness emits the claude --output-format json envelope (incl. API
        # error bodies like a 401) to STDOUT; stderr is often empty. Surface
        # whichever is non-empty so failures are diagnosable, not silent.
        detail = (r.stderr.strip() or r.stdout.strip())[:500]
        print(f"Audit harness failed (exit {r.returncode}): {detail}", file=sys.stderr)
        return 2
    verdict = extract_verdict(r.stdout)
    if not verdict:
        print("Could not parse a verdict from the reviewer. Raw:\n" + r.stdout[:1000])
        return 1
    print(json.dumps(verdict, indent=2))
    return 0 if verdict.get("verdict", "").upper() == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
