#!/bin/sh
# claude-grok-bridge: Claude side install / update for this Mac.
# Usage: curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh -s -- --peer cos --name CoS --inbox trig_...
# Without arguments it only installs or updates the skill. CGB_REF=main installs the dev branch.
set -e
REPO="${CGB_REPO:-https://github.com/francoCosimo95/claude-grok-bridge}"
DIR="${CGB_DIR:-$HOME/claude-grok-bridge}"
if [ -t 1 ]; then B="$(printf '\033[1m')"; G="$(printf '\033[32m')"; R="$(printf '\033[0m')"; else B=""; G=""; R=""; fi

step() { printf '\n%s%s%s\n' "$B" "$1" "$R"; }

step "claude-grok-bridge: setting up Claude Code on this Mac"
command -v git >/dev/null || { echo "git is missing: install Xcode command line tools (xcode-select --install) and run this again."; exit 1; }
command -v python3 >/dev/null || { echo "python3 is missing: install it (xcode-select --install) and run this again."; exit 1; }

step "Step 1 of 2: download the latest release"
if [ -d "$DIR/.git" ]; then git -C "$DIR" fetch -q --tags origin; else git clone -q "$REPO" "$DIR"; fi
REF="${CGB_REF:-$(git -C "$DIR" tag -l 'v*' --sort=-v:refname | head -n 1)}"
[ -n "$REF" ] || REF=main
OLD="$(cat "$DIR/VERSION" 2>/dev/null || echo none)"
git -C "$DIR" -c advice.detachedHead=false checkout -q "$REF"
[ "$REF" = "main" ] && git -C "$DIR" pull -q --ff-only origin main
NEW="$(cat "$DIR/VERSION")"
mkdir -p "$HOME/.claude/skills"
[ -e "$HOME/.claude/skills/grok-bridge" ] || ln -s "$DIR/claude/skills/grok-bridge" "$HOME/.claude/skills/grok-bridge"
if [ "$OLD" = "$NEW" ]; then echo "${G}OK${R} version $NEW (already up to date)"; else echo "${G}OK${R} version $NEW (was $OLD)"; fi

if [ "$#" -eq 0 ]; then
  step "Done. The Claude Code skill is installed and up to date."
  exit 0
fi

step "Step 2 of 2: connect to your Grok Bot agent"
python3 -I "$DIR/claude/skills/grok-bridge/scripts/add_peer.py" "$@" < /dev/tty
