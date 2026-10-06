#!/usr/bin/env python3
"""Scaffold generator — stamp out battle-tested starter patterns with the
gotcha-fixes already baked in, each with a passing starter test.

Kinds:
  daemon  launchd-style daemon: /health endpoint, optional load gate, pid lock, runtime!=source notes
  mcp     stdio JSON-RPC MCP server stub (zero deps)
  skill   SKILL.md + scripts/main.py + tests/  (matches plugin skill convention)
  cli     CLI tool whose secrets come from plain environment variables, with a test

Usage: generate.py {daemon|mcp|skill|cli} NAME [--dest DIR] [--port N]
"""
from __future__ import annotations

import argparse
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from templates import render  # noqa: E402


def _write(path: str, content: str, executable: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    if executable:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def generate(kind: str, name: str, dest: str, port: int) -> str:
    base = os.path.join(os.path.abspath(dest), name)
    for path, content, executable in render(kind, name, base, port):
        _write(path, content, executable)
    return base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["daemon", "mcp", "skill", "cli"])
    ap.add_argument("name")
    ap.add_argument("--dest", default=".")
    ap.add_argument("--port", type=int, default=8790)
    args = ap.parse_args()
    if not args.name.isidentifier():
        print("NAME must be a valid identifier (letters/digits/underscore)", file=sys.stderr)
        return 2
    base = generate(args.kind, args.name, args.dest, args.port)
    print(f"scaffolded {args.kind} at {base}")
    print(f"next: python3 {os.path.join(base, 'tests')}/*  (run the starter test)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
