#!/usr/bin/env python3
"""Tests for adversarial-review. Mocks the audit harness — zero cloud cost.

Run: python3 tests/test_review.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)
import review  # noqa: E402


class ExtractVerdict(unittest.TestCase):
    def test_envelope_with_fenced_json(self):
        env = json.dumps({"result": 'Here:\n```json\n{"verdict":"PASS","findings":[],"summary":"ok"}\n```'})
        self.assertEqual(review.extract_verdict(env)["verdict"], "PASS")

    def test_envelope_with_inner_json_string(self):
        env = json.dumps({"result": json.dumps({"verdict": "FAIL", "findings": [], "summary": "x"})})
        self.assertEqual(review.extract_verdict(env)["verdict"], "FAIL")

    def test_plain_json_no_envelope(self):
        self.assertEqual(review.extract_verdict('{"verdict":"CONCERNS","findings":[]}')["verdict"], "CONCERNS")

    def test_unparseable_returns_none(self):
        self.assertIsNone(review.extract_verdict("no json here at all"))


class EndToEndMocked(unittest.TestCase):
    def _fake_harness(self, verdict_obj):
        env_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"result": json.dumps(verdict_obj)}, env_file)
        env_file.close()
        fake = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
        fake.write(f"#!/usr/bin/env bash\ncat {env_file.name}\n")
        fake.close()
        os.chmod(fake.name, 0o755)
        return fake.name, env_file.name

    def test_concerns_exits_1(self):
        fake, envf = self._fake_harness(
            {"verdict": "CONCERNS", "findings": [{"severity": "high", "where": "x.py:1",
             "issue": "bug", "fix": "y"}], "summary": "s"}
        )
        codefile = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
        codefile.write("x = 1\n")
        codefile.close()
        env = dict(os.environ, AUDIT_SCRIPT=fake)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "review.py"), "--files", codefile.name],
                           capture_output=True, text=True, env=env)
        for p in (fake, envf, codefile.name):
            os.unlink(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("CONCERNS", r.stdout)

    def test_pass_exits_0(self):
        fake, envf = self._fake_harness({"verdict": "PASS", "findings": [], "summary": "clean"})
        codefile = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
        codefile.write("x = 1\n")
        codefile.close()
        env = dict(os.environ, AUDIT_SCRIPT=fake)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "review.py"), "--files", codefile.name],
                           capture_output=True, text=True, env=env)
        for p in (fake, envf, codefile.name):
            os.unlink(p)
        self.assertEqual(r.returncode, 0)


class BundledHarness(unittest.TestCase):
    AUDIT = os.path.join(SCRIPTS, "audit.sh")

    def test_default_harness_is_bundled(self):
        self.assertEqual(review.DEFAULT_AUDIT_SCRIPT, self.AUDIT)
        self.assertTrue(os.path.isfile(self.AUDIT))

    def test_missing_auth_is_setup_error(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "claude")
            with open(fake, "w") as f:
                f.write("#!/usr/bin/env bash\necho should-not-run\n")
            os.chmod(fake, 0o755)
            env = {k: v for k, v in os.environ.items()
                   if k not in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")}
            env["PATH"] = d + os.pathsep + env["PATH"]
            r = subprocess.run(["bash", self.AUDIT, "hello"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", r.stderr)

    def test_audit_passes_safety_flags_to_claude(self):
        """With a stub `claude` on PATH, confirm tool-less / no-session / budget-capped invocation."""
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "claude")
            with open(fake, "w") as f:
                f.write('#!/usr/bin/env bash\necho "ARGS: $*"\n')
            os.chmod(fake, 0o755)
            env = dict(os.environ, CLAUDE_CODE_OAUTH_TOKEN="test-token")
            env["PATH"] = d + os.pathsep + env["PATH"]
            r = subprocess.run(["bash", self.AUDIT, "--budget", "0.10", "hi"],
                               capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        for flag in ("--tools", "--no-session-persistence", "--max-budget-usd 0.10"):
            self.assertIn(flag, r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
