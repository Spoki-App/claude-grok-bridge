#!/bin/sh
# Cut a release: scripts/release.sh 0.2.0
# Requires a clean tree on main and a "## [Unreleased]" section in CHANGELOG.md with the notes.
set -e
cd "$(dirname "$0")/.."
NEW="$1"
echo "$NEW" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "usage: scripts/release.sh X.Y.Z"; exit 1; }
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "release from main only"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
git fetch -q --tags
git rev-parse -q --verify "refs/tags/v$NEW" >/dev/null && { echo "tag v$NEW exists"; exit 1; }
OLD="$(cat VERSION)"
TODAY="$(date -u +%Y-%m-%d)"
NOTES="$(awk '/^## \[Unreleased\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md | sed '/^[[:space:]]*$/d')"
[ -n "$NOTES" ] || { echo "CHANGELOG.md: add notes under ## [Unreleased] first"; exit 1; }
echo "$NEW" > VERSION
python3 - "$NEW" "$TODAY" <<'PY'
import pathlib, re, sys
new, today = sys.argv[1], sys.argv[2]
c = pathlib.Path("CHANGELOG.md"); s = c.read_text()
c.write_text(s.replace("## [Unreleased]\n", f"## [Unreleased]\n\n## [{new}] - {today}\n", 1))
pj = pathlib.Path("plugins/claude-code/.cursor-plugin/plugin.json")
pj.write_text(re.sub(r'"version": "\d+\.\d+\.\d+"', f'"version": "{new}"', pj.read_text()))
p = pathlib.Path("claude/INBOX_ROUTINE.md"); s = p.read_text()
p.write_text(re.sub(r"claude-grok-bridge inbox v\d+\.\d+\.\d+", f"claude-grok-bridge inbox v{new}", s))
PY
./scripts/sync-skill-docs.sh >/dev/null
git add -A
git commit -q -m "chore(release): v$NEW"
git tag -a "v$NEW" -m "v$NEW"
git push -q origin main "v$NEW"
printf '%s\n' "$NOTES" | gh release create "v$NEW" --title "v$NEW" --notes-file -
echo "released v$NEW (was v$OLD)"
