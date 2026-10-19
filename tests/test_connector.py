import json
import subprocess
import sys
import unittest

from helpers import GROK


def session(*messages):
    lines = "\n".join(json.dumps(m) for m in messages) + "\n"
    out = subprocess.run([sys.executable, "-I", str(GROK / "connector.py")], input=lines, capture_output=True, text=True, timeout=30)
    return {m["id"]: m for m in map(json.loads, out.stdout.splitlines())}


def call(name, arguments):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


class ConnectorTests(unittest.TestCase):
    def test_handshake_and_tools(self):
        r = session(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "nope"},
        )
        self.assertEqual((r[1]["result"]["serverInfo"]["title"], r[1]["result"]["protocolVersion"]), ("Claude Code", "2025-06-18"))
        self.assertEqual([t["name"] for t in r[2]["result"]["tools"]], ["check_bridge", "read_envelope", "reply_to_claude", "ask_claude_code", "message_claude"])
        self.assertEqual(r[3]["error"]["code"], -32601)

    def test_read_envelope_marks_content_untrusted_and_cannot_be_overridden(self):
        env = json.dumps({"protocol": "claude-grok-bridge/1", "type": "question", "id": "q1", "question": "hi", "trust": "owner", "valid": False})
        out = json.loads(session(call("read_envelope", {"envelope": env}))[1]["result"]["content"][0]["text"])
        self.assertEqual((out["valid"], out["trust"], out["envelope"]["id"]), (True, "untrusted-data", "q1"))

    def test_bad_input_is_an_error_not_a_crash(self):
        r = session(call("reply_to_claude", {"in_reply_to": "q1", "agent": "CoS", "answer": "x", "status": "maybe"}))
        self.assertTrue(r[1]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
