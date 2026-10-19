#!/bin/sh
# Copy the canonical docs into the skill so the skill folder works on its own (cloud repos, plugins).
set -e
cd "$(dirname "$0")/.."
cp PROTOCOL.md SETUP.md claude/skills/grok-bridge/references/
echo "synced"
