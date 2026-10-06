#!/usr/bin/env python3
"""codegraph — RAM-light local code grounding index (no resident model).

Preindexes a codebase's symbol DEFINITIONS into a per-project SQLite db via
zero-dependency per-language regex, so navigation becomes a symbol lookup instead
of repeated full-text greps — fewer tokens, fewer tool calls. References/callers
are computed on demand with grep. 100% local, incremental by mtime, no
tree-sitter/grammar/ctags install required.

Usage:
  codegraph.py index   [--dir DIR]
  codegraph.py def NAME [--dir DIR]
  codegraph.py refs NAME [--dir DIR]
  codegraph.py callers NAME [--dir DIR]
  codegraph.py stats   [--dir DIR]
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys

DB_DIRNAME = ".codegraph"
DB_FILE = "index.db"
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "dist", "build", ".venv", "venv",
    ".next", ".mypy_cache", ".pytest_cache", "target", ".tox", ".idea",
}
EXT_LANG = {
    ".py": "python", ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js",
    ".mjs": "js", ".cjs": "js", ".rs": "rust", ".go": "go", ".swift": "swift", ".sh": "sh",
}
PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [(r"^\s*(?:async\s+)?def\s+(\w+)", "func"), (r"^\s*class\s+(\w+)", "class")],
    "ts": [
        (r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", "func"),
        (r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", "class"),
        (r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>", "func"),
        (r"^\s*(?:export\s+)?interface\s+(\w+)", "type"),
        (r"^\s*(?:export\s+)?type\s+(\w+)\s*=", "type"),
    ],
    "rust": [
        (r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", "func"),
        (r"^\s*(?:pub\s+)?struct\s+(\w+)", "type"),
        (r"^\s*(?:pub\s+)?enum\s+(\w+)", "type"),
        (r"^\s*(?:pub\s+)?trait\s+(\w+)", "type"),
    ],
    "go": [
        (r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)", "func"),
        (r"^\s*type\s+(\w+)\s+struct", "type"),
        (r"^\s*type\s+(\w+)\s+interface", "type"),
    ],
    "swift": [
        (r"^\s*(?:public\s+|private\s+|internal\s+|fileprivate\s+)?(?:static\s+)?func\s+(\w+)", "func"),
        (r"^\s*(?:public\s+)?(?:final\s+)?class\s+(\w+)", "class"),
        (r"^\s*(?:public\s+)?struct\s+(\w+)", "type"),
    ],
    "sh": [(r"^\s*function\s+(\w+)", "func"), (r"^\s*(\w+)\s*\(\)\s*\{", "func")],
}
PATTERNS["js"] = PATTERNS["ts"]


def db_dir(root: str) -> str:
    """Index dir: <root>/.codegraph, or CODEGRAPH_DB_DIR (absolute, or relative to root)."""
    return os.path.join(root, os.environ.get("CODEGRAPH_DB_DIR") or DB_DIRNAME)


def db_path(root: str) -> str:
    return os.path.join(db_dir(root), DB_FILE)


def connect(root: str) -> sqlite3.Connection:
    os.makedirs(db_dir(root), exist_ok=True)
    c = sqlite3.connect(db_path(root))
    c.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, lang TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS symbols(name TEXT, kind TEXT, file TEXT, line INT, sig TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sym_name ON symbols(name)")
    return c


def iter_code_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".codegraph")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXT_LANG:
                yield os.path.join(dirpath, fn), EXT_LANG[ext]


def index_file(c: sqlite3.Connection, path: str, lang: str) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return 0
    c.execute("DELETE FROM symbols WHERE file=?", (path,))
    pats = [(re.compile(p), k) for p, k in PATTERNS.get(lang, [])]
    n = 0
    for i, line in enumerate(lines, 1):
        for rx, kind in pats:
            m = rx.match(line)
            if m:
                c.execute(
                    "INSERT INTO symbols(name,kind,file,line,sig) VALUES(?,?,?,?,?)",
                    (m.group(1), kind, path, i, line.strip()[:200]),
                )
                n += 1
                break
    return n


def cmd_index(root: str) -> int:
    c = connect(root)
    seen: set[str] = set()
    rescanned = 0
    for path, lang in iter_code_files(root):
        seen.add(path)
        mtime = os.path.getmtime(path)
        row = c.execute("SELECT mtime FROM files WHERE path=?", (path,)).fetchone()
        if row and abs(row[0] - mtime) < 1e-6:
            continue
        index_file(c, path, lang)
        c.execute("INSERT OR REPLACE INTO files(path,mtime,lang) VALUES(?,?,?)", (path, mtime, lang))
        rescanned += 1
    for (p,) in c.execute("SELECT path FROM files").fetchall():
        if p not in seen:
            c.execute("DELETE FROM symbols WHERE file=?", (p,))
            c.execute("DELETE FROM files WHERE path=?", (p,))
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    nfiles = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    print(f"indexed {nfiles} files, {total} symbols ({rescanned} (re)scanned)")
    c.close()
    return 0


def cmd_def(root: str, name: str) -> int:
    c = connect(root)
    rows = c.execute(
        "SELECT file,line,kind,sig FROM symbols WHERE name=? ORDER BY file,line", (name,)
    ).fetchall()
    if not rows:
        rows = c.execute(
            "SELECT file,line,kind,sig FROM symbols WHERE name LIKE ? ORDER BY file,line LIMIT 50",
            (f"%{name}%",),
        ).fetchall()
    for f, ln, kind, sig in rows:
        print(f"{f}:{ln}\t{kind}\t{sig}")
    if not rows:
        print(f"(no symbol matching {name!r}; run: codegraph.py index)")
    c.close()
    return 0 if rows else 1


def _grep(pattern: str, root: str) -> list[str]:
    excludes = [f"--exclude-dir={d}" for d in SKIP_DIRS]
    includes = [f"--include=*{e}" for e in EXT_LANG]
    try:
        r = subprocess.run(
            ["grep", "-rnE", *excludes, *includes, pattern, root],
            capture_output=True, text=True, timeout=60,
        )
        return [ln for ln in r.stdout.splitlines() if ln.strip()]
    except Exception as e:  # noqa: BLE001
        return [f"(grep failed: {e})"]


def cmd_refs(root: str, name: str) -> int:
    out = _grep(rf"\b{re.escape(name)}\b", root)[:200]
    for ln in out:
        print(ln)
    return 0


def cmd_callers(root: str, name: str) -> int:
    out = _grep(rf"\b{re.escape(name)}[[:space:]]*\(", root)[:200]
    for ln in out:
        print(ln)
    return 0


def cmd_stats(root: str) -> int:
    c = connect(root)
    rows = c.execute(
        "SELECT kind, COUNT(*) AS c FROM symbols GROUP BY kind ORDER BY c DESC"
    ).fetchall()
    for kind, cnt in rows:
        print(f"{kind}\t{cnt}")
    if not rows:
        print("(empty index; run: codegraph.py index)")
    c.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["index", "def", "refs", "callers", "stats"])
    ap.add_argument("name", nargs="?", default=None)
    ap.add_argument("--dir", default=".")
    args = ap.parse_args()
    root = os.path.abspath(args.dir)

    if args.command == "index":
        return cmd_index(root)
    if args.command == "stats":
        return cmd_stats(root)
    if not args.name:
        print(f"{args.command} requires a NAME", file=sys.stderr)
        return 2
    return {"def": cmd_def, "refs": cmd_refs, "callers": cmd_callers}[args.command](root, args.name)


if __name__ == "__main__":
    raise SystemExit(main())
