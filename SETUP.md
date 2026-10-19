# Setup: one line

Send your Grok Bot agent this one line:

```text
Set up the Claude Code bridge: follow https://github.com/francoCosimo95/claude-grok-bridge/blob/main/grok/BOOTSTRAP.md
```

That's it. You do nothing else. The agent, by itself (`grok/BOOTSTRAP.md`):
1. installs the bridge on its box and, through the Claude CLI signed in there (your Claude
   account), finds or **creates** your "Grok bridge inbox" routine;
2. creates a **polling routine** (zero-touch: it collects what Claude Code sessions send it), an
   optional webhook routine (fast lane), and a **"Claude Code"** plugin (connector + skill) that
   you see in "Manage plugins and skills";
3. on your Mac, through Grok Bot's local exec, installs the Claude Code skill and registers
   itself (no secrets needed; if it can read its webhook key it also sets up the fast lane);
4. runs a self-test and answers `PONG` back into Claude;
5. tells you "Bridge ready" and how quickly it picks up messages.

Then in any Claude Code session: "ask CoS ...", "tell CoS to ...", "did CoS answer?".

What the agent needs, and asks you for only if missing:
- the Claude CLI signed in on its box (`claude /login`);
- local exec on your Mac; without it, you paste one line in the Terminal (no values to type).

Speed: zero-touch messages reach the agent within its poll interval (the shortest schedule its
platform allows; the agent tells you the number). Answers come back in about 30 seconds. With
the fast lane, messages reach the agent in about a second.

Cost: each poll is one short Claude CLI call on the agent's box, and each message or answer is a
short inbox run on your Claude plan (30 per hour per routine).

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
- The agent cannot create plugins: the bridge still works through its routine; you can add the
  connector by hand (stdio command `python3 /workspace/claude-grok-bridge/grok/mcp_server.py`).

## Cloud sessions

Cloud sessions send in zero-touch mode with no key at all: they run the inbox routine through
their built-in `Claude_Code_Remote` connector, and answers are pushed back into them. They only
need the skill (in the repository's `.claude/skills/`, or a plugin). The fast lane in a cloud
session would need the Grok webhook key in that environment (`GROK_BRIDGE_<PEER>_URL` /
`GROK_BRIDGE_<PEER>_AUTH`); only do that if your rules allow it.

## Session id

A cloud session finds its own id in `CLAUDE_CODE_REMOTE_SESSION_ID` and puts it in
`reply_to.session_id` so the answer is pushed into it. Local sessions read answers from the
inbox.

## Rotating

- Grok webhook key: regenerate it on the agent's routine, then ask the agent to rerun bootstrap
  step 3.
- Inbox token (token mode only): Regenerate on the routine's API trigger, give the new one to
  the agent.
