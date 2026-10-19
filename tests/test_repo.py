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

    def test_skill_references_are_in_sync(self):
        pairs = {"PROTOCOL.md": "PROTOCOL.md", "SETUP.md": "SETUP.md", "claude/INBOX_ROUTINE.md": "INBOX_ROUTINE.md", "grok/BOOTSTRAP.md": "BOOTSTRAP.md"}
        refs = ROOT / "claude" / "skills" / "grok-bridge" / "references"
        for src, ref in pairs.items():
            self.assertEqual((ROOT / src).read_text(), (refs / ref).read_text(), f"run scripts/sync-skill-docs.sh ({src})")
        self.assertEqual((ROOT / "VERSION").read_text(), (ROOT / "claude/skills/grok-bridge/VERSION").read_text())

    def test_versions_agree(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        plugin = json.loads((ROOT / "plugins/claude-code/.cursor-plugin/plugin.json").read_text())
        self.assertEqual(plugin["version"], version)
        self.assertIn(f"claude-grok-bridge inbox v{version}.", (ROOT / "claude/INBOX_ROUTINE.md").read_text())
        self.assertIn(f"## [{version}]", (ROOT / "CHANGELOG.md").read_text())

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
