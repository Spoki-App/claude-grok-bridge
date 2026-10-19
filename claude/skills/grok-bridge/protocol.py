"""claude-grok-bridge/1: the facts both sides share. Edit here only; scripts/sync.sh copies this file
next to each bridge.py (claude/skills/grok-bridge/ and grok/). Standard library only."""

import json
import re

PROTOCOL = "claude-grok-bridge/1"
BODY_FIELD = {"question": "question", "request": "request", "note": "note", "answer": "answer"}
A2A_STATE = {  # each status as an A2A TaskState, sent as "state" so A2A tools can read answers
    "answered": "TASK_STATE_COMPLETED", "done": "TASK_STATE_COMPLETED", "accepted": "TASK_STATE_WORKING",
    "escalated": "TASK_STATE_WORKING", "needs_confirmation": "TASK_STATE_INPUT_REQUIRED", "declined": "TASK_STATE_REJECTED",
}
STATUSES = list(A2A_STATE)
MAX_BYTES = 60_000
ID_SHAPE = re.compile(r"[A-Za-z0-9_.-]{1,80}")  # ids name triggers and files


def problem(env):
    """Why an envelope is invalid, or None. Senders check before sending, so the inbox only ever
    sees well-formed messages; it still checks, since anyone with the fire API could send anything."""
    if not isinstance(env, dict) or env.get("protocol") != PROTOCOL or env.get("type") not in BODY_FIELD:
        return f"need protocol {PROTOCOL} and type question, request, note or answer"
    kind = env["type"]
    missing = [k for k in ("id", "from", "to", BODY_FIELD[kind]) if not env.get(k)]
    if missing:
        return f"missing {missing}"
    if not ID_SHAPE.fullmatch(str(env["id"])):
        return "id must be 1 to 80 letters, digits, dots, dashes or underscores"
    if kind == "answer" and (env.get("status") not in STATUSES or not env.get("in_reply_to")):
        return f"an answer needs in_reply_to and a status in {STATUSES}"
    if env.get("on_behalf_of") and (kind != "request" or not env.get("owner_words")):
        return "on_behalf_of only on a request, with owner_words"
    size = len(json.dumps(env, ensure_ascii=False, separators=(",", ":")).encode())
    if size > MAX_BYTES:
        return f"too large: {size} bytes, max {MAX_BYTES}"
    return None
