# Bootstrap message for a Grok Bot agent

The only thing a human does: paste this message to the Grok Bot agent. The Claude Code skill
fills the placeholders for you ("set up the grok bridge for CoS"):
`{{REPO}}`, `{{INBOX_ROUTINE}}`, `{{AGENT}}`, `{{PEER}}`, `{{OWNER}}`.

```text
Set up claude-grok-bridge so Claude Code sessions can talk to you. Repo: {{REPO}}
Do every step yourself; only ask me if a step is impossible for you.

1. On your box: clone the repo into /workspace/claude-grok-bridge (pull if it exists). Write
   /workspace/claude-grok-bridge/grok/bridge.local.json as {"inbox_routine": "{{INBOX_ROUTINE}}"}.
   Run: python3 /workspace/claude-grok-bridge/grok/reply_to_claude.py --check
   Expect mode "cli" with claude_cli_found true (the Claude CLI already signed in on your box).
   If the CLI is missing, tell me: I will give you an inbox token instead.
2. Create a routine named "Claude Code bridge" with a webhook trigger. Its prompt is the block
   in /workspace/claude-grok-bridge/grok/ROUTINE_PROMPT.md with <AGENT> = {{AGENT}} and
   <OWNER> = {{OWNER}}.
3. Give Claude the way to reach you, on my Mac through local exec:
   a. If ~/.claude/skills/grok-bridge does not exist: git clone {{REPO}} ~/claude-grok-bridge
      (pull if it exists) and ln -s ~/claude-grok-bridge/claude/skills/grok-bridge ~/.claude/skills/grok-bridge
   b. Read your new routine's Webhook URL and Authorization header value, and pipe them as JSON
      {"webhook_url": "...", "authorization": "..."} into
      python3 -I ~/.claude/skills/grok-bridge/scripts/add_peer.py --peer {{PEER}} --name {{AGENT}} --inbox {{INBOX_ROUTINE}} --stdin
      Never write those two values in our chat, in a file other than that config, or in a log.
      If you cannot read them, tell me to run that command without --stdin and paste them
      myself (hidden input).
4. Self-test, on my Mac through local exec: write this to /tmp/cgb-hello.json and run
   python3 -I ~/.claude/skills/grok-bridge/scripts/send_to_grok.py --peer {{PEER}} --envelope /tmp/cgb-hello.json
   {"protocol":"claude-grok-bridge/1","type":"question","id":"q-bootstrap-hello","from":{"kind":"claude-code","label":"bootstrap self-test"},"to":"{{PEER}}","subject":"Bridge self-test","question":"Reply with the single word PONG.","reply_to":{"session_id":null}}
   Expect HTTP 2xx. Your "Claude Code bridge" routine then fires and answers PONG through
   reply_to_claude.py; expect HTTP 200 there too.
5. Tell me in one line: bridge ready (or which step failed and why).
```
