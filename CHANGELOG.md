# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/) for the kit. The wire protocol has its own version
(`claude-grok-bridge/1`) and only changes when compatibility breaks.

## [Unreleased]

## [0.4.0] - 2026-10-19

### Added
- **Zero-touch mode, now the default.** Claude Code sessions send through the inbox routine with
  the login they already have; the agent collects its messages with a scheduled
  `reply_to_claude.py --poll`. No webhook values to paste, and cloud sessions can send with no key.
  The webhook stays as an optional fast lane.
- `reply_to_claude.py --self-test`, `add_peer.py --inbox-mode` (keeps an existing fast lane).

### Fixed
- Answers sent through the Claude CLI could reach the inbox without their payload (seen once in
  production). Delivery is now verified from the raw tool output and retried once.
- The inbox pushes only messages from Grok agents, so a question from a cloud session is never
  pushed back into the session that asked it.

### Changed
- The Claude CLI calls use `sonnet` by default (`CLAUDE_BRIDGE_CLI_MODEL` to override).

## [0.3.0] - 2026-10-19

### Added
- Open source project setup: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue and PR
  templates.
- Test suite (`tests/`, standard library only) and CI on Linux and macOS: unit tests for every
  script, MCP handshake, em dash check, skill docs sync, version consistency, secret scan.

## [0.2.0] - 2026-10-19

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
