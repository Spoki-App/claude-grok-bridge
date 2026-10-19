#!/bin/sh
# The skill ships its own VERSION and PROTOCOL.md so it works when copied anywhere.
set -e
cd "$(dirname "$0")/.."
cp VERSION PROTOCOL.md claude/skills/grok-bridge/
