# Setup: one paste

You do one thing: paste a message to your Grok Bot agent. Claude and the agent do the rest.

## 1. In Claude Code

Say: **"set up the grok bridge for CoS"** (any agent name). If the skill is not installed yet,
install it first (or let the agent do it in step 2):

```bash
git clone https://github.com/francoCosimo95/claude-grok-bridge ~/claude-grok-bridge && ln -s ~/claude-grok-bridge/claude/skills/grok-bridge ~/.claude/skills/grok-bridge
```

Claude creates the **inbox routine** on your Claude account (or reuses it) and prints the
bootstrap message with every id filled in.

## 2. In Grok Bot: paste the message

The agent, by itself (`grok/BOOTSTRAP.md`):
1. clones the repo on its box and checks it can answer through the Claude CLI already signed in
   there (no new token);
2. creates its "Claude Code bridge" routine with a webhook trigger;
3. on your Mac, through Grok Bot's local exec, installs the skill if missing and writes the
   routine's webhook URL and key into `~/.config/grok-bridge/config.json` (chmod 600), never
   in the chat;
4. runs a self-test: a question from your Mac to itself, answered PONG back into Claude;
5. tells you "bridge ready".

It only comes back to you if a step is impossible for it (for example it cannot read its own
webhook key: then you run one command and paste the two values in hidden input).

## Fallbacks

- No Claude CLI on the agent's box: generate an API token on the inbox routine
  (claude.ai/code/routines, Edit, Add another trigger, API, Generate token) and give it to the
  agent as `CLAUDE_BRIDGE_INBOX_TOKEN` through its masked secret input.
- Manual peer config: `python3 -I ~/.claude/skills/grok-bridge/scripts/add_peer.py --peer cos --name CoS --inbox <trig id>`
  (hidden prompts).
- Optional connector: register `grok/mcp_server.py` as a stdio MCP connector named `claude-code`
  for typed tools (`check_bridge`, `read_envelope`, `reply_to_claude`).

## Cloud sessions

Cloud sessions receive answers automatically (pushed into the session). To let them also
**send**, the skill folder must be in the repo's `.claude/skills/` and the Grok webhook key must
reach them, for example as `GROK_BRIDGE_<PEER>_URL` / `GROK_BRIDGE_<PEER>_AUTH` on the
claude.ai/code environment. Only do this if your rules allow a low-privilege key there: it can
only wake that one Grok routine, and the agent treats what it receives as untrusted data.

## Session id

A cloud session finds its own id in `CLAUDE_CODE_REMOTE_SESSION_ID` and puts it in
`reply_to.session_id` so the answer is pushed into it. Local sessions read answers from the
inbox.

## Rotating

- Grok webhook key: regenerate it on the agent's routine, then ask the agent to rerun bootstrap
  step 3.
- Inbox token (token mode only): Regenerate on the routine's API trigger, give the new one to
  the agent.
