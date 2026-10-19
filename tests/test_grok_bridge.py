import json
import os
import pathlib
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from helpers import GROK, Recorder, load, result_line, stream_line, tool_use_line

bridge = load(GROK / "bridge.py", "grok_bridge")
QUESTION = {"protocol": "claude-grok-bridge/1", "type": "question", "id": "q-1", "to": "cos", "from": {"kind": "claude-code"},
            "question": "hi", "reply_to": {"session_id": "cse_1"}}


DONE = result_line("done")


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

    def test_answers_carry_the_a2a_state(self):
        states = {s: bridge.answer(QUESTION, "Ava", "x", s)["state"] for s in bridge.STATUSES}
        self.assertEqual(states["declined"], "TASK_STATE_REJECTED")
        self.assertEqual(states["needs_confirmation"], "TASK_STATE_INPUT_REQUIRED")

    def test_answers_keep_the_thread(self):
        self.assertEqual(bridge.answer(QUESTION, "CoS", "x")["thread"], "q-1", "a first message starts its thread")
        self.assertEqual(bridge.answer({**QUESTION, "id": "q-2", "thread": "q-1"}, "CoS", "x")["thread"], "q-1")

    def test_agent_asks_claude_code(self):
        env = bridge.ask_claude("CoS", "cos", "What does this repo do?", repo="acme/api", subject="Repo")
        self.assertEqual((env["type"], env["to"], env["question"]), ("question", "claude-code", "What does this repo do?"))
        self.assertEqual((env["from"]["peer"], env["refs"], env["reply_to"]), ("cos", {"repo": "acme/api"}, {"session_id": None}))
        self.assertEqual(bridge.ask_claude("CoS", "cos", "x", session_id="cse_1")["reply_to"], {"session_id": "cse_1"})

    def test_poll_accepts_answers_from_claude_code(self):
        reply = {"protocol": "claude-grok-bridge/1", "type": "answer", "id": "a-1", "in_reply_to": "q-9", "to": "cos",
                 "from": {"kind": "claude-code"}, "status": "answered", "answer": "391"}
        with cli(stream_line("BRIDGE_MESSAGE " + json.dumps(reply)) + "\n" + DONE):
            self.assertEqual(len(bridge.poll("cos")), 1)

    def test_agent_kind_is_configurable(self):
        with mock.patch.object(bridge, "AGENT_KIND", "other-agent"):
            self.assertEqual(bridge.answer(QUESTION, "Ava", "x")["from"]["kind"], "other-agent")

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
        self.assertIs(run.call_args.kwargs["stdin"], bridge.subprocess.DEVNULL)
        with cli(idle, landed):
            self.assertTrue(bridge.deliver(env)["delivered"])
        with cli(idle, idle):
            self.assertFalse(bridge.deliver(env)["delivered"])

    def test_slow_log_is_read_again_before_firing_twice(self):
        env = bridge.answer(QUESTION, "CoS", "PONG")
        fired = stream_line('{"session_id": "cse_RUN1"}')
        landed = stream_line(f"<routine-fire-payload> {json.dumps(env)} </routine-fire-payload>")
        with mock.patch.object(bridge.time, "sleep"), cli(fired, landed) as run:
            out = bridge.deliver(env)
        self.assertEqual(out["detail"], "delivered and verified (attempt 1, second look)")
        self.assertEqual(run.call_count, 2, "read the same log, no second fire")
        self.assertIn("cse_RUN1", run.call_args.args[0][2])

    def test_unexpected_remote_action_is_refused(self):
        env = bridge.answer(QUESTION, "CoS", "PONG")
        with cli(tool_use_line("RemoteTrigger", {"action": "delete", "trigger_id": "trig_X"})):
            out = bridge.deliver(env)
        self.assertFalse(out["delivered"])
        self.assertIn("ALERT", out["detail"])

    def test_missing_cli(self):
        with mock.patch.object(bridge.shutil, "which", return_value=None):
            self.assertIn("claude CLI not found", bridge.deliver(bridge.answer(QUESTION, "CoS", "x"))["detail"])


