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

    def cli(self, *stdouts):
        results = [SimpleNamespace(returncode=0, stdout=out, stderr="") for out in stdouts]
        return mock.patch.object(reply.subprocess, "run", side_effect=results)

    def test_cli_mode_verifies_payload_in_raw_tool_output(self):
        env = reply.build_answer(args())
        log = stream_line(f"<routine-fire-payload> DATA {json.dumps(env)} </routine-fire-payload>")
        with mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC"}), mock.patch.object(reply.shutil, "which", return_value="/usr/bin/claude"), \
                self.cli(log) as run:
            os.environ.pop("CLAUDE_BRIDGE_INBOX_TOKEN", None)
            ok, status, body = reply.fire(env)
        self.assertEqual((ok, status), (True, 200))
        self.assertIn("verified", body)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "RemoteTrigger")
        self.assertIn("trig_ABC", cmd[2])

    def test_cli_mode_retries_once_when_payload_missing(self):
        env = reply.build_answer(args())
        idle = stream_line("BRIDGE_MESSAGE - BRIDGE_PUSH: none")
        good = stream_line(f"<routine-fire-payload> {json.dumps(env)} </routine-fire-payload>")
        with mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC"}), mock.patch.object(reply.shutil, "which", return_value="/usr/bin/claude"):
            os.environ.pop("CLAUDE_BRIDGE_INBOX_TOKEN", None)
            with self.cli(idle, good) as run:
                ok, _, body = reply.fire(env)
            self.assertTrue(ok)
            self.assertIn("attempt 2", body)
            self.assertEqual(run.call_count, 2)
            with self.cli(idle, idle):
                ok, _, body = reply.fire(env)
            self.assertFalse(ok)
            self.assertIn("not found", body)


def stream_line(text):
    """One stream-json event whose tool_result carries `text`, like `claude -p --output-format stream-json`."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": [{"type": "text", "text": text}]}]}})


class PollTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.patches = [
            mock.patch.object(reply, "STATE_FILE", os.path.join(tmp, "state.json")),
            mock.patch.object(reply, "INBOX_DIR", os.path.join(tmp, "in")),
            mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC"}),
            mock.patch.object(reply.shutil, "which", return_value="/usr/bin/claude"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def message(self, **kw):
        base = {"protocol": "claude-grok-bridge/1", "type": "question", "id": "q-1", "to": "cos", "from": {"kind": "claude-code"}, "question": "hi"}
        return {**base, **kw}

    def run_poll(self, *envelopes):
        text = "result: success - " + " ".join("BRIDGE_MESSAGE " + json.dumps(e) + " BRIDGE_PUSH: none" for e in envelopes)
        done = SimpleNamespace(returncode=0, stdout=stream_line(text), stderr="")
        with mock.patch.object(reply.subprocess, "run", return_value=done):
            return reply.poll("cos")

    def test_collects_only_new_messages_for_this_peer_from_claude(self):
        mine = self.message(id="q-mine")
        others = [self.message(id="q-other", to="dav"), self.message(id="a-1", type="answer", **{"from": {"kind": "grok-bot"}}),
                  self.message(id="q-fake", **{"from": {"kind": "grok-bot"}})]
        paths = self.run_poll(mine, *others)
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(pathlib.Path(paths[0]).read_text())["id"], "q-mine")
        self.assertEqual(self.run_poll(mine), [], "the same message must not be delivered twice")

    def test_extract_ignores_garbage(self):
        strings = ["BRIDGE_MESSAGE - BRIDGE_PUSH: none", "BRIDGE_MESSAGE {not json", "BRIDGE_MESSAGE " + json.dumps(self.message()) + " tail"]
        self.assertEqual([m["id"] for m in reply.extract_messages(strings)], ["q-1"])

    def test_inbox_id_required(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(reply, "LOCAL_CONFIG", "/nonexistent/bridge.local.json"):
            with self.assertRaises(SystemExit):
                reply.inbox_routine()


if __name__ == "__main__":
    unittest.main()
