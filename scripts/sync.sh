#!/bin/sh
# The skill ships its own VERSION, PROTOCOL.md and protocol.py so it works when copied anywhere;
# the agent side gets protocol.py too. Edit the root copies only.
set -e
cd "$(dirname "$0")/.."
cp VERSION PROTOCOL.md protocol.py claude/skills/grok-bridge/
cp protocol.py grok/
