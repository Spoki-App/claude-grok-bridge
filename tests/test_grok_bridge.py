import json
import os
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from helpers import GROK, Recorder, load, result_line, stream_line

bridge = load(GROK / "bridge.py", "grok_bridge")
QUESTION = {"protocol": "claude-grok-bridge/1", "type": "question", "id": "q-1", "to": "cos", "from": {"kind": "claude-code"},
            "question": "hi", "reply_to": {"session_id": "cse_1"}}


def cli(*stdouts):
    return mock.patch.object(bridge.subprocess, "run", side_effect=[SimpleNamespace(returncode=0, stdout=o, stderr="") for o in stdouts])


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.patches = [
            mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_ROUTINE": "trig_ABC"}),
            mock.patch.object(bridge, "STATE_FILE", os.path.join(tmp, "state.json")),
            mock.patch.object(bridge, "INBOX_DIR", os.path.join(tmp, "in")),
            mock.patch.object(bridge, "LOCAL_CONFIG", os.path.join(tmp, "local.json")),
            mock.patch.object(bridge.shutil, "which", return_value="/usr/bin/claude"),
        ]
        for p in self.patches:
            p.start()
        os.environ.pop("CLAUDE_BRIDGE_INBOX_TOKEN", None)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()


class AnswerTests(Base):
    def test_answer_envelope(self):
        env = bridge.answer(QUESTION, "CoS", "PONG")
        self.assertEqual((env["type"], env["in_reply_to"], env["answer"], env["status"]), ("answer", "q-1", "PONG", "answered"))
        self.assertEqual(env["reply_to"], {"session_id": "cse_1"})
        self.assertEqual(env["from"], {"kind": "grok-bot", "agent": "CoS", "version": bridge.version()})

    def test_rejects_empty_or_unknown_status(self):
        for text, status in (("", "answered"), ("x", "maybe")):
            with self.assertRaises(SystemExit):
                bridge.answer(QUESTION, "CoS", text, status)


class DeliveryTests(Base):
    def test_token_mode_uses_the_documented_fire_endpoint(self):
        token = "sk-ant-oat01-secretsecretsecret"
        rec = Recorder(body='{"type":"routine_fire"}')
        with mock.patch.dict(os.environ, {"CLAUDE_BRIDGE_INBOX_TOKEN": token}), mock.patch.object(bridge.urllib.request, "urlopen", rec):
            out = bridge.deliver(bridge.answer(QUESTION, "CoS", "PONG"))
        self.assertTrue(out["delivered"])
        self.assertEqual(rec.request.full_url, "https://api.anthropic.com/v1/claude_code/routines/trig_ABC/fire")
        self.assertEqual(rec.request.get_header("Authorization"), f"Bearer {token}")
        self.assertEqual(json.loads(json.loads(rec.request.data)["text"])["answer"], "PONG")
        self.assertNotIn(token, json.dumps(out))

    def test_cli_mode_verifies_and_retries_once(self):
        env = bridge.answer(QUESTION, "CoS", "PONG")
        idle = stream_line("BRIDGE_MESSAGE - BRIDGE_PUSH: none")
        landed = stream_line(f"<routine-fire-payload> {json.dumps(env)} </routine-fire-payload>")
        with cli(landed) as run:
            self.assertEqual(bridge.deliver(env)["detail"], "delivered and verified (attempt 1)")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "RemoteTrigger")
        with cli(idle, landed):
            self.assertTrue(bridge.deliver(env)["delivered"])
        with cli(idle, idle):
            self.assertFalse(bridge.deliver(env)["delivered"])

    def test_missing_cli(self):
        with mock.patch.object(bridge.shutil, "which", return_value=None):
            self.assertIn("claude CLI not found", bridge.deliver(bridge.answer(QUESTION, "CoS", "x"))["detail"])


class PollTests(Base):
    def poll(self, *envelopes):
        text = "result - " + " ".join("BRIDGE_MESSAGE " + json.dumps(e) + " BRIDGE_PUSH: none" for e in envelopes)
        with cli(stream_line(text)):
            return bridge.poll("cos")

    def test_only_new_messages_for_this_peer_from_claude(self):
        others = [{**QUESTION, "id": "q-dav", "to": "dav"}, {**QUESTION, "id": "a-1", "type": "answer", "from": {"kind": "grok-bot"}},
                  {**QUESTION, "id": "q-fake", "from": {"kind": "grok-bot"}}]
        paths = self.poll(QUESTION, *others)
        self.assertEqual([json.loads(pathlib.Path(p).read_text())["id"] for p in paths], ["q-1"])
        self.assertEqual(self.poll(QUESTION), [], "never twice")

    def test_extract_ignores_garbage(self):
        strings = ["BRIDGE_MESSAGE - x", "BRIDGE_MESSAGE {broken", "BRIDGE_MESSAGE " + json.dumps(QUESTION) + " tail"]
        self.assertEqual([m["id"] for m in bridge.extract_messages(strings)], ["q-1"])


class SetupTests(Base):
    def test_takes_the_id_from_the_final_result_only(self):
        listing = stream_line('{"data":[{"id":"trig_OTHER1"},{"id":"trig_OTHER2"}]}')
        with cli(listing + "\n" + result_line("trig_INBOX9")):
            self.assertEqual(bridge.setup(), "trig_INBOX9")
        self.assertEqual(json.loads(pathlib.Path(bridge.LOCAL_CONFIG).read_text()), {"inbox_routine": "trig_INBOX9"})

    def test_fails_clearly(self):
        with cli(result_line("NONE no environment")), self.assertRaises(SystemExit) as ctx:
            bridge.setup()
        self.assertIn("claude /login", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
