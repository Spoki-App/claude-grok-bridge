# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/) for the kit. The wire protocol has its own version
(`claude-grok-bridge/1`) and only changes when compatibility breaks.

## [Unreleased]

## [0.12.0] - 2026-10-19

### Changed
- Faster and cheaper polling: the agent's poll runs on the small model (`haiku`, override with
  `CLAUDE_BRIDGE_POLL_MODEL`), since it only lists runs and reads logs.
- Setup never recreates an existing webhook routine (a new one breaks the owner's fast lane), and
  relaxes the poll to every 15 minutes when the fast lane works: the poll is then a safety net.
- When the fast lane is off, the agent's final report and `bridge.py check` say how to turn it on.

## [0.11.0] - 2026-10-19

### Changed
- One `protocol.py` holds what both sides share (protocol name, types, statuses, A2A states, size
  and id rules, validation); `scripts/sync.sh` copies it next to each `bridge.py`.
- Both sides validate envelopes before sending, and the agent's poll keeps only valid ones; ids
  must be plain (letters, digits, `.`, `-`, `_`), since they name triggers and files.

### Fixed
- Agent envelopes now always carry `to` (`claude-code`); answers from the agent had none.

### Security
- SECURITY.md states the trust boundary for relayed owner requests and why they are not signed.

## [0.10.0] - 2026-10-19

### Added
- `add-peer --no-claude-md` skips the agents block in `~/.claude/CLAUDE.md`; when it writes it,
  it shows the line and how to undo it.
- `bridge.py peers` prints a `FOR_REPO_CLAUDE_MD` line for a repository's `CLAUDE.md`, so cloud
  sessions know the agent's name too.

### Changed
- README: says which Grok Bot this is, what the bridge relies on (preview or undocumented), and
  what stays compatible before 1.0.

## [0.9.2] - 2026-10-19

### Fixed
- Agent side: the transcript audit crashed when an event's `message` was text, not an object
  (reported by CoS during the 0.9.1 setup).
- Claude side: if the fast lane fails (for example its webhook routine was deleted), the message
  goes through the inbox instead of failing (`FAST_LANE_FAILED ...` then `SEND_VIA_INBOX`).

### Added
- `add-peer --inbox-mode --no-fast-lane` forgets a webhook that no longer exists; the setup tells
  the agent to use it when it recreated its webhook routine and cannot read the new values.

### Verified
- The channel works live: with the development flag, a message left by `bridge.py drop`
  appears in an open terminal session within seconds (Claude Team org, Claude Code 2.1.303).

## [0.9.1] - 2026-10-19

### Fixed
- The inbox lists triggers with `include_completed` and pages back 24 hours, so dedupe and
  cleanup also see ended triggers whatever order the listing returns.

## [0.9.0] - 2026-10-19

### Added
- **A2A vocabulary.** Answers carry `state`, the `status` as an A2A `TaskState`
  (`TASK_STATE_COMPLETED`, `TASK_STATE_WORKING`, `TASK_STATE_INPUT_REQUIRED`,
  `TASK_STATE_REJECTED`); `thread` is the A2A `contextId`. Mapping in PROTOCOL.md.
- **No double delivery.** The inbox names push and ask triggers by the message's own id and
  skips a message it already delivered (`BRIDGE_PUSH: duplicate ...`), so sender retries are safe.
  Two answers to one question (accepted, then done) both arrive.
- **Agents by any name.** `add-peer` keeps a marked block in `~/.claude/CLAUDE.md` naming your
  agents, so "ask Ava" (whatever you named it) reaches the skill in every session. Examples are generic.
- **Channel (experimental).** A Claude Code channel in the plugin: the agent drops its answer on
  your Mac (`bridge.py drop`, through local exec) and an open terminal session shows it at once.
  Needs the channels development flag during the research preview; not yet verified live.

### Changed
- README use cases are chat images (Grok black, Claude orange), generated from
  `scripts/chats.py`; a test keeps them in sync.

## [0.8.0] - 2026-10-19

### Added
- **Agents can ask Claude Code.** `grok/bridge.py ask` (connector tool `ask_claude_code`) sends a
  question `to: "claude-code"`; the inbox schedules a one-off routine (`grok-bridge ask <id>`)
  that investigates read-only and writes the answer as its final reply; the agent's poll reads it
  there (verified live: question in, answer read back). With `--session`, the
  question goes into a running session instead, which replies with the new Claude side command
  `bridge.py answer`.
- **Both sides know the bridge.** The agent's "Claude Code" skill triggers on "ask Claude Code" /
  "chiedi a Claude Code"; setup asks the agent to remember the channel; the Claude skill knows how
  to answer an agent.

### Changed
- Answering sessions call no tool to reply: in scheduled sessions every connector call waits for
  a human approval, so the answer is their final reply and the agent's poll (now also allowed the
  read-only `list` action) collects it. The inbox keeps `grok-bridge ask` routines for 24 hours.

