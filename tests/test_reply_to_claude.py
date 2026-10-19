import json
import os
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from helpers import GROK, Recorder, load

reply = load(GROK / "reply_to_claude.py", "reply_to_claude")


def args(**kw):
    base = dict(question=None, in_reply_to="q-1", session_id=None, agent="CoS", status="answered", answer="PONG", answer_file=None)
    return SimpleNamespace(**{**base, **kw})


class BuildAnswerTests(unittest.TestCase):
    def test_answer_envelope(self):
        env = reply.build_answer(args(session_id="cse_1"))
        self.assertEqual(env["protocol"], "claude-grok-bridge/1")
        self.assertEqual((env["type"], env["in_reply_to"], env["answer"], env["status"]), ("answer", "q-1", "PONG", "answered"))
        self.assertEqual(env["reply_to"], {"session_id": "cse_1"})
        self.assertEqual(env["from"], {"kind": "grok-bot", "agent": "CoS", "version": reply.version()})

    def test_reads_id_and_session_from_question_file(self):
        for kind in ("question", "request", "note"):
            path = os.path.join(tempfile.mkdtemp(), "q.json")
            pathlib.Path(path).write_text(json.dumps({"protocol": "claude-grok-bridge/1", "type": kind, "id": f"{kind}-9", "reply_to": {"session_id": "session_9"}}))
            env = reply.build_answer(args(question=path, in_reply_to=None))
            self.assertEqual((env["in_reply_to"], env["reply_to"]["session_id"]), (f"{kind}-9", "session_9"))

    def test_rejects_empty_answer(self):
        with self.assertRaises(SystemExit):
            reply.build_answer(args(answer=""))


class DeliveryTests(unittest.TestCase):
    def test_token_mode_calls_documented_fire_endpoint(self):
        rec = Recorder(body='{"type":"routine_fire","claude_code_session_id":"session_1"}')
        token = "sk-ant-oat01-secretsecretsecret"
        with mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC", "CLAUDE_BRIDGE_INBOX_TOKEN": token}), \
                mock.patch.object(reply.urllib.request, "urlopen", rec):
            ok, status, body = reply.fire(reply.build_answer(args()))
        self.assertTrue(ok)
        self.assertEqual(rec.request.full_url, "https://api.anthropic.com/v1/claude_code/routines/trig_ABC/fire")
        self.assertEqual(rec.request.get_header("Authorization"), f"Bearer {token}")
        self.assertEqual(rec.request.get_header("Anthropic-version"), "2023-06-01")
        sent = json.loads(json.loads(rec.request.data)["text"])
        self.assertEqual(sent["answer"], "PONG")
        self.assertNotIn(token, body)

    def test_cli_mode_without_cli_fails_cleanly(self):
        with mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC"}, clear=False), mock.patch.object(reply.shutil, "which", return_value=None):
            os.environ.pop("CLAUDE_BRIDGE_INBOX_TOKEN", None)
            ok, status, body = reply.fire(reply.build_answer(args()))
        self.assertFalse(ok)
        self.assertIn("claude CLI not found", body)

    def test_cli_mode_parses_http_status(self):
        done = SimpleNamespace(returncode=0, stdout="HTTP 200", stderr="")
        with mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC"}), mock.patch.object(reply.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(reply.subprocess, "run", return_value=done) as run:
            os.environ.pop("CLAUDE_BRIDGE_INBOX_TOKEN", None)
            ok, status, _ = reply.fire(reply.build_answer(args()))
        self.assertEqual((ok, status), (True, 200))
        cmd = run.call_args.args[0]
        self.assertIn("RemoteTrigger", cmd)
        self.assertIn("trig_ABC", cmd[2])

    def test_inbox_id_required(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(reply, "LOCAL_CONFIG", "/nonexistent/bridge.local.json"):
            with self.assertRaises(SystemExit):
                reply.inbox_routine()


if __name__ == "__main__":
    unittest.main()
