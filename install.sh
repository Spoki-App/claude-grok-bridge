#!/bin/sh
# claude-grok-bridge: install or update the Claude Code skill on this Mac (latest release).
#   curl -fsSL https://github.com/Spoki-App/claude-grok-bridge/releases/latest/download/install.sh | sh
# Extra arguments register a Grok agent, e.g.: | sh -s -- ava --name Ava --inbox trig_... --inbox-mode
set -e
REPO="${CGB_REPO:-https://github.com/Spoki-App/claude-grok-bridge}"
DIR="${CGB_DIR:-$HOME/claude-grok-bridge}"
SKILL="$HOME/.claude/skills/grok-bridge"
command -v git >/dev/null && command -v python3 >/dev/null || { echo "Needs git and python3: run xcode-select --install, then this again."; exit 1; }

echo "claude-grok-bridge: installing the Claude Code skill"
if [ -d "$DIR/.git" ]; then git -C "$DIR" fetch -q --tags origin; else git clone -q "$REPO" "$DIR"; fi
REF="${CGB_REF:-$(git -C "$DIR" tag -l 'v*' --sort=-v:refname | head -n 1)}"
git -C "$DIR" -c advice.detachedHead=false checkout -q "${REF:-main}"
mkdir -p "$HOME/.claude/skills"
if [ -L "$SKILL" ] || [ ! -e "$SKILL" ]; then
  ln -sfn "$DIR/claude/skills/grok-bridge" "$SKILL"
  echo "OK version $(cat "$DIR/VERSION")"
else
  echo "WARNING: $SKILL is a real folder, not replaced. Remove it and run this again to update."
fi

[ "$#" -eq 0 ] && exit 0
case " $* " in
  *" --inbox-mode "*|*" --stdin "*) exec python3 -I "$SKILL/bridge.py" add-peer "$@" ;;
  *) exec python3 -I "$SKILL/bridge.py" add-peer "$@" < /dev/tty ;;  # hidden prompts need the terminal
esac
