import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

from helpers import SKILL_SCRIPTS

SCRIPT = str(SKILL_SCRIPTS / "add_peer.py")


def run(stdin, *args, config):
    env = {**os.environ, "GROK_BRIDGE_CONFIG": config}
    return subprocess.run([sys.executable, "-I", SCRIPT, *args], input=stdin, capture_output=True, text=True, env=env)


class AddPeerTests(unittest.TestCase):
    def setUp(self):
        self.config = os.path.join(tempfile.mkdtemp(), "sub", "config.json")

    def test_stdin_writes_private_config_and_strips_prefix(self):
        res = run(json.dumps({"webhook_url": "https://h.example.test/x", "authorization": "Authorization: Bearer crsr_abcdefgh"}),
                  "--peer", "cos", "--name", "CoS", "--inbox", "trig_X", "--stdin", config=self.config)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(self.config).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.config)).st_mode), 0o700)
        data = json.loads(pathlib.Path(self.config).read_text())
        self.assertEqual(data["inbox_routine"], "trig_X")
        self.assertEqual(data["peers"]["cos"], {"name": "CoS", "webhook_url": "https://h.example.test/x", "authorization": "Bearer crsr_abcdefgh"})
        self.assertNotIn("crsr_abcdefgh", res.stdout)

    def test_keeps_other_peers(self):
        for peer in ("cos", "dav"):
            run(json.dumps({"webhook_url": f"https://{peer}.example.test", "authorization": "Bearer abcdefgh"}), "--peer", peer, "--stdin", config=self.config)
        self.assertEqual(sorted(json.loads(pathlib.Path(self.config).read_text())["peers"]), ["cos", "dav"])

    def test_inbox_mode_needs_no_values(self):
        res = run("", "--peer", "cos", "--name", "CoS", "--inbox", "trig_X", "--inbox-mode", config=self.config)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(pathlib.Path(self.config).read_text())["peers"]["cos"], {"name": "CoS", "mode": "inbox"})

    def test_inbox_mode_keeps_an_existing_fast_lane(self):
        run(json.dumps({"webhook_url": "https://h.example.test/x", "authorization": "Bearer abcdefgh"}), "--peer", "cos", "--stdin", config=self.config)
        res = run("", "--peer", "cos", "--name", "CoS", "--inbox-mode", config=self.config)
        self.assertEqual(res.returncode, 0, res.stderr)
        entry = json.loads(pathlib.Path(self.config).read_text())["peers"]["cos"]
        self.assertEqual(entry["webhook_url"], "https://h.example.test/x")
        self.assertIn("Kept the existing fast lane", res.stdout)

    def test_rejects_non_https(self):
        res = run(json.dumps({"webhook_url": "http://h.example.test", "authorization": "Bearer abcdefgh"}), "--peer", "cos", "--stdin", config=self.config)
        self.assertNotEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
