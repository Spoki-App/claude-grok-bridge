#!/bin/sh
set -e
cd "$(dirname "$0")/.."
NEW="$1"
MODE="${2:-}"
echo "$NEW" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "usage: scripts/release.sh X.Y.Z [finish]"; exit 1; }
BRANCH="release/v$NEW"

notes_for() {
  if [ -n "$2" ]; then git show "$2:CHANGELOG.md"; else cat CHANGELOG.md; fi |
    awk -v heading="## [$1]" 'index($0, heading) == 1 {f=1; next} /^## \[/ {f=0} f' | sed '/^[[:space:]]*$/d'
}

pr_field() {
  gh pr list --state all --head "$BRANCH" --json number,state,mergeCommit --jq ".[0].$1 // empty"
}

retry() {
  limit="$1"; shift
  tries=0
  until "$@"; do
    tries=$((tries + 1))
    [ "$tries" -le "$limit" ] || return 1
    sleep 5
  done
}

merge_commit_known() {
  SHA="$(pr_field mergeCommit.oid)"
  [ -n "$SHA" ]
}

merge_commit_fetched() {
  git fetch -q --tags origin && git cat-file -e "$SHA^{commit}" 2>/dev/null
}

wait_for_ci() {
  tries=0
  while :; do
    count="$(gh pr checks "$BRANCH" --json name --jq length 2>/dev/null)" || true
    [ "${count:-0}" -gt 0 ] && break
    tries=$((tries + 1))
    [ "$tries" -le 30 ] || { echo "no CI checks on $BRANCH after 5 minutes. Then: scripts/release.sh $NEW finish"; exit 1; }
    sleep 10
  done
  gh pr checks "$BRANCH" --watch --interval 15 || { echo "CI failed on $BRANCH. Fix it, then: scripts/release.sh $NEW finish"; exit 1; }
}

finish() {
  [ -n "$(pr_field number)" ] || { echo "no pull request for $BRANCH"; exit 1; }
  if [ "$(pr_field state)" != "MERGED" ]; then
    wait_for_ci
    gh pr merge "$BRANCH" --squash --delete-branch
  fi
  retry 12 merge_commit_known || { echo "GitHub reports no merge commit for $BRANCH yet. Then: scripts/release.sh $NEW finish"; exit 1; }
  retry 12 merge_commit_fetched || { echo "merge commit $SHA not on origin yet. Then: scripts/release.sh $NEW finish"; exit 1; }
  git checkout -q main
  git merge -q --ff-only origin/main
  if ! git rev-parse -q --verify "refs/tags/v$NEW" >/dev/null; then
    git tag -a "v$NEW" "$SHA" -m "v$NEW"
    git push -q origin "v$NEW"
  fi
  if ! gh release view "v$NEW" >/dev/null 2>&1; then
    notes_for "$NEW" "$SHA" | gh release create "v$NEW" install.sh --title "v$NEW" --notes-file -
  fi
  echo "released v$NEW at $SHA"
}

if [ "$MODE" = "finish" ]; then
  finish
  exit 0
fi

[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "start from main"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
git fetch -q --tags origin
git merge -q --ff-only origin/main
git rev-parse -q --verify "refs/tags/v$NEW" >/dev/null && { echo "tag v$NEW exists"; exit 1; }
NOTES="$(notes_for Unreleased)"
[ -n "$NOTES" ] || { echo "CHANGELOG.md: add notes under ## [Unreleased] first"; exit 1; }
git checkout -q -b "$BRANCH"
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
git add -A && git commit -q -m "chore(release): v$NEW"
git push -q -u origin "$BRANCH"
printf 'Release v%s.\n\n%s\n' "$NEW" "$NOTES" | gh pr create --base main --head "$BRANCH" --title "chore(release): v$NEW" --body-file -
finish
