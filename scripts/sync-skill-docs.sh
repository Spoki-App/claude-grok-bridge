#!/bin/sh
# Copy the canonical docs into the skill so the skill folder works on its own (cloud repos, plugins).
set -e
cd "$(dirname "$0")/.."
cp PROTOCOL.md SETUP.md claude/INBOX_ROUTINE.md grok/BOOTSTRAP.md claude/skills/grok-bridge/references/
cp VERSION claude/skills/grok-bridge/VERSION
echo "synced"
