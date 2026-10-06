#!/usr/bin/env python3
"""Meta-test: generate each artifact kind and run its generated starter test.

Proves the scaffold emits working, test-green code. Pure stdlib.
Run: python3 tests/test_scaffold.py
"""
import glob
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)
import generate  # noqa: E402


def _run_generated_tests(base: str) -> tuple[int, str]:
    tests = glob.glob(os.path.join(base, "tests", "test_*.py"))
    assert tests, f"no generated tests under {base}"
    outputs = []
    for t in tests:
        r = subprocess.run([sys.executable, t], capture_output=True, text=True)
        outputs.append(r.stdout + r.stderr)
        if r.returncode != 0:
            return r.returncode, "\n".join(outputs)
    return 0, "\n".join(outputs)


class Scaffold(unittest.TestCase):
    def _check(self, kind, name):
        with tempfile.TemporaryDirectory(prefix="scaf_") as d:
            base = generate.generate(kind, name, d, port=8799)
            self.assertTrue(os.path.isdir(base))
            rc, out = _run_generated_tests(base)
            self.assertEqual(rc, 0, f"{kind} generated tests failed:\n{out}")

    def test_daemon(self):
        self._check("daemon", "demo_daemon_x")

    def test_mcp(self):
        self._check("mcp", "demo_mcp_x")

    def test_cli(self):
        self._check("cli", "demo_cli_x")

    def test_skill(self):
        self._check("skill", "demo_skill_x")

    def test_invalid_name_rejected(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "generate.py"), "cli", "bad-name"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_daemon_has_plist_and_health(self):
        with tempfile.TemporaryDirectory(prefix="scaf_") as d:
            base = generate.generate("daemon", "demo_daemon_y", d, port=8799)
            self.assertTrue(os.path.exists(os.path.join(base, "com.example.demo_daemon_y.plist")))
            with open(os.path.join(base, "demo_daemon_y.py")) as f:
                src = f.read()
            self.assertIn("/health", src)
            self.assertIn("load_ok", src)

    def test_cli_template_uses_plain_env_vars(self):
        with tempfile.TemporaryDirectory(prefix="scaf_") as d:
            base = generate.generate("cli", "demo_cli_z", d, port=8799)
            with open(os.path.join(base, "demo_cli_z.py")) as f:
                src = f.read()
            self.assertIn("os.environ", src)
            self.assertNotIn("broker", src.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
