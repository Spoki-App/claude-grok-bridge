import json
import re
import subprocess
import unittest
import xml.etree.ElementTree as ET

from helpers import ROOT, load

EM_DASH = chr(0x2014)
TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".txt", ".yml", ".yaml", ""}


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / p for p in out.splitlines() if (ROOT / p).suffix in TEXT_SUFFIXES and (ROOT / p).is_file()]


class RepoConsistencyTests(unittest.TestCase):
    def test_no_em_dash(self):
        offenders = [str(p.relative_to(ROOT)) for p in tracked_files() if EM_DASH in p.read_text(errors="ignore")]
        self.assertEqual(offenders, [], "house style: no em dash characters")

    def test_skill_copies_are_in_sync(self):
        skill = ROOT / "claude" / "skills" / "grok-bridge"
        for name in ("VERSION", "PROTOCOL.md", "protocol.py"):
            self.assertEqual((ROOT / name).read_text(), (skill / name).read_text(), f"run scripts/sync.sh ({name})")
        self.assertEqual((ROOT / "protocol.py").read_text(), (ROOT / "grok" / "protocol.py").read_text(), "run scripts/sync.sh (grok)")

    def test_versions_agree(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        for manifest in ("grok/plugin/.cursor-plugin/plugin.json", "claude/.claude-plugin/plugin.json"):
            self.assertEqual(json.loads((ROOT / manifest).read_text())["version"], version, manifest)
        self.assertIn(f"claude-grok-bridge inbox v{version}.", (ROOT / "claude/inbox.md").read_text())
        self.assertIn(f"## [{version}]", (ROOT / "CHANGELOG.md").read_text())

    def test_no_stale_names(self):
        stale = ["reply_to_claude.py", "send_to_grok.py", "add_peer.py", "mcp_server.py", "ROUTINE_PROMPT", "INBOX_ROUTINE.md",
                 "SETUP.md", "sync-skill-docs", "plugins/claude-code"]
        allowed = {"CHANGELOG.md", "tests/test_repo.py"}
        hits = [f"{p.relative_to(ROOT)}: {name}" for p in tracked_files() if str(p.relative_to(ROOT)) not in allowed
                for name in stale if name in p.read_text(errors="ignore")]
        self.assertEqual(hits, [])

    def test_readme_chats_match_their_source(self):
        chats = load(ROOT / "scripts" / "chats.py", "chats")
        for name, messages in chats.CHATS.items():
            self.assertEqual((ROOT / "assets" / f"chat-{name}.svg").read_text(), chats.render(messages), f"run python3 scripts/chats.py ({name})")
            self.assertIn(f"assets/chat-{name}.svg", (ROOT / "README.md").read_text())

    def test_readme_demo_matches_its_source(self):
        demo = load(ROOT / "scripts" / "demo.py", "demo")
        self.assertEqual((ROOT / "assets" / "demo.svg").read_text(), demo.render(), "run python3 scripts/demo.py")
        self.assertIn('<img src="assets/demo.svg"', (ROOT / "README.md").read_text())
        self.assertIn(demo.CAPTION, (ROOT / "README.md").read_text())
        ET.fromstring(demo.render())

    def test_both_sides_use_the_one_protocol_module(self):
        shared = load(ROOT / "protocol.py", "shared_protocol")
        claude = load(ROOT / "claude" / "skills" / "grok-bridge" / "bridge.py", "claude_side")
        grok = load(ROOT / "grok" / "bridge.py", "grok_side")
        self.assertEqual((claude.A2A_STATE, grok.A2A_STATE, claude.PROTOCOL, grok.PROTOCOL), (shared.A2A_STATE,) * 2 + (shared.PROTOCOL,) * 2)
        for name in ("claude/skills/grok-bridge/bridge.py", "grok/bridge.py"):
            self.assertNotIn("TASK_STATE_", (ROOT / name).read_text(), f"{name} must not redefine shared facts")
        for status, state in shared.A2A_STATE.items():
            self.assertIn(f"`{status}`", (ROOT / "PROTOCOL.md").read_text())
            self.assertIn(f"`{state}`", (ROOT / "PROTOCOL.md").read_text())

    def test_inbox_dedupes_by_the_envelope_own_id(self):
        prompt = (ROOT / "claude" / "inbox.md").read_text()
        self.assertIn("named `grok-bridge reply <id>`", prompt.replace("\n      ", " "))
        self.assertNotIn("grok-bridge reply <in_reply_to", prompt, "two answers to one question share in_reply_to")
        self.assertIn("duplicate <trigger id>", prompt)
        self.assertIn("include_completed true", prompt, "ended triggers must be visible to dedupe and cleanup")

    def test_json_files_parse(self):
        for p in tracked_files():
            if p.suffix == ".json":
                json.loads(p.read_text())

    def test_no_secrets_committed(self):
        pattern = re.compile(r"sk-ant-oat01-[A-Za-z0-9_-]{20,}|crsr_[A-Za-z0-9]{20,}")
        hits = [str(p.relative_to(ROOT)) for p in tracked_files() if p.parent.name != "tests" and pattern.search(p.read_text(errors="ignore"))]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
