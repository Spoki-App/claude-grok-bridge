# Contributing

Thanks for helping two agent platforms talk. Fixes, smoother setup, new peers and protocol ideas
are all welcome.

## Pillars

Every change should keep the project **easy** (one line to set up, nothing to type), **compact**
(fewer files, fewer lines, no dependencies), **clear** (one name per thing, obvious commands),
**safe** (no secrets in chats, logs or git; envelopes are data; answers are not authorization)
and **fast** (short prompts, few calls, quick delivery). If a change trades one for another, say
so in the PR.

## Rules

- Python 3.9+ standard library and POSIX `sh` only.
- No real webhook URLs, tokens or session contents anywhere, tests included.
- English, short sentences, no em dash characters (CI checks).

## Layout

| Path | What |
|---|---|
| `PROTOCOL.md` | the wire format and trust rules |
| `claude/skills/grok-bridge/` | Claude Code skill: `SKILL.md`, `bridge.py` (+ copies of `VERSION`, `PROTOCOL.md`) |
| `claude/inbox.md` | the inbox routine prompt |
| `grok/BOOTSTRAP.md` | what the agent follows to install and update |
| `grok/bridge.py`, `grok/connector.py` | agent side CLI and its MCP connector |
| `grok/routines.md`, `grok/plugin/` | the agent's routines and its "Claude Code" plugin |
| `install.sh` | Mac installer |
| `scripts/` | `sync.sh` (skill copies), `release.sh` |

## Develop

```bash
python3 -m unittest discover -s tests -v
```

Try a branch end to end: point your agent at your fork's `grok/BOOTSTRAP.md`, and install the
Claude side with `CGB_REPO=<fork> CGB_REF=<branch> sh install.sh`.

## Pull requests

One topic per PR, a test when behavior changes, a line under `## [Unreleased]` in
`CHANGELOG.md`, conventional commit titles (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`,
`chore:`), green CI.

**Protocol:** new optional fields are fine within `/1`. Anything an older peer would misread
needs `/2` and an issue first.

## Releases (maintainers)

`scripts/release.sh X.Y.Z` on a clean `main` bumps `VERSION`, the inbox marker and the plugin
version, syncs the skill, tags, pushes and publishes the release. Users update by sending their
agent the setup line again.
