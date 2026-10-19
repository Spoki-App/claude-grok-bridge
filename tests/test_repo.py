import json
import re
import subprocess
import unittest

from helpers import ROOT

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
        for name in ("VERSION", "PROTOCOL.md"):
            self.assertEqual((ROOT / name).read_text(), (skill / name).read_text(), f"run scripts/sync.sh ({name})")

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
