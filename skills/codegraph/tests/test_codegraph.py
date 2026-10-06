#!/usr/bin/env python3
"""Tests for codegraph. Pure stdlib unittest. Run: python3 tests/test_codegraph.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
CG = os.path.join(SCRIPTS, "codegraph.py")


def run(*args, cwd=None):
    return subprocess.run([sys.executable, CG, *args], capture_output=True, text=True, cwd=cwd)


class CodeGraph(unittest.TestCase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(prefix="cg_")
        self.addCleanup(shutil.rmtree, self.proj, ignore_errors=True)
        with open(os.path.join(self.proj, "mod.py"), "w") as f:
            f.write("class Widget:\n    def assemble(self):\n        return 1\n\ndef build_widget():\n    return Widget()\n")
        with open(os.path.join(self.proj, "app.ts"), "w") as f:
            f.write("export function render() {}\nexport const helper = () => 2\nexport class View {}\n")
        sub = os.path.join(self.proj, "node_modules")
        os.makedirs(sub)
        with open(os.path.join(sub, "junk.py"), "w") as f:
            f.write("def should_be_ignored():\n    pass\n")

    def test_index_and_stats(self):
        out = run("index", "--dir", self.proj).stdout
        self.assertIn("symbols", out)
        stats = run("stats", "--dir", self.proj).stdout
        self.assertIn("func", stats)
        self.assertIn("class", stats)

    def test_def_lookup(self):
        run("index", "--dir", self.proj)
        out = run("def", "build_widget", "--dir", self.proj).stdout
        self.assertIn("mod.py", out)
        self.assertIn("func", out)

    def test_ts_symbols_indexed(self):
        run("index", "--dir", self.proj)
        self.assertIn("app.ts", run("def", "render", "--dir", self.proj).stdout)
        self.assertIn("app.ts", run("def", "helper", "--dir", self.proj).stdout)
        self.assertIn("app.ts", run("def", "View", "--dir", self.proj).stdout)

    def test_skip_dirs_excluded(self):
        run("index", "--dir", self.proj)
        out = run("def", "should_be_ignored", "--dir", self.proj)
        self.assertEqual(out.returncode, 1)  # not found -> exit 1

    def test_callers_grep(self):
        run("index", "--dir", self.proj)
        out = run("callers", "Widget", "--dir", self.proj).stdout
        self.assertIn("mod.py", out)  # Widget() call site

    def test_index_lives_in_dot_codegraph(self):
        run("index", "--dir", self.proj)
        self.assertTrue(os.path.isfile(os.path.join(self.proj, ".codegraph", "index.db")))

    def test_db_dir_override(self):
        alt = tempfile.mkdtemp(prefix="cg_db_")
        env = dict(os.environ, CODEGRAPH_DB_DIR=alt)
        subprocess.run([sys.executable, CG, "index", "--dir", self.proj],
                       capture_output=True, text=True, env=env)
        self.assertTrue(os.path.isfile(os.path.join(alt, "index.db")))
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".codegraph")))

    def test_incremental_reindex(self):
        run("index", "--dir", self.proj)
        # add a new symbol, reindex should pick it up
        with open(os.path.join(self.proj, "mod.py"), "a") as f:
            f.write("\ndef freshly_added():\n    pass\n")
        run("index", "--dir", self.proj)
        self.assertIn("mod.py", run("def", "freshly_added", "--dir", self.proj).stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
