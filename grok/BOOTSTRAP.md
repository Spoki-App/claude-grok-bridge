# Bootstrap and update: instructions for the Grok Bot agent

Your owner sent you one line asking you to follow this file. The same line installs and
updates: every step below is safe to run again. Goal: your owner does **nothing** else. No
copy and paste, no commands, no values.

## How to talk to your owner while doing this

Your owner is probably not technical. In every message during setup:
- Start with where you are: "Step 2 of 5: ...". One or two plain sentences.
- Do every step yourself. Never ask your owner for something you can do.
- End with exactly one line, in bold: **Nothing to do, I'm on it.** or, only if truly
  unavoidable, **Next step for you:** with one concrete action (what to open, what to click).
- Speak your owner's language.

Names: `AGENT` is your name (for example CoS), `PEER` the same in lowercase (`cos`), `OWNER` your
owner's first name, `REPO` https://github.com/francoCosimo95/claude-grok-bridge (or the fork your
owner named).

## Step 1 of 5: install or update on your box

```bash
D=/workspace/claude-grok-bridge
[ -d $D/.git ] && git -C $D fetch -q --tags origin || git clone -q REPO $D
git -C $D -c advice.detachedHead=false checkout -q "$(git -C $D tag -l 'v*' --sort=-v:refname | head -n1)"
python3 $D/grok/reply_to_claude.py --version
python3 $D/grok/reply_to_claude.py --discover
python3 $D/grok/reply_to_claude.py --check
```

This pins you to the latest release. `--discover` uses the Claude CLI signed in on your box
(your owner's Claude account) to find the "Grok bridge inbox" routine, **create it if missing,
and update its prompt if it is from an older release**. `--check` must show a `trig_...` id and
`claude_cli_found: true`.
- Claude CLI missing: install it (`npm install -g @anthropic-ai/claude-code`) and retry.
- Not signed in: this is the one thing you cannot do alone. **Next step for you:** sign in to
  Claude on my box (tell them exactly how your box lets them run `claude /login`).

## Step 2 of 5: your routines and your "Claude Code" plugin

All prompts are in `/workspace/claude-grok-bridge/grok/ROUTINE_PROMPT.md`; replace `<AGENT>`,
`<OWNER>`, `<PEER>`. Create each one if missing, or reset its prompt on update.

1. **"Claude Code bridge poll"**: scheduled, at the **shortest interval Grok Bot allows**. This is
   the zero-touch path: Claude Code sessions drop messages in the inbox and you collect them.
   Note the interval you set: you report it in step 5.
2. **"Claude Code bridge"**: webhook trigger. Optional fast lane, used only if step 3 can store
   its URL and key on your owner's Mac.
3. **Plugin "Claude Code"** in your owner's "Manage plugins and skills", the same way you create
   your other plugins (for example google-chat):
   - connector: stdio command `python3 /workspace/claude-grok-bridge/grok/mcp_server.py`
     (no dependencies; tools `check_bridge`, `read_envelope`, `reply_to_claude`, `message_claude`);
   - skill: `/workspace/claude-grok-bridge/plugins/claude-code/skills/claude-code-bridge/SKILL.md`;
   - description and version: from `plugins/claude-code/.cursor-plugin/plugin.json`.
   If your plugin tooling installs from GitHub marketplaces, this repo is one
   (`.cursor-plugin/marketplace.json`, plugin `claude-code`). Then call `check_bridge` through it.
   If you cannot create plugins, say so in one line and continue: the routines work without it.

## Step 3 of 5: your owner's Mac (through local exec)

1. Install or update the Claude Code skill:
   `curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh`
2. Register yourself in zero-touch mode (no secrets involved):
   `python3 -I ~/claude-grok-bridge/claude/skills/grok-bridge/scripts/add_peer.py --peer PEER --name AGENT --inbox <inbox id> --inbox-mode`
3. Fast lane, only if you can read your webhook routine's **Webhook URL** and **Authorization**
   value: pipe them as JSON `{"webhook_url": "...", "authorization": "..."}` into the same
   command with `--stdin` instead of `--inbox-mode`. Never write those values in a chat, another
   file, or a log. If you cannot read them, skip this: zero-touch already works.

No local exec on your owner's Mac? Then the only step left for them is installing the skill:
**Next step for you:** open the Terminal app, paste this line, press Enter. Nothing else.

```bash
curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh -s -- --peer PEER --name AGENT --inbox <inbox id> --inbox-mode
```

## Step 4 of 5: self-test

1. From your box: `python3 /workspace/claude-grok-bridge/grok/reply_to_claude.py --self-test --peer PEER`
   (expect HTTP 200, "delivered and verified").
2. Run your "Claude Code bridge poll" routine now (or wait for it). It must find the
   `q-selftest-...` question and you answer `PONG` with `reply_to_claude.py` (expect HTTP 200,
   "delivered and verified").
3. If you configured the fast lane, also run on the Mac:
   `python3 -I ~/.claude/skills/grok-bridge/scripts/send_to_grok.py --peer PEER --hello`
   (expect HTTP 2xx) and answer that PONG too.

## Step 5 of 5: report

One short message: "Bridge ready (version X.Y.Z). Claude Code sessions reach me within N
minutes" (N = your poll interval; add "or seconds through the fast lane" if configured). Then
two examples your owner can type in Claude Code: `ask AGENT whether ...` and
`tell AGENT to ...`. End with **Nothing to do, the bridge is ready.** If a step failed, say
which one, why, and the one next step.