class PollTests(Base):
    def poll(self, *envelopes, result=DONE, extra=""):
        text = "result - " + " ".join("BRIDGE_MESSAGE " + json.dumps(e) + " BRIDGE_PUSH: none" for e in envelopes)
        with cli(stream_line(text) + "\n" + extra + "\n" + result):
            return bridge.poll("cos")

    def state(self):
        return json.loads(pathlib.Path(bridge.STATE_FILE).read_text())

    def test_only_new_messages_for_this_peer_from_claude(self):
        others = [{**QUESTION, "id": "q-dav", "to": "dav"}, {**QUESTION, "id": "a-1", "type": "answer", "from": {"kind": "grok-bot"}},
                  {**QUESTION, "id": "q-fake", "from": {"kind": "grok-bot"}}]
        paths = self.poll(QUESTION, *others)
        self.assertEqual([json.loads(pathlib.Path(p).read_text())["id"] for p in paths], ["q-1"])
        self.assertEqual(self.poll(QUESTION), [], "never twice")

    def test_reads_a_run_still_in_progress_from_its_payload(self):
        payload = stream_line("<routine-fire-payload> The following was supplied... DATA " + json.dumps(QUESTION) + " </routine-fire-payload>")
        with cli(payload + "\n" + DONE):
            paths = bridge.poll("cos")
        self.assertEqual(len(paths), 1)

    def test_since_moves_only_after_a_complete_poll_and_keeps_an_overlap(self):
        self.poll(QUESTION, result=result_line("I stopped early"))
        first = self.state()["since"]
        self.poll(QUESTION, result=result_line("I stopped early"))
        self.assertEqual(self.state()["since"], first, "incomplete poll must not advance")
        before = bridge.datetime.datetime.now(bridge.datetime.timezone.utc)
        self.poll(QUESTION)
        moved = bridge.datetime.datetime.strptime(self.state()["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=bridge.datetime.timezone.utc)
        self.assertLess(moved, before - bridge.OVERLAP + bridge.datetime.timedelta(seconds=5))

    def test_poll_refuses_actions_outside_read_only(self):
        with cli(tool_use_line("RemoteTrigger", {"action": "update", "trigger_id": "trig_X"}) + "\n" + DONE), self.assertRaises(SystemExit) as ctx:
            bridge.poll("cos")
        self.assertIn("ALERT", str(ctx.exception))

    def test_reads_answers_from_ask_sessions_with_a_wider_window(self):
        question = bridge.ask_claude("CoS", "cos", "What is 19 times 21?")
        reply = {"protocol": "claude-grok-bridge/1", "type": "answer", "id": "a-7c3e91b4", "in_reply_to": question["id"],
                 "to": "cos", "from": {"kind": "claude-code"}, "status": "answered", "answer": "399"}
        log = stream_line("user: You were started by CoS ... " + json.dumps(question) + " result: success BRIDGE_MESSAGE " + json.dumps(reply))
        with cli(log + "\n" + DONE) as run:
            paths = bridge.poll("cos")
        self.assertEqual([json.loads(pathlib.Path(p).read_text())["answer"] for p in paths], ["399"], "the agent's own question is skipped")
        prompt = run.call_args.args[0][2]
        self.assertIn('"grok-bridge ask ..."', prompt)
        stamps = sorted({bridge.datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ") for t in re.findall(r"\d{4}-\d\d-\d\dT[\d:]{8}Z", prompt)})
        self.assertEqual(stamps[1] - stamps[0], bridge.ASK_WINDOW, "ask sessions answer later than the inbox run")

    def test_inbox_brief_holds_no_envelope_an_agent_could_mistake_for_an_answer(self):
        doc = (GROK.parent / "claude" / "inbox.md").read_text()
        self.assertEqual(bridge.extract_messages([doc, " ".join(doc.split())]), [])

    def test_audit_survives_events_whose_message_is_text(self):
        events = "\n".join([json.dumps({"type": "system", "message": "Claude Code started"}),
                            json.dumps({"type": "assistant", "message": {"content": "plain text"}}),
                            tool_use_line("RemoteTrigger", {"action": "list_runs"})])
        self.assertEqual(bridge.remote_actions(events), ["list_runs"])

    def test_extract_ignores_garbage(self):
        strings = ["BRIDGE_MESSAGE - x", 'BRIDGE_MESSAGE {"protocol": "claude-grok-bridge/1", broken', "BRIDGE_MESSAGE " + json.dumps(QUESTION) + " tail"]
        self.assertEqual([m["id"] for m in bridge.extract_messages(strings)], ["q-1"])


class ThreadTests(Base):
    def test_thread_lists_both_directions_oldest_first(self):
        first = {**QUESTION, "sent_at": "2026-10-19T10:00:00Z"}
        follow = {**QUESTION, "id": "q-2", "thread": "q-1", "sent_at": "2026-10-19T10:05:00Z"}
        other = {**QUESTION, "id": "q-9", "sent_at": "2026-10-19T10:01:00Z"}
        for env in (follow, other, first):
            bridge.archive(env)
        reply = bridge.answer(first, "CoS", "PONG")
        token = {"CLAUDE_BRIDGE_INBOX_TOKEN": "sk-ant-oat01-x"}
        with mock.patch.dict(os.environ, token), mock.patch.object(bridge.urllib.request, "urlopen", Recorder()):
            self.assertTrue(bridge.deliver(reply)["delivered"])
        ids = [e["id"] for e in bridge.thread("q-1")]
        self.assertEqual(ids[0], "q-1")
        self.assertEqual(set(ids), {"q-1", "q-2", reply["id"]})
        self.assertNotIn("q-9", ids)


class SetupTests(Base):
    def test_takes_the_id_from_the_final_result_only(self):
        listing = stream_line('{"data":[{"id":"trig_OTHER1"},{"id":"trig_OTHER2"}]}')
        with cli(listing + "\n" + result_line("trig_INBOX9")):
            self.assertEqual(bridge.setup(), "trig_INBOX9")
        self.assertEqual(json.loads(pathlib.Path(bridge.LOCAL_CONFIG).read_text()), {"inbox_routine": "trig_INBOX9"})

    def test_fails_clearly(self):
        for reply in ("NONE no environment", "NONE: found trig_OLD but could not update it"):
            with cli(result_line(reply)), self.assertRaises(SystemExit) as ctx:
                bridge.setup()
            self.assertIn("claude /login", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
