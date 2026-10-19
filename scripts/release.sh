#!/bin/sh
# Cut a release from a clean main: scripts/release.sh 0.6.0
# Notes come from "## [Unreleased]" in CHANGELOG.md.
set -e
cd "$(dirname "$0")/.."
NEW="$1"
echo "$NEW" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "usage: scripts/release.sh X.Y.Z"; exit 1; }
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "release from main only"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
git fetch -q --tags
git rev-parse -q --verify "refs/tags/v$NEW" >/dev/null && { echo "tag v$NEW exists"; exit 1; }
NOTES="$(awk '/^## \[Unreleased\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md | sed '/^[[:space:]]*$/d')"
[ -n "$NOTES" ] || { echo "CHANGELOG.md: add notes under ## [Unreleased] first"; exit 1; }
python3 - "$NEW" "$(date -u +%Y-%m-%d)" <<'PY'
import pathlib, re, sys
new, today = sys.argv[1], sys.argv[2]
def sub(path, pattern, repl):
    p = pathlib.Path(path); p.write_text(re.sub(pattern, repl, p.read_text(), count=1))
pathlib.Path("VERSION").write_text(new + "\n")
sub("CHANGELOG.md", r"## \[Unreleased\]\n", f"## [Unreleased]\n\n## [{new}] - {today}\n")
sub("claude/inbox.md", r"claude-grok-bridge inbox v\d+\.\d+\.\d+", f"claude-grok-bridge inbox v{new}")
sub("grok/plugin/.cursor-plugin/plugin.json", r'"version": "\d+\.\d+\.\d+"', f'"version": "{new}"')
sub("claude/.claude-plugin/plugin.json", r'"version": "\d+\.\d+\.\d+"', f'"version": "{new}"')
PY
./scripts/sync.sh
git add -A && git commit -q -m "chore(release): v$NEW" && git tag -a "v$NEW" -m "v$NEW"
git push -q origin main "v$NEW"
printf '%s\n' "$NOTES" | gh release create "v$NEW" install.sh --title "v$NEW" --notes-file -
echo "released v$NEW"
