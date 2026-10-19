#!/usr/bin/env python3
"""Grok Bot side: deliver a claude-grok-bridge/1 answer to Claude Code.

Fires the Claude Code inbox routine (documented routine API). If the question carried
reply_to.session_id, the inbox pushes the answer into that cloud session as a new turn.

Env (set through Grok Bot's masked secret input, never in chat):
  CLAUDE_BRIDGE_INBOX_ROUTINE   trig_... id of the inbox routine
  CLAUDE_BRIDGE_INBOX_TOKEN     the inbox routine's API token (sk-ant-oat01-...)

Usage:
  python3 reply_to_claude.py --question question.json --agent CoS --status answered --answer-file answer.txt
  python3 reply_to_claude.py --in-reply-to q-123 --session-id session_... --agent CoS --answer "text"
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid

FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{routine}/fire"
PROTOCOL = "claude-grok-bridge/1"
MAX_TEXT = 60_000
STATUSES = ["answered", "accepted", "escalated", "needs_confirmation", "done", "declined"]
TOKENISH = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")


def build_answer(args):
    in_reply_to, session_id = args.in_reply_to, args.session_id
    if args.question:
        with open(args.question) as f:
            q = json.load(f)
        if q.get("protocol") != PROTOCOL or q.get("type") != "question":
            sys.exit("not a claude-grok-bridge/1 question")
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
        "from": {"kind": "grok-bot", "agent": args.agent},
        "status": args.status,
        "answer": answer,
        "reply_to": {"session_id": session_id},
        "sent_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def fire(envelope):
    routine, token = os.environ.get("CLAUDE_BRIDGE_INBOX_ROUTINE"), os.environ.get("CLAUDE_BRIDGE_INBOX_TOKEN")
    if not routine or not token:
        sys.exit("CLAUDE_BRIDGE_INBOX_ROUTINE and CLAUDE_BRIDGE_INBOX_TOKEN must be set")
    text = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_TEXT:
        sys.exit(f"envelope too large ({len(text)} chars, max {MAX_TEXT})")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", help="path to the question envelope JSON")
    ap.add_argument("--in-reply-to")
    ap.add_argument("--session-id")
    ap.add_argument("--agent", required=True, help="your agent name, e.g. CoS")
    ap.add_argument("--status", default="answered", choices=STATUSES)
    ap.add_argument("--answer")
    ap.add_argument("--answer-file")
    args = ap.parse_args()
    ok, status, body = fire(build_answer(args))
    print(f"HTTP {status}")
    print(body)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
