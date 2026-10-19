# Setup

About 15 minutes, once per Claude account and once per Grok Bot agent. Every secret is entered
by a human in a masked field or a chmod 600 file, never pasted into a chat.

## A. Claude side (once per Claude account)

1. **Inbox routine.** Ask any Claude Code session: "create the grok-bridge inbox routine from
   `claude/INBOX_ROUTINE.md`". It creates a no-schedule routine and trims its connectors to
   `Claude_Code_Remote` only. Note the `trig_...` id.
2. **API token for the inbox.** claude.ai/code/routines, open "Grok bridge inbox", Edit, Add
   another trigger, API, Generate token. It is shown once: keep it for step B4.
3. **Skill.** Clone this repo and link the skill:
   ```bash
   git clone https://github.com/<you>/claude-grok-bridge ~/claude-grok-bridge
   ```
   ```bash
   ln -s ~/claude-grok-bridge/claude/skills/grok-bridge ~/.claude/skills/grok-bridge
   ```
   For cloud sessions, add the same folder to the repository's `.claude/skills/` (or ship it in a
   plugin).

## B. Grok Bot side (once per agent)

1. **Install.** Tell the agent: "Clone https://github.com/<you>/claude-grok-bridge into
   /workspace/claude-grok-bridge, create a venv there and `pip install mcp`."
2. **Connector.** Grok Bot, Connectors, add a custom connector, type **MCP server (stdio
   command)**, name `claude-code`, command
   `/workspace/claude-grok-bridge/.venv/bin/python /workspace/claude-grok-bridge/grok/mcp_server.py`.
   Tools: `check_bridge`, `read_envelope`, `reply_to_claude`.
3. **Routine.** Create the "Claude Code question" routine with a **webhook** trigger and the
   prompt in `grok/ROUTINE_PROMPT.md` (the agent can create its own routines: paste the file and
   ask it to). Copy the routine's **Webhook URL** and **Authorization** value for step C.
4. **Secrets.** Through Grok Bot's masked secret input: `CLAUDE_BRIDGE_INBOX_ROUTINE` (the
   `trig_...` id from A1) and `CLAUDE_BRIDGE_INBOX_TOKEN` (the token from A2). Then ask the agent
   to run `check_bridge`: both flags must be true.

## C. Tell Claude how to reach the agent

On each machine that runs local Claude Code sessions:

```bash
mkdir -p ~/.config/grok-bridge && chmod 700 ~/.config/grok-bridge
```

Write `~/.config/grok-bridge/config.json` with an editor (shape in
`examples/config.example.json`): the inbox routine id, and per agent its webhook URL and
Authorization value. Then:

```bash
chmod 600 ~/.config/grok-bridge/config.json
```

```bash
python3 -I ~/.claude/skills/grok-bridge/scripts/send_to_grok.py --check --peer cos
```

For cloud sessions, set `GROK_BRIDGE_<PEER>_URL`, `GROK_BRIDGE_<PEER>_AUTH` and
`GROK_BRIDGE_INBOX_ROUTINE` on the claude.ai/code environment, only if your team's rules allow
a low-privilege key there. The key can only wake that one routine, and the agent treats what it
receives as untrusted data.

## Session id

A cloud session finds its own id in `CLAUDE_CODE_REMOTE_SESSION_ID` (`cse_...`, the same session
as `session_...`). Put it in `reply_to.session_id` so the answer is pushed into the session.
Local sessions have no such id: they read answers from the inbox.

## Rotating

- Grok webhook key: regenerate it on the agent's routine, update `config.json` / env.
- Inbox token: Regenerate on the routine's API trigger (revokes the old one), update the agent's
  secret.
