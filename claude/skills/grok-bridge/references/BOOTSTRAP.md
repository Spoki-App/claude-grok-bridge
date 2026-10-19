# Bootstrap: instructions for the Grok Bot agent

Your owner sent you one line asking you to follow this file. Do every step yourself and only
ask your owner if a step is impossible for you. Names used below:
- `AGENT`: your own agent name (for example CoS). `PEER`: the same in lowercase (`cos`).
- `OWNER`: your human owner's first name.
- `REPO`: https://github.com/francoCosimo95/claude-grok-bridge (or the fork your owner named).

## 1. Install on your box

```bash
git clone REPO /workspace/claude-grok-bridge || git -C /workspace/claude-grok-bridge pull
python3 /workspace/claude-grok-bridge/grok/reply_to_claude.py --discover
```

`--discover` uses the Claude CLI signed in on your box (your owner's Claude account) to find
the "Grok bridge inbox" routine, **creating it if it does not exist**, and saves its id in
`grok/bridge.local.json`. If your owner gave you an inbox id, run `--discover --inbox <id>`.
Then:

```bash
python3 /workspace/claude-grok-bridge/grok/reply_to_claude.py --check
```

Expect a `trig_...` inbox id, mode `cli`, `claude_cli_found: true`. If the Claude CLI is
missing on your box, install it (`npm install -g @anthropic-ai/claude-code`). If it is not
signed in, ask your owner to sign it in (`claude /login`, their Claude account). Then retry.

## 2. Create your routine

Create a routine named **"Claude Code bridge"** with a **webhook** trigger. Its prompt is the
text block in `/workspace/claude-grok-bridge/grok/ROUTINE_PROMPT.md`, with `<AGENT>` and
`<OWNER>` replaced.

## 3. Wire Claude to you (on your owner's Mac, through local exec)

If you cannot run commands on your owner's Mac, skip to the end of this step.

1. If `~/.claude/skills/grok-bridge` does not exist:
   `git clone REPO ~/claude-grok-bridge || git -C ~/claude-grok-bridge pull`, then
   `ln -s ~/claude-grok-bridge/claude/skills/grok-bridge ~/.claude/skills/grok-bridge`.
2. Read your new routine's **Webhook URL** and **Authorization** header value and pipe them as
   JSON `{"webhook_url": "...", "authorization": "..."}` into:
   `python3 -I ~/.claude/skills/grok-bridge/scripts/add_peer.py --peer PEER --name AGENT --inbox <inbox id> --stdin`
   Never write those two values in a chat, in any other file, or in a log.

No local exec, or you cannot read the two values: ask your owner to run this one command in
their terminal and paste the two values when asked (hidden input):
`curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh -s -- --peer PEER --name AGENT --inbox <inbox id>`

## 4. Self-test (on your owner's Mac, through local exec; else ask your owner to run it)

```bash
python3 -I ~/.claude/skills/grok-bridge/scripts/send_to_grok.py --peer PEER --hello
```

Expect HTTP 2xx. Your "Claude Code bridge" routine then fires with a question asking for the
word PONG and answers it through `reply_to_claude.py` (expect HTTP 200 there).

## 5. Report

Tell your owner in one line: "bridge ready", or which step failed and why.
