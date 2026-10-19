#!/usr/bin/env python3
"""Grok Bot side: deliver a claude-grok-bridge/1 answer to Claude Code by firing the Claude inbox routine.

Two delivery modes, picked automatically:
  token  CLAUDE_BRIDGE_INBOX_TOKEN is set: documented routine fire API with that routine's token.
  cli    otherwise: the Claude Code CLI already signed in on this box runs the inbox routine
         (RemoteTrigger tool). No extra secret needed.
The inbox logs the answer and, if reply_to.session_id is set, pushes it into that cloud session.

Inbox routine id (not a secret): env CLAUDE_BRIDGE_INBOX_ROUTINE, or "inbox_routine" in
grok/bridge.local.json next to this script.

Usage:
  python3 reply_to_claude.py --discover [--inbox trig_...]
  python3 reply_to_claude.py --check
  python3 reply_to_claude.py --question envelope.json --agent CoS --status answered --answer "text"
  python3 reply_to_claude.py --in-reply-to q-123 --session-id session_... --agent CoS --answer-file answer.txt
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{routine}/fire"
PROTOCOL = "claude-grok-bridge/1"
MAX_TEXT = 60_000
STATUSES = ["answered", "accepted", "escalated", "needs_confirmation", "done", "declined"]
TOKENISH = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")
LOCAL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.local.json")
VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
INBOX_DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "claude", "INBOX_ROUTINE.md")
CLI_PROMPT = (
    "Use the RemoteTrigger tool exactly once: action \"run\", trigger_id \"{routine}\", body "
    "{{\"text\": <the JSON string below, passed verbatim as a string>}}. Do nothing else. Then reply "
    "with only the HTTP status line the tool returned.\n\n{text}"
)
DISCOVER_PROMPT = """You are setting up or updating claude-grok-bridge on this Claude account. Use only the
RemoteTrigger tool, the Read tool and the schedule skill. Do nothing else.
Read {inbox_doc}: it has the create body and, under "Inbox prompt", the prompt text (the fenced
block). Its first line is a version marker like "claude-grok-bridge inbox vX.Y.Z.".
1. RemoteTrigger action "list". If an enabled routine named exactly "Grok bridge inbox" exists:
   if its prompt does not start with that same marker line, call RemoteTrigger "update" on it,
   setting job_config.ccr.events to one user event whose content is the doc's prompt (keep its
   environment_id and session_context). Then reply with only its id (trig_...) and stop.
2. Otherwise create it from the doc. For environment_id, load the schedule skill to see this
   account's environments and pick the one named "Default" (else the first). Generate a fresh
   lowercase UUID for the event. Then call RemoteTrigger "update" on the new routine so
   mcp_connections contains only the Claude_Code_Remote connector, exactly as the doc says.
