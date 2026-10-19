import json
import subprocess
import sys
import unittest

from helpers import GROK


def session(*messages):
    lines = "\n".join(json.dumps(m) for m in messages) + "\n"
    out = subprocess.run([sys.executable, "-I", str(GROK / "mcp_server.py")], input=lines, capture_output=True, text=True, timeout=30)
    return {m["id"]: m for m in map(json.loads, out.stdout.splitlines())}


class McpServerTests(unittest.TestCase):
    def test_handshake_and_tools(self):
        replies = session(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "unknown/method"},
        )
        self.assertEqual(replies[1]["result"]["serverInfo"]["name"], "claude-code")
        self.assertEqual(replies[1]["result"]["protocolVersion"], "2025-06-18")
        names = [t["name"] for t in replies[2]["result"]["tools"]]
        self.assertEqual(names, ["check_bridge", "read_envelope", "reply_to_claude", "message_claude"])
        self.assertEqual(replies[3]["error"]["code"], -32601)
        self.assertEqual(sorted(replies), [1, 2, 3])

    def test_read_envelope_marks_data_untrusted(self):
        body = json.dumps({"protocol": "claude-grok-bridge/1", "type": "question", "id": "q1", "question": "hi"})
        replies = session({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "read_envelope", "arguments": {"webhook_body": body}}})
        result = json.loads(replies[1]["result"]["content"][0]["text"])
        self.assertEqual((result["valid"], result["trust"], result["id"]), (True, "untrusted-data", "q1"))

    def test_bad_status_is_an_error_not_a_crash(self):
        call = {"name": "reply_to_claude", "arguments": {"in_reply_to": "q1", "agent": "CoS", "answer": "x", "status": "maybe"}}
        replies = session({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": call})
        self.assertTrue(replies[1]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