### Fixed
- **Safety:** the inbox routine's `allowed_tools` was empty, which means the full default tool
  set. It is now `["TodoWrite"]` plus an explicit deny list (shell, writes, web, sub-agents).
  Reading stays allowed, so answering sessions, which inherit the list, can look at code.

## [0.7.0] - 2026-10-19

### Added
- **Native Claude Code plugin** `grok-bridge`: the repo is a Claude Code marketplace
  (`/plugin install grok-bridge --marketplace francoCosimo95/claude-grok-bridge`). Cloud sessions
  get it through the repository's `.claude/settings.json`, no files to copy. Validated with
  `claude plugin validate --strict`.
- **Threads.** Optional `thread` field (id of the first message): `ask/tell/note --thread <id>`;
  answers keep it; the agent archives messages both ways and reads `bridge.py thread <id>` before
  answering a follow-up.
- **Any agent platform.** The inbox pushes answers from any `from.kind` other than `claude-code`;
  `CLAUDE_BRIDGE_AGENT_KIND` names the agent's platform (default `grok-bot`).

### Changed
- The skill finds `bridge.py` next to its own SKILL.md, so it works as a plugin, a linked skill or
  a repo skill.

## [0.6.0] - 2026-10-19

Fixes from an independent review (Fable), checked against the five pillars.

### Fixed
- **No lost messages in poll.** It now also reads the fire payload (so a run still executing is
  not missed), keeps a 10 minute overlap (ids dedupe), and only advances when the poll completed.
- **No duplicate deliveries.** When the payload is not yet in the log, the same run is read
  again before firing a second time.
- **Connector trust label** can no longer be overridden by the envelope (`read_envelope` nests it).
- The inbox **cleanup never deletes a reminder that has not fired** yet.
- `setup` accepts only a reply that is exactly one routine id.
- `install.sh`: `--stdin` works through the pipe, and a real folder in place of the skill is
  reported instead of a green "OK".
- `--ref` without `=` is a clear error, not a traceback. The CLI never waits on stdin.

### Security
- **Least privilege for the models in the loop.** Every Claude CLI call is audited from its
  transcript: any RemoteTrigger action outside the expected ones (poll: list and read only) fails
  the call with an alert.
- **The inbox has no shell.** It keeps one harmless tool and denies the rest explicitly (an empty
  allowed list would mean the default set, shell included). It reads the time from its system
  reminder.
- **Installs come from the release**, not `main`: `install.sh` is a release asset, fetched from
  `releases/latest/download/install.sh`.
- Envelopes poll into a private folder next to the install, not shared `/tmp`.

### Changed
- In zero-touch mode the Claude side prints a ready `BODY {"text": ...}` and the tool to use
  (`via=`), so the session does not hand-escape JSON.
- README: use cases as short chats; PROTOCOL documents the known limits.

## [0.5.0] - 2026-10-19

Rebuilt around five pillars: easy, compact, clear, safe, fast. **Breaking for installs**: send
your Grok agent the setup line again; it migrates routines and paths.

### Changed
- Claude side is one script, `claude/skills/grok-bridge/bridge.py`, with `ask`, `tell`, `note`,
  `hello`, `send`, `check`, `peers`, `version`, `add-peer`. It builds envelopes itself: no JSON
  to write by hand.
- Agent side is `grok/bridge.py` (`setup`, `poll`, `reply`, `note`, `self-test`, `check`,
  `version`) and `grok/connector.py`; the plugin lives in `grok/plugin/`.
- One name for everything: routines "claude-grok-bridge inbox", "claude-grok-bridge poll",
  "claude-grok-bridge webhook"; skills `grok-bridge` (Claude side) and `claude-code` (agent side).
- Docs: SETUP merged into the README and BOOTSTRAP, duplicated copies removed (the skill keeps
  only `VERSION` and `PROTOCOL.md`), SKILL.md halved, PROTOCOL shorter with full examples.
- `setup` reads the inbox id from the CLI's final result only, and renames the old inbox routine.

### Fixed
- `install.sh` repairs a broken skill symlink and works without a terminal (zero-touch installs
  by the agent).

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
