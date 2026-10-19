#!/bin/sh
# Claude side install for claude-grok-bridge, for machines where the Grok agent cannot run local exec.
# Usage: curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh -s -- --peer cos --name CoS --inbox trig_...
set -e
REPO="${CGB_REPO:-https://github.com/francoCosimo95/claude-grok-bridge}"
DIR="${CGB_DIR:-$HOME/claude-grok-bridge}"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q; else git clone -q "$REPO" "$DIR"; fi
mkdir -p "$HOME/.claude/skills"
[ -e "$HOME/.claude/skills/grok-bridge" ] || ln -s "$DIR/claude/skills/grok-bridge" "$HOME/.claude/skills/grok-bridge"
echo "Skill installed at ~/.claude/skills/grok-bridge"
if [ "$#" -gt 0 ]; then
  python3 -I "$DIR/claude/skills/grok-bridge/scripts/add_peer.py" "$@" < /dev/tty
fi
