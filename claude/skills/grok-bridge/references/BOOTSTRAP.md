# Bootstrap and update: instructions for the Grok Bot agent

Your owner sent you one line asking you to follow this file. The same line is used to install
and to update: every step below is safe to run again.

## How to talk to your owner while doing this

Your owner is probably not technical. In every message during setup:
- Start with where you are: "Step 2 of 5: ...". Keep it to one or two plain sentences.
- Do every step yourself. Never ask your owner for something you can do.
- End with exactly one line, in bold: **Next step for you:** followed by one concrete action
  (what to open, what to click, what to paste, where), or **Nothing to do, I'm on it.**
- When you need them to run a command, give the command alone in a code block, say where to
  run it (the Terminal app on their Mac), what it will ask, and where to find each value.
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
and update its prompt if it is from an older release**. `--check` must show a `trig_...` id,
mode `cli`, `claude_cli_found: true`.
- Claude CLI missing: install it (`npm install -g @anthropic-ai/claude-code`) and retry.
- Not signed in: **Next step for you:** sign in on my box (tell them how your box lets them run
  `claude /login`), then tell me "done".

## Step 2 of 5: your routine

If you have no routine named **"Claude Code bridge"**, create it with a **webhook** trigger. Set
(or reset, on update) its prompt to exactly the "Routine prompt" block in
`/workspace/claude-grok-bridge/grok/ROUTINE_PROMPT.md`, with `<AGENT>` and `<OWNER>` replaced.
That prompt reads the installed instructions at run time, so later updates need no edit here.

## Step 3 of 5: connect your owner's Mac

Through local exec on your owner's Mac, if you have it:
1. Install or update the skill: run
   `curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh`
2. If you can read your routine's **Webhook URL** and **Authorization** value, pipe them as JSON
   `{"webhook_url": "...", "authorization": "..."}` into
   `python3 -I ~/claude-grok-bridge/claude/skills/grok-bridge/scripts/add_peer.py --peer PEER --name AGENT --inbox <inbox id> --stdin`
   Never write those values in a chat, another file, or a log.

If you have no local exec or cannot read the two values (on update, skip this if
`send_to_grok.py --check --peer PEER` already says CONFIG_OK), your message ends with:

**Next step for you:** open the Terminal app on your Mac, paste this command, press Enter, and
follow the 2 questions it asks (it tells you where to find each value; what you paste stays
hidden). Then come back here and write "done".

```bash
curl -fsSL https://raw.githubusercontent.com/francoCosimo95/claude-grok-bridge/main/install.sh | sh -s -- --peer PEER --name AGENT --inbox <inbox id>
```

Right under it, give your owner the two values as clickable references if your interface can
(Webhook URL, Authorization), never as plain text in the chat.

## Step 4 of 5: self-test

On your owner's Mac (local exec, or ask them to run it the same way as step 3):

```bash
python3 -I ~/.claude/skills/grok-bridge/scripts/send_to_grok.py --peer PEER --hello
```

Expect HTTP 2xx. Your routine then fires with a question asking for the word PONG; answer it
through `reply_to_claude.py` and expect HTTP 200.

## Step 5 of 5: report

One short message: "Bridge ready (version X.Y.Z)." Then tell your owner what they can do now,
with two examples to type in Claude Code: `ask AGENT whether ...` and `tell AGENT to ...`.
End with **Nothing to do, the bridge is ready.** If a step failed, say which one, why, and the
one next step.
