# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/) for the kit. The wire protocol has its own version
(`claude-grok-bridge/1`) and only changes when compatibility breaks.

## [Unreleased]

### Added
- Grok Bot plugin **"Claude Code"** (`plugins/claude-code/`): connector + skill, created by the
  agent during setup like its other plugins, and listed in a `.cursor-plugin` marketplace.
- Connector tool `message_claude`: the agent can message a Claude Code cloud session on its own
  initiative.

### Changed
- The connector is now a dependency-free stdio MCP server (no venv, no `pip install`).

### Fixed
- Accept an Authorization value pasted with its `Authorization:` header prefix (Grok Bot copies
  it that way); stripped on save and on send.

## [0.1.0] - 2026-10-19

### Added
- Protocol `claude-grok-bridge/1`: `question`, `request` (relayed from the owner with
  `owner_words`), `note`, `answer`; statuses `answered`, `accepted`, `escalated`,
  `needs_confirmation`, `done`, `declined`; trust rules.
- Claude Code skill `grok-bridge` with `send_to_grok.py` (`--hello`, `--check`, `--peers`,
  `--version`) and `add_peer.py` (hidden input or `--stdin`).
- Claude inbox routine: logs every message, pushes answers into the asking cloud session as a
  system notification, cleans up its one-off reminders.
- Grok side: `reply_to_claude.py` (Claude CLI on the box, or routine API token),
  `--discover` finds or creates the inbox and keeps its prompt in sync, optional stdio MCP
  connector `claude-code`, routine prompt.
- One-line setup and update: the Grok agent follows `grok/BOOTSTRAP.md`; `install.sh` fallback
  for Macs without Grok local exec.
- Release tooling: `VERSION`, this changelog, `scripts/release.sh`.