3. Reply with only the routine id (trig_...), or NONE and one short reason if you could not."""


def version():
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def inbox_routine():
    routine = os.environ.get("CLAUDE_BRIDGE_INBOX_ROUTINE")
    if not routine and os.path.exists(LOCAL_CONFIG):
        with open(LOCAL_CONFIG) as f:
            routine = json.load(f).get("inbox_routine")
    if not routine or not routine.startswith("trig_"):
        sys.exit(f"inbox routine id missing: set CLAUDE_BRIDGE_INBOX_ROUTINE or inbox_routine in {LOCAL_CONFIG}")
    return routine


def build_answer(args):
    in_reply_to, session_id = args.in_reply_to, args.session_id
    if args.question:
        with open(args.question) as f:
            q = json.load(f)
        if q.get("protocol") != PROTOCOL or q.get("type") not in ("question", "request", "note"):
            sys.exit("not a claude-grok-bridge/1 envelope")
        in_reply_to = in_reply_to or q.get("id")
        session_id = session_id or (q.get("reply_to") or {}).get("session_id")
    if not in_reply_to:
        sys.exit("--in-reply-to or --question is required")
    answer = args.answer
    if args.answer_file:
        with open(args.answer_file) as f:
            answer = f.read().strip()
    if not answer:
        sys.exit("empty answer")
    return {
        "protocol": PROTOCOL,
        "type": "answer",
        "id": f"a-{uuid.uuid4().hex[:12]}",
        "in_reply_to": in_reply_to,
        "from": {"kind": "grok-bot", "agent": args.agent, "version": version()},
        "status": args.status,
        "answer": answer,
        "reply_to": {"session_id": session_id or None},
        "sent_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def fire_with_token(routine, token, text):
    req = urllib.request.Request(
        FIRE_URL.format(routine=routine),
        data=json.dumps({"text": text}).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, resp.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read(4000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        status, body = 0, f"network error: {e}"
    return 200 <= status < 300, status, TOKENISH.sub("<redacted>", body.replace(token, "<redacted>"))


def fire_with_cli(routine, text):
    claude = shutil.which("claude")
    if not claude:
        return False, 0, "claude CLI not found on this box; set CLAUDE_BRIDGE_INBOX_TOKEN instead"
    cmd = [claude, "-p", CLI_PROMPT.format(routine=routine, text=text), "--allowedTools", "RemoteTrigger", "--output-format", "text"]
    model = os.environ.get("CLAUDE_BRIDGE_CLI_MODEL", "haiku")
    if model:
        cmd += ["--model", model]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False, 0, "claude CLI timed out"
    body = TOKENISH.sub("<redacted>", (out.stdout or out.stderr).strip())[-2000:]
    m = re.search(r"HTTP (\d{3})", body)
    status = int(m.group(1)) if m else 0
    return out.returncode == 0 and 200 <= status < 300, status, body


def fire(envelope):
    routine = inbox_routine()
    text = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_TEXT:
        sys.exit(f"envelope too large ({len(text)} chars, max {MAX_TEXT})")
    token = os.environ.get("CLAUDE_BRIDGE_INBOX_TOKEN")
    return fire_with_token(routine, token, text) if token else fire_with_cli(routine, text)


def discover(given):
    routine = given
    if not routine:
        claude = shutil.which("claude")
        if not claude:
            sys.exit("claude CLI not found on this box; pass --inbox trig_... instead")
        prompt = DISCOVER_PROMPT.format(inbox_doc=INBOX_DOC)
        cmd = [claude, "-p", prompt, "--allowedTools", "RemoteTrigger", "Read", "Skill", "--output-format", "text", "--model", "sonnet"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            sys.exit("claude CLI timed out while looking for the inbox routine")
        m = re.search(r"\btrig_[A-Za-z0-9]+\b", out.stdout or "")
        if not m:
            said = TOKENISH.sub("<redacted>", (out.stdout or out.stderr).strip())[-300:]
            sys.exit(f"could not find or create the 'Grok bridge inbox' routine. Is the claude CLI signed in (claude /login)? CLI said: {said}")
        routine = m.group(0)
    with open(LOCAL_CONFIG, "w") as f:
        json.dump({"inbox_routine": routine}, f)
    return routine


def check():
    token = bool(os.environ.get("CLAUDE_BRIDGE_INBOX_TOKEN"))
    try:
        routine = inbox_routine()
    except SystemExit as e:
        routine = f"MISSING: {e}"
    return {
        "version": version(),
        "protocol": PROTOCOL,
        "inbox_routine": routine,
        "mode": "token" if token else "cli",
        "claude_cli_found": bool(shutil.which("claude")),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--discover", action="store_true", help="find (or create) the owner's 'Grok bridge inbox' routine and save its id")
    ap.add_argument("--inbox", help="with --discover: use this trig_... id instead of looking it up")
    ap.add_argument("--question", help="path to the envelope JSON being answered")
    ap.add_argument("--in-reply-to")
    ap.add_argument("--session-id")
    ap.add_argument("--agent", help="your agent name, e.g. CoS")
    ap.add_argument("--status", default="answered", choices=STATUSES)
    ap.add_argument("--answer")
    ap.add_argument("--answer-file")
    args = ap.parse_args()
    if args.version:
        print(f"claude-grok-bridge {version()} (protocol {PROTOCOL})")
        return
    if args.discover:
        print(f"inbox_routine={discover(args.inbox)} saved to {LOCAL_CONFIG}")
        return
    if args.check:
        print(json.dumps(check()))
        return
    if not args.agent:
        ap.error("--agent is required")
    ok, status, body = fire(build_answer(args))
    print(f"HTTP {status}")
    print(body)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
