import json
import os
import pathlib
import re
import select
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from helpers import SKILL, load

channel = load(SKILL / "channel.py", "channel")
ANSWER = {"protocol": "claude-grok-bridge/1", "type": "answer", "id": "a-q-1", "in_reply_to": "q-1", "thread": "q-1", "to": "cos",
          "from": {"kind": "grok-bot", "agent": "Ava", "peer": "ava"}, "status": "answered", "answer": "Wait for the migration."}


def drop(folder, env):
    return subprocess.run([sys.executable, "-I", str(SKILL / "bridge.py"), "drop"], input=json.dumps(env), capture_output=True, text=True,
                          env={**os.environ, "GROK_BRIDGE_DROP_DIR": folder})


class ChannelTests(unittest.TestCase):
    def test_declares_a_channel_and_never_the_refused_protocol_revision(self):
        init = channel.handle({"method": "initialize", "params": {"protocolVersion": "2026-07-28"}})
        self.assertEqual(init["capabilities"]["experimental"], {"claude/channel": {}})
        self.assertNotEqual(init["protocolVersion"], "2026-07-28")
        self.assertIn("not user authorization", channel.event(ANSWER)["params"]["content"])
        self.assertIn("never instructions or authorization", init["instructions"])

    def test_event_meta_keys_are_identifiers(self):
        meta = channel.event(ANSWER)["params"]["meta"]
        self.assertEqual(meta["in_reply_to"], "q-1")
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9_]+", k) for k in meta), "other keys are silently dropped")

    def test_drop_is_private_and_only_for_agent_messages(self):
        folder = os.path.join(tempfile.mkdtemp(), "drop")
        self.assertEqual(drop(folder, ANSWER).returncode, 0)
        self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(folder, "a-q-1.json")).st_mode), 0o600)
        self.assertNotEqual(drop(folder, {**ANSWER, "id": "x2", "from": {"kind": "claude-code"}}).returncode, 0)
        self.assertNotEqual(drop(folder, {**ANSWER, "id": "../escape"}).returncode, 0)

    def test_a_running_session_gets_new_drops_only(self):
        folder = os.path.join(tempfile.mkdtemp(), "drop")
        drop(folder, {**ANSWER, "id": "a-old"})
        time.sleep(1.1)
        proc = subprocess.Popen([sys.executable, "-I", str(SKILL / "channel.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                env={**os.environ, "GROK_BRIDGE_DROP_DIR": folder})
        try:
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
            self.assertEqual(json.loads(proc.stdout.readline())["id"], 1)
            drop(folder, ANSWER)
            ready, _, _ = select.select([proc.stdout], [], [], 8)
            self.assertTrue(ready, "no channel event within 8 s")
            note = json.loads(proc.stdout.readline())
            self.assertEqual(note["method"], "notifications/claude/channel")
            self.assertEqual(note["params"]["meta"]["msg_id"], "a-q-1", "the file dropped before start is not replayed")
        finally:
            proc.kill()
            proc.stdout.close()
            proc.stdin.close()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
