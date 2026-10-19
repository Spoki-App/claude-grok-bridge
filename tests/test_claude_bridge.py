import contextlib
import io
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from helpers import SKILL, Recorder, load, write_config

bridge = load(SKILL / "bridge.py", "claude_bridge")
URL = "https://hooks.example.test/secret-path-abcdefghijklmnopqrstuvwxyz"
AUTH = "Bearer crsr_supersecretvalue1234567890"


def sent(out):
    """The envelope inside the BODY line the session passes to the inbox routine."""
    body = json.loads(next(line for line in out.splitlines() if line.startswith("BODY "))[len("BODY "):])
    return json.loads(body["text"])


def run(*argv):
    out, code = io.StringIO(), 0
    with mock.patch.object(sys, "argv", ["bridge.py", *argv]), contextlib.redirect_stdout(out):
        try:
            bridge.main()
        except SystemExit as e:
            code = e.code or 0
    return code, out.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("GROK_BRIDGE_", "CLAUDE_CODE_REMOTE"))}
        self.env = mock.patch.dict(os.environ, clean, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def config(self, data, mode=0o600):
        os.environ["GROK_BRIDGE_CONFIG"] = write_config(self.tmp, data, mode)


class ResolveTests(Base):
    def test_webhook_peer(self):
        self.config({"inbox_routine": "trig_A", "peers": {"cos": {"name": "CoS", "webhook_url": URL, "authorization": AUTH}}})
        t = bridge.resolve("cos")
        self.assertEqual((t["mode"], t["url"], t["auth"], t["inbox"], t["name"]), ("webhook", URL, AUTH, "trig_A", "CoS"))

    def test_env_overrides_and_header_prefix_is_stripped(self):
        self.config({"peers": {}})
        os.environ.update({"GROK_BRIDGE_COS_URL": "https://env.example.test/x", "GROK_BRIDGE_COS_AUTH": "Authorization: Bearer env"})
        t = bridge.resolve("cos")
        self.assertEqual((t["url"], t["auth"]), ("https://env.example.test/x", "Bearer env"))

    def test_unknown_peer_is_zero_touch(self):
        self.config({"peers": {}})
        code, out = run("check", "--to", "nobody")
        self.assertEqual(code, 0)
        self.assertIn("mode=inbox", out)

    def test_refuses_readable_config(self):
        self.config({"peers": {}}, mode=0o644)
        code, out = run("check", "--to", "cos")
        self.assertEqual(code, 2)
        self.assertIn("CONFIG_INSECURE", out)

    def test_single_peer_is_the_default(self):
        self.config({"inbox_routine": "trig_A", "peers": {"cos": {"mode": "inbox"}}})
        code, out = run("note", "hello")
        self.assertEqual(code, 0)
        self.assertEqual(sent(out)["to"], "cos")

    def test_no_peer_and_no_default(self):
        self.config({"peers": {}})
        code, out = run("note", "hello")
        self.assertEqual(code, 2)


class SendTests(Base):
    def test_ask_in_zero_touch_mode_prints_the_envelope(self):
        self.config({"inbox_routine": "trig_IN", "peers": {"cos": {"name": "CoS", "mode": "inbox"}}})
        os.environ["CLAUDE_CODE_REMOTE_SESSION_ID"] = "cse_ME"
        with mock.patch.object(bridge.urllib.request, "urlopen", Recorder()) as rec:
            code, out = run("ask", "Merge", "now?", "--to", "cos", "--context", "ctx", "--option", "A) yes", "--option", "B) no",
                            "--recommend", "A", "--ref", "pr=https://x.test/1")
        self.assertEqual(code, 0)
        self.assertIsNone(rec.request)
        first = out.splitlines()[0]
        self.assertTrue(first.startswith("SEND_VIA_INBOX routine=trig_IN id=q-"))
        self.assertTrue(first.endswith("via=Claude_Code_Remote fire_trigger"))
        env = sent(out)
        self.assertEqual((env["type"], env["question"], env["to"], env["context"]), ("question", "Merge now?", "cos", "ctx"))
        self.assertEqual(env["options"], ["A) yes", "B) no"])
        self.assertEqual(env["refs"], {"pr": "https://x.test/1"})
        self.assertEqual(env["reply_to"], {"session_id": "cse_ME", "inbox_routine": "trig_IN"})
        self.assertEqual(env["from"]["version"], bridge.version())

    def test_tell_carries_the_owner_words(self):
        self.config({"peers": {"cos": {"mode": "inbox"}}})
        code, out = run("tell", "Move card 1234 to review", "--to", "cos", "--owner-words", "sposta la card 1234 in review")
        env = sent(out)
        self.assertIn("via=RemoteTrigger run", out.splitlines()[0])
        self.assertEqual((env["type"], env["on_behalf_of"], env["owner_words"]), ("request", "owner", "sposta la card 1234 in review"))

    def test_webhook_mode_posts_and_never_prints_secrets(self):
        self.config({"peers": {"cos": {"webhook_url": URL, "authorization": AUTH}}})
        rec = Recorder(body='{"success":true,"runUuid":"abcdefabcdefabcdefabcdefabcdef12"}')
        with mock.patch.object(bridge.urllib.request, "urlopen", rec):
            code, out = run("hello", "--to", "cos")
        self.assertEqual(code, 0)
        self.assertEqual((rec.request.full_url, rec.request.get_header("Authorization")), (URL, AUTH))
        self.assertEqual(json.loads(rec.request.data)["question"], "Reply with the single word PONG.")
        self.assertIn("via=webhook", out)
        for secret in ("secret-path", "supersecret", "abcdefabcdef"):
            self.assertNotIn(secret, out)

    def test_answer_an_agent(self):
        self.config({"peers": {"cos": {"mode": "inbox"}}})
        code, out = run("answer", "q-agent-1", "It", "is", "391", "--to", "cos")
        env = sent(out)
        self.assertEqual((env["type"], env["in_reply_to"], env["answer"], env["status"], env["thread"]), ("answer", "q-agent-1", "It is 391", "answered", "q-agent-1"))
        self.assertEqual(env["state"], "TASK_STATE_COMPLETED", "A2A tools read the state")

    def test_thread_flag(self):
        self.config({"peers": {"cos": {"mode": "inbox"}}})
        code, out = run("ask", "And tomorrow?", "--to", "cos", "--thread", "q-20261019-1036-aa5b")
        self.assertEqual(sent(out)["thread"], "q-20261019-1036-aa5b")

    def test_bad_ref_is_a_clear_error(self):
        self.config({"peers": {"cos": {"mode": "inbox"}}})
        code, out = run("note", "x", "--to", "cos", "--ref", "no-equals-sign")
        self.assertEqual(code, 4)
        self.assertIn("key=value", out)

    def test_http_error(self):
        self.config({"peers": {"cos": {"webhook_url": URL, "authorization": AUTH}}})
        with mock.patch.object(bridge.urllib.request, "urlopen", Recorder(status=500)):
            code, out = run("note", "x", "--to", "cos")
        self.assertEqual(code, 3)
        self.assertIn("HTTP_ERROR 500", out)


class ValidateTests(unittest.TestCase):
    BASE = {"protocol": "claude-grok-bridge/1", "type": "question", "id": "q-1", "from": {"kind": "claude-code"}, "to": "cos", "question": "Hi?"}

    def invalid(self, env):
        with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stdout(io.StringIO()):
            bridge.validate(env)
        self.assertEqual(ctx.exception.code, 4)

    def test_rules(self):
        bridge.validate(self.BASE)
        self.invalid({**self.BASE, "protocol": "other/1"})
        self.invalid({**self.BASE, "type": "answer"})
        self.invalid({k: v for k, v in self.BASE.items() if k != "question"})
        self.invalid({**self.BASE, "on_behalf_of": "owner", "owner_words": "x"})
        self.invalid({**self.BASE, "type": "request", "request": "x", "on_behalf_of": "owner"})


class AddPeerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(tmp, "sub", "config.json")
        self.claude_md = pathlib.Path(tmp, "CLAUDE.md")

    def add(self, stdin, *args):
        env = {**os.environ, "GROK_BRIDGE_CONFIG": self.cfg, "GROK_BRIDGE_CLAUDE_MD": str(self.claude_md)}
        return subprocess.run([sys.executable, "-I", str(SKILL / "bridge.py"), "add-peer", *args], input=stdin, capture_output=True, text=True, env=env)

    def saved(self):
        return json.loads(pathlib.Path(self.cfg).read_text())

    def test_fast_lane_from_stdin_is_private(self):
        res = self.add(json.dumps({"webhook_url": "https://h.test/x", "authorization": "Authorization: Bearer crsr_abcdefgh"}), "cos", "--name", "CoS", "--inbox", "trig_X", "--stdin")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(self.cfg).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.cfg)).st_mode), 0o700)
        self.assertEqual(self.saved()["peers"]["cos"]["authorization"], "Bearer crsr_abcdefgh")
        self.assertNotIn("crsr_abcdefgh", res.stdout)

    def test_zero_touch_needs_nothing_and_keeps_a_fast_lane(self):
        self.assertEqual(self.add("", "cos", "--name", "CoS", "--inbox-mode").returncode, 0)
        self.assertEqual(self.saved()["peers"]["cos"], {"name": "CoS", "mode": "inbox"})
        self.add(json.dumps({"webhook_url": "https://h.test/x", "authorization": "Bearer abcdefgh"}), "cos", "--stdin")
        res = self.add("", "cos", "--name", "CoS", "--inbox-mode")
        self.assertEqual(self.saved()["peers"]["cos"]["webhook_url"], "https://h.test/x")
        self.assertIn("Kept the existing fast lane", res.stdout)

    def test_claude_md_learns_the_agent_names_once(self):
        self.claude_md.write_text("# My rules\n\nBe brief.\n")
        self.add("", "cos", "--name", "CoS", "--inbox-mode")
        self.add("", "ava", "--name", "Ava", "--inbox-mode")
        self.add("", "ava", "--name", "Ava", "--inbox-mode")
        text = self.claude_md.read_text()
        self.assertTrue(text.startswith("# My rules\n\nBe brief.\n"), "the user's own rules stay untouched")
        self.assertEqual(text.count("<!-- grok-bridge:agents -->"), 1)
        self.assertIn("Ava (`--to ava`), CoS (`--to cos`)", text)

    def test_rejects_plain_http(self):
        self.assertNotEqual(self.add(json.dumps({"webhook_url": "http://h.test", "authorization": "Bearer abcdefgh"}), "cos", "--stdin").returncode, 0)


if __name__ == "__main__":
    unittest.main()
