import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from helpers import SKILL_SCRIPTS, Recorder, load, write_config

send = load(SKILL_SCRIPTS / "send_to_grok.py", "send_to_grok")

SECRET_URL = "https://hooks.example.test/secret-path-abcdefghijklmnopqrstuvwxyz"
SECRET_AUTH = "Bearer crsr_supersecretvalue1234567890"
QUESTION = {"protocol": "claude-grok-bridge/1", "type": "question", "id": "q-1", "from": {"kind": "claude-code"}, "question": "Hi?"}


def run_main(*argv):
    out = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["send_to_grok.py", *argv]), contextlib.redirect_stdout(out):
        try:
            send.main()
        except SystemExit as e:
            code = e.code or 0
    return code, out.getvalue()


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for key in [k for k in os.environ if k.startswith("GROK_BRIDGE_")]:
            del os.environ[key]

    def tearDown(self):
        self.env.stop()

    def use_config(self, data, mode=0o600):
        os.environ["GROK_BRIDGE_CONFIG"] = write_config(self.tmp, data, mode)

    def test_reads_peer_from_file(self):
        self.use_config({"inbox_routine": "trig_A", "peers": {"cos": {"name": "CoS", "webhook_url": SECRET_URL, "authorization": SECRET_AUTH}}})
        peer = send.resolve("cos")
        self.assertEqual((peer["mode"], peer["url"], peer["auth"], peer["inbox"], peer["name"]), ("webhook", SECRET_URL, SECRET_AUTH, "trig_A", "CoS"))

    def test_env_overrides_file(self):
        self.use_config({"peers": {}})
        os.environ.update({"GROK_BRIDGE_COS_URL": "https://env.example.test/x", "GROK_BRIDGE_COS_AUTH": "Bearer env"})
        peer = send.resolve("cos")
        self.assertEqual((peer["url"], peer["auth"]), ("https://env.example.test/x", "Bearer env"))

    def test_strips_pasted_header_prefix(self):
        self.use_config({"peers": {"cos": {"webhook_url": SECRET_URL, "authorization": "Authorization: " + SECRET_AUTH}}})
        self.assertEqual(send.resolve("cos")["auth"], SECRET_AUTH)

    def test_refuses_world_readable_config(self):
        self.use_config({"peers": {}}, mode=0o644)
        code, out = run_main("--check", "--peer", "cos")
        self.assertEqual(code, 2)
        self.assertIn("CONFIG_INSECURE", out)

    def test_unconfigured_peer_falls_back_to_inbox_mode(self):
        self.use_config({"peers": {}})
        code, out = run_main("--check", "--peer", "nobody")
        self.assertEqual(code, 0)
        self.assertIn("mode=inbox", out)
        self.assertIn("not configured", out)

    def test_inbox_mode_prints_envelope_for_the_session_to_deliver(self):
        self.use_config({"inbox_routine": "trig_IN", "peers": {"cos": {"name": "CoS", "mode": "inbox"}}})
        rec = Recorder()
        with mock.patch.object(send.urllib.request, "urlopen", rec):
            code, out = run_main("--peer", "cos", "--hello")
        self.assertEqual(code, 0)
        self.assertIsNone(rec.request, "inbox mode must not call any webhook")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("SEND_VIA_INBOX routine=trig_IN id=q-hello-"))
        env = json.loads(lines[1][len("ENVELOPE "):])
        self.assertEqual((env["to"], env["type"], env["reply_to"]["inbox_routine"]), ("cos", "question", "trig_IN"))


class EnvelopeTests(unittest.TestCase):
    def assert_invalid(self, env):
        with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stdout(io.StringIO()):
            send.validate(env)
        self.assertEqual(ctx.exception.code, 4)

    def test_accepts_question_request_note(self):
        send.validate(QUESTION)
        send.validate({**QUESTION, "type": "note", "note": "fyi"})
        send.validate({**QUESTION, "type": "request", "request": "do x", "on_behalf_of": "owner", "owner_words": "fai x"})

    def test_rejects_wrong_protocol_or_type(self):
        self.assert_invalid({**QUESTION, "protocol": "other/1"})
        self.assert_invalid({**QUESTION, "type": "answer"})

    def test_rejects_missing_body_field(self):
        self.assert_invalid({k: v for k, v in QUESTION.items() if k != "question"})

    def test_on_behalf_of_needs_request_and_owner_words(self):
        self.assert_invalid({**QUESTION, "on_behalf_of": "owner", "owner_words": "x"})
        self.assert_invalid({**QUESTION, "type": "request", "request": "do x", "on_behalf_of": "owner"})


class SendTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.patch = mock.patch.dict(os.environ, {"GROK_BRIDGE_CONFIG": write_config(tmp, {
            "inbox_routine": "trig_INBOX", "peers": {"cos": {"webhook_url": SECRET_URL, "authorization": SECRET_AUTH}}})})
        self.patch.start()
        os.environ.pop("CLAUDE_CODE_REMOTE_SESSION_ID", None)

    def tearDown(self):
        self.patch.stop()

    def test_hello_posts_envelope_and_never_prints_secrets(self):
        rec = Recorder(body='{"success":true,"runUuid":"abcdefabcdefabcdefabcdefabcdef12"}')
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_REMOTE_SESSION_ID": "cse_TEST"}), mock.patch.object(send.urllib.request, "urlopen", rec):
            code, out = run_main("--peer", "cos", "--hello")
        self.assertEqual(code, 0)
        self.assertEqual(rec.request.full_url, SECRET_URL)
        self.assertEqual(rec.request.get_header("Authorization"), SECRET_AUTH)
        body = json.loads(rec.request.data)
        self.assertEqual(body["type"], "question")
        self.assertEqual(body["reply_to"], {"session_id": "cse_TEST", "inbox_routine": "trig_INBOX"})
        self.assertEqual(body["from"]["version"], send.version())
        self.assertNotIn(SECRET_URL, out)
        self.assertNotIn("supersecret", out)
        self.assertNotIn("abcdefabcdef", out)

    def test_http_error_exit_code(self):
        with mock.patch.object(send.urllib.request, "urlopen", Recorder(status=500)):
            code, out = run_main("--peer", "cos", "--hello")
        self.assertEqual(code, 3)
        self.assertIn("HTTP 500", out)


if __name__ == "__main__":
    unittest.main()
