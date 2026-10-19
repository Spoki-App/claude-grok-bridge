# Setup: one line

Send your Grok Bot agent this one line:

```text
Set up the Claude Code bridge: follow https://github.com/francoCosimo95/claude-grok-bridge/blob/main/grok/BOOTSTRAP.md
```

That's it. The agent, by itself (`grok/BOOTSTRAP.md`):
1. clones the repo on its box and, through the Claude CLI signed in there (your Claude
   account), finds or **creates** your "Grok bridge inbox" routine;
2. creates its own "Claude Code bridge" routine with a webhook trigger;
3. on your Mac, through Grok Bot's local exec, installs the Claude Code skill and writes its
   webhook URL and key into `~/.config/grok-bridge/config.json` (chmod 600), never in a chat;
4. runs a self-test (a question from your Mac answered PONG back into Claude);
5. tells you "bridge ready".

Then in any Claude Code session: "ask CoS ...", "tell CoS to ...", "did CoS answer?".

What the agent needs, and asks you for only if missing:
- the Claude CLI signed in on its box (`claude /login`);
- local exec on your Mac; without it, you run one command it gives you (`install.sh`, hidden
  input for the two values).

## Updating

Send your Grok agent **the same line again**. Setup is idempotent: the agent moves its box to the
latest release, refreshes the inbox routine prompt if it changed, reinstalls the Claude skill on
your Mac, reruns the self-test and tells you the new version. Check what you have with:

```bash
python3 -I ~/.claude/skills/grok-bridge/scripts/send_to_grok.py --version
```

## Fallbacks

- The agent cannot use a Claude CLI at all: generate an API token on the inbox routine
  (claude.ai/code/routines, Edit, Add another trigger, API, Generate token) and give it to the
  agent as `CLAUDE_BRIDGE_INBOX_TOKEN` through its masked secret input.
- Manual install and peer config on a Mac:
  `curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh -s -- --peer cos --name CoS --inbox <trig id>`
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
