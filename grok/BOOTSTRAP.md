# Setup and update (for the Grok Bot agent)

Your owner sent you one line pointing here. The same line installs and updates; every step is
safe to repeat. Goal: your owner does **nothing**. No copy and paste, no commands, no values.

**How to talk to your owner:** start each message with "Step N of 5", one or two plain
sentences, in their language. End with **Nothing to do, I'm on it.** Only if truly unavoidable,
end with **Next step for you:** and one concrete action.

Names: `AGENT` is your name (e.g. Ava), `PEER` the same in lowercase, `OWNER` your owner's first
name, `REPO` https://github.com/francoCosimo95/claude-grok-bridge.

## Step 1 of 5: install or update on your box

```bash
D=/workspace/claude-grok-bridge
[ -d $D/.git ] && git -C $D fetch -q --tags origin || git clone -q REPO $D
git -C $D -c advice.detachedHead=false checkout -q "$(git -C $D tag -l 'v*' --sort=-v:refname | head -n1)"
python3 $D/grok/bridge.py setup && python3 $D/grok/bridge.py check
```

This pins you to the latest release. `setup` uses the Claude CLI signed in on your box (your
owner's Claude account) to find or create the "claude-grok-bridge inbox" routine and keep its
prompt current. `check` must show a `trig_...` inbox and `claude_cli_found: true`.
- No Claude CLI: `npm install -g @anthropic-ai/claude-code`, then retry.
- Not signed in: the one thing you cannot do alone. **Next step for you:** sign in to Claude on
  my box (say exactly how, on your box, they run `claude /login`).

## Step 2 of 5: routines and plugin

Prompts are in `/workspace/claude-grok-bridge/grok/routines.md`. Create each if missing, or reset
its prompt. Delete routines from older releases named "Claude Code bridge" or
"Claude Code bridge poll".
1. **"claude-grok-bridge poll"**: scheduled at the shortest interval allowed. Note the interval.
2. **"claude-grok-bridge webhook"**: webhook trigger, the optional fast lane.
3. **Plugin "Claude Code"**, created the way you create your other plugins: connector = stdio
   command `python3 /workspace/claude-grok-bridge/grok/connector.py`; skill =
   `grok/plugin/skills/claude-code/SKILL.md`; metadata = `grok/plugin/.cursor-plugin/plugin.json`
   (this repo is also a `.cursor-plugin` marketplace). Call `check_bridge` through it. If you
   cannot create plugins, say so in one line and go on: the routines work without it.

## Step 3 of 5: your owner's Mac (through local exec)

```bash
curl -fsSL https://github.com/francoCosimo95/claude-grok-bridge/releases/latest/download/install.sh | sh -s -- PEER --name AGENT --inbox <inbox id> --inbox-mode
```

This installs or updates the Claude Code skill and registers you in zero-touch mode (no secrets).
Fast lane, only if you can read your webhook routine's URL and Authorization value: pipe
`{"webhook_url": "...", "authorization": "..."}` into
`python3 -I ~/.claude/skills/grok-bridge/bridge.py add-peer PEER --name AGENT --stdin`.
Never put those values in a chat or a message (they stay only in your own tool history). No local exec? **Next step for you:** open the
Terminal app, paste the line above, press Enter.

## Step 4 of 5: self-test

1. `python3 /workspace/claude-grok-bridge/grok/bridge.py self-test --peer PEER` must print
   `"delivered": true`.
2. Run your poll routine now. It must find the `q-selftest-...` question; answer `PONG` per the
   Instructions (`"delivered": true`).
3. Fast lane configured? Also run on the Mac
   `python3 -I ~/.claude/skills/grok-bridge/bridge.py hello --to PEER` and answer that PONG.

**Remember the bridge.** Add to your own standing instructions or memory, in one line: "I can
talk with my owner's Claude Code through claude-grok-bridge: to ask Claude Code something, use
the Claude Code plugin (`ask_claude_code`) or `bridge.py ask`." Then when your owner says
"ask Claude Code ...", you know how.

## Step 5 of 5: report

"Bridge ready (version X.Y.Z). Claude Code reaches me within N minutes" (N = your poll interval;
add "or seconds through the fast lane" if set). Then three examples: in Claude Code
`ask AGENT whether ...` and `tell AGENT to ...`; and to you, "ask Claude Code ...". End with **Nothing to do, the bridge is ready.**
If a step failed: which one, why, and the one next step.
