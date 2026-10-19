#!/usr/bin/env python3
"""claude-grok-bridge, Claude Code side. Standard library only.

  bridge.py ask   "Merge develop now?" [--to ava] [--context ...] [--option "A) ..."] [--recommend ...] [--ref pr=URL]
  bridge.py tell  "Move card 1234 to review" --owner-words "the user's exact words" [--to ava] [--context ...]
  bridge.py note  "PR 42 is merged" [--to ava]
  (any of them with --thread <first message id> continues a conversation)
  bridge.py answer Q_ID "text" --to ava [--status answered] [--thread ID]   answer an agent's question
  bridge.py hello [--to ava]                      self-test: asks the agent for PONG
  bridge.py send  envelope.json [--to ava]        send a prepared envelope
  bridge.py check [--to ava] | peers | version
  bridge.py add-peer ava --name Ava [--inbox trig_...] [--inbox-mode [--no-fast-lane] | --stdin]
  bridge.py drop < envelope.json                  the agent's local exec leaves a message for local sessions

Delivery: if the peer has a webhook (fast lane) it is POSTed and prints "SENT ... via=webhook".
Otherwise (zero-touch, the default) it prints "SEND_VIA_INBOX routine=... id=..." and an
"ENVELOPE {...}" line: the Claude session runs the inbox routine with that text.

Config: ~/.config/grok-bridge/config.json (chmod 600; or $GROK_BRIDGE_CONFIG), env overrides
GROK_BRIDGE_<PEER>_URL / _AUTH / GROK_BRIDGE_INBOX_ROUTINE. Secrets are never printed.
Exit codes: 0 ok, 2 config, 3 network or HTTP error, 4 invalid envelope.
"""

import argparse
import datetime
import getpass
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROTOCOL = "claude-grok-bridge/1"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/francoCosimo95/claude-grok-bridge"
DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".config", "grok-bridge", "config.json")
BODY_FIELD = {"question": "question", "request": "request", "note": "note", "answer": "answer"}
A2A_STATE = {  # each status as an A2A TaskState, sent as "state" so A2A tools can read answers
    "answered": "TASK_STATE_COMPLETED", "done": "TASK_STATE_COMPLETED", "accepted": "TASK_STATE_WORKING",
    "escalated": "TASK_STATE_WORKING", "needs_confirmation": "TASK_STATE_INPUT_REQUIRED", "declined": "TASK_STATE_REJECTED",
}
STATUSES = list(A2A_STATE)
MAX_BYTES = 60_000
AGENTS_BLOCK = re.compile(r"<!-- grok-bridge:agents -->.*?<!-- /grok-bridge:agents -->", re.S)
LONG_TOKEN = re.compile(r"[A-Za-z0-9_\-.]{24,}")
HEADER_PREFIX = re.compile(r"(?i)^\s*authorization\s*:\s*")


def fail(code, msg):
    print(msg)
    sys.exit(code)


def version():
    try:
        with open(os.path.join(HERE, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- config ----------

def config_path():
    return os.environ.get("GROK_BRIDGE_CONFIG", DEFAULT_CONFIG)


def load_config():
    path = config_path()
    if not os.path.exists(path):
        return {}
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        fail(2, f"CONFIG_INSECURE: {path} is readable by others ({oct(mode)}). Fix: chmod 600 {path}")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        fail(2, f"CONFIG_INVALID: cannot parse {path} ({type(e).__name__})")


def save_config(cfg):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.chmod(os.path.dirname(path), 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(path, 0o600)
    return path


def resolve(peer):
    cfg = load_config()
    key = re.sub(r"[^A-Z0-9]", "_", peer.upper())
    entry = (cfg.get("peers") or {}).get(peer, {})
    url = os.environ.get(f"GROK_BRIDGE_{key}_URL") or entry.get("webhook_url", "")
    auth = HEADER_PREFIX.sub("", os.environ.get(f"GROK_BRIDGE_{key}_AUTH") or entry.get("authorization", "")).strip()
    fast = url.startswith("https://") and bool(auth)
    return {
        "peer": peer,
        "name": entry.get("name", peer),
        "mode": "webhook" if fast else "inbox",
        "url": url,
        "auth": auth,
        "inbox": os.environ.get("GROK_BRIDGE_INBOX_ROUTINE") or cfg.get("inbox_routine", ""),
        "configured": bool(entry) or fast,
    }


def default_peer():
    peers = list((load_config().get("peers") or {}).keys())
    return peers[0] if len(peers) == 1 else None


# ---------- envelopes ----------

def envelope(kind, text, peer, args=None):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M")
    env = {
        "protocol": PROTOCOL,
        "type": kind,
        "id": f"{kind[0]}-{stamp}-{secrets.token_hex(2)}",
        "from": {"kind": "claude-code", "label": getattr(args, "label", None) or label(), "version": version()},
        "to": peer,
        BODY_FIELD[kind]: text,
        "reply_to": {"session_id": os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID") or None},
        "sent_at": now(),
    }
    if args is not None:
        for field in ("subject", "context", "recommendation", "thread"):
            if getattr(args, field, None):
                env[field] = getattr(args, field)
        if getattr(args, "option", None):
            env["options"] = args.option
        if getattr(args, "ref", None):
            bad = [item for item in args.ref if "=" not in item]
            if bad:
                fail(4, f"--ref needs key=value, got {bad}")
            env["refs"] = dict(item.split("=", 1) for item in args.ref)
        if getattr(args, "owner_words", None):
            env["on_behalf_of"], env["owner_words"] = "owner", args.owner_words
    return env


def label():
    where = "cloud" if os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID") else "local"
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5).stdout.strip()
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        top = branch = ""
    return f"{os.path.basename(top)} @ {branch} ({where})" if top else f"Claude Code ({where})"


def validate(env):
    kind = env.get("type")
    if env.get("protocol") != PROTOCOL or kind not in BODY_FIELD:
        fail(4, f"ENVELOPE_INVALID: need protocol {PROTOCOL} and type question, request, note or answer")
    missing = [k for k in ("id", "from", "to", BODY_FIELD[kind]) if not env.get(k)]
    if missing:
        fail(4, f"ENVELOPE_INVALID: missing {missing}")
    if kind == "answer" and (env.get("status") not in STATUSES or not env.get("in_reply_to")):
        fail(4, f"ENVELOPE_INVALID: an answer needs in_reply_to and a status in {STATUSES}")
    if env.get("on_behalf_of") and (kind != "request" or not env.get("owner_words")):
        fail(4, "ENVELOPE_INVALID: on_behalf_of only on a request, with owner_words")
    raw = json.dumps(env, ensure_ascii=False, separators=(",", ":"))
    if len(raw.encode()) > MAX_BYTES:
        fail(4, f"ENVELOPE_TOO_LARGE: {len(raw.encode())} bytes, max {MAX_BYTES}")
    return raw


# ---------- delivery ----------

def via_inbox(env, raw, target):
    cloud = bool(os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID"))
    tool = "Claude_Code_Remote fire_trigger" if cloud else "RemoteTrigger run"
    print(f"SEND_VIA_INBOX routine={target['inbox'] or 'FIND:claude-grok-bridge inbox'} id={env['id']} via={tool}")
    print("BODY " + json.dumps({"text": raw}, ensure_ascii=False))


def deliver(env, target):
    """Fast lane when configured; the inbox otherwise, and whenever the fast lane fails (a deleted or
    rotated webhook must not lose the message)."""
    if target["inbox"]:
        env.setdefault("reply_to", {}).setdefault("inbox_routine", target["inbox"])
    raw = validate(env)
    if target["mode"] == "inbox":
        return via_inbox(env, raw, target)
    url, auth = target["url"], target["auth"]
    req = urllib.request.Request(url, data=raw.encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, resp.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read(2000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        status, body = 0, "network error: " + str(e)
    body = LONG_TOKEN.sub("<redacted>", body.replace(url, "<url>").replace(auth, "<redacted>")).strip()
    if 200 <= status < 300:
        print(f"SENT id={env['id']} to={target['peer']} via=webhook (HTTP {status})")
        return
    print(f"FAST_LANE_FAILED {status or 'network'} {body[:200]}: sending through the inbox instead. "
          f"If it keeps failing, ask {target['name']} to run the setup line again.")
    via_inbox(env, raw, target)


# ---------- commands ----------

def cmd_message(args, kind):
    peer = args.to or default_peer() or fail(2, "Say which agent: --to <peer> (see: bridge.py peers)")
    text = " ".join(args.text)
    if kind == "request" and not args.owner_words:
        fail(4, "tell needs --owner-words with the user's exact words")
    deliver(envelope(kind, text, peer, args), resolve(peer))


def cmd_answer(args):
    peer = args.to or default_peer() or fail(2, "Say which agent: --to <peer>")
    env = envelope("answer", " ".join(args.text), peer, args)
    env["in_reply_to"], env["status"], env["state"] = args.in_reply_to, args.status, A2A_STATE[args.status]
    env["thread"] = args.thread or args.in_reply_to
    deliver(env, resolve(peer))


def cmd_hello(args):
    peer = args.to or default_peer() or fail(2, "Say which agent: --to <peer>")
    env = envelope("question", "Reply with the single word PONG.", peer)
    env["subject"], env["from"]["label"] = "Bridge self-test", "bridge self-test"
    deliver(env, resolve(peer))


def cmd_send(args):
    with open(args.file) as f:
        env = json.load(f)
    peer = args.to or env.get("to") or default_peer() or fail(2, "Say which agent: --to <peer>")
    env["to"] = peer
    if isinstance(env.get("from"), dict):
        env["from"].setdefault("version", version())
    deliver(env, resolve(peer))


def cmd_check(args):
    peer = args.to or default_peer() or fail(2, "Say which agent: --to <peer> (see: bridge.py peers)")
    t = resolve(peer)
    note = "" if t["configured"] else " (not configured here: messages go through the inbox)"
    print(f"CONFIG_OK peer={peer} name={t['name']} mode={t['mode']} inbox={t['inbox'] or 'FIND:claude-grok-bridge inbox'} version={version()}{note}")


def cmd_peers(_args):
    cfg = load_config()
    names = set((cfg.get("peers") or {}).keys())
    names |= {m.group(1).lower() for k in os.environ if (m := re.match(r"GROK_BRIDGE_(.+)_URL$", k))}
    print("PEERS " + (", ".join(sorted(names)) or "none"))
    print("INBOX " + (os.environ.get("GROK_BRIDGE_INBOX_ROUTINE") or cfg.get("inbox_routine") or "unset"))


def latest_release():
    try:
        out = subprocess.run(["git", "ls-remote", "--tags", "--refs", REPO_URL], capture_output=True, text=True, timeout=8).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    tags = [t for t in (line.rsplit("/v", 1)[-1] for line in out.splitlines()) if re.fullmatch(r"\d+\.\d+\.\d+", t)]
    return max(tags, key=lambda t: tuple(map(int, t.split(".")))) if tags else None


def cmd_version(_args):
    latest = latest_release()
    print(f"grok-bridge {version()} (protocol {PROTOCOL}), latest release {latest or 'unknown'}")
    if latest and latest != version():
        print("UPDATE_AVAILABLE: send your Grok agent the setup line again")


def cmd_add_peer(args):
    cfg = load_config()
    name = args.name or args.peer
    existing = (cfg.get("peers") or {}).get(args.peer) or {}
    if args.inbox_mode:
        keep = existing.get("webhook_url") and not args.no_fast_lane
        entry = {**existing, "name": name} if keep else {"name": name, "mode": "inbox"}
        if keep:
            print(f"Kept the existing fast lane for '{args.peer}'.")
        elif existing.get("webhook_url"):
            print(f"Removed the fast lane for '{args.peer}': messages go through the inbox.")
    else:
        url, auth = read_secrets(name) if not args.stdin else stdin_secrets()
        entry = {"name": name, "webhook_url": url, "authorization": auth}
    cfg.setdefault("peers", {})[args.peer] = entry
    if args.inbox:
        cfg["inbox_routine"] = args.inbox
    print(f"Saved '{args.peer}' to {save_config(cfg)} (only you can read it).")
    noted = remember_agents(cfg["peers"])
    if noted:
        print(f"Listed your agents in {noted}, so Claude Code knows their names.")
    if not args.stdin and not args.inbox_mode:
        print(f"\n  NEXT STEP: go back to {name}'s chat in Grok Bot and write \"done\".\n")


def drop_dir():
    return os.environ.get("GROK_BRIDGE_DROP_DIR") or os.path.join(os.path.dirname(config_path()), "drop")


def cmd_drop(_args):
    """Keep an agent's message where the grok-bridge channel of a running local session picks it up."""
    try:
        env = json.load(sys.stdin)
    except ValueError:
        fail(4, "ENVELOPE_INVALID: stdin is not JSON")
    if not isinstance(env, dict) or env.get("protocol") != PROTOCOL or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", str(env.get("id", ""))):
        fail(4, f"ENVELOPE_INVALID: needs protocol {PROTOCOL} and a plain id")
    if (env.get("from") or {}).get("kind") == "claude-code":
        fail(4, "ENVELOPE_INVALID: drop carries messages from an agent, not from Claude Code")
    folder = drop_dir()
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    for name in os.listdir(folder):
        if time.time() - os.path.getmtime(os.path.join(folder, name)) > 86400:
            os.remove(os.path.join(folder, name))
    fd = os.open(os.path.join(folder, env["id"] + ".json"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(env, f, ensure_ascii=False)
    print(f"DROPPED id={env['id']}")


def claude_md_path():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.environ.get("GROK_BRIDGE_CLAUDE_MD", os.path.join(base, "CLAUDE.md"))


def remember_agents(peers):
    """Keep one marked block in the user's CLAUDE.md naming their agents, so any name the user
    chose ("Ava", "CoS") reads as a Grok Bot agent in every Claude Code session."""
    path = claude_md_path()
    if not os.path.isdir(os.path.dirname(path)):
        return None
    names = ", ".join(f"{entry.get('name') or key} (`--to {key}`)" for key, entry in sorted(peers.items()))
    block = (f"<!-- grok-bridge:agents -->\nMy Grok Bot agents, reachable from Claude Code with the grok-bridge skill: "
             f"{names}.\n<!-- /grok-bridge:agents -->")
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    text = AGENTS_BLOCK.sub(lambda _m: block, text) if AGENTS_BLOCK.search(text) else text.rstrip("\n") + ("\n\n" if text.strip() else "") + block + "\n"
    with open(path, "w") as f:
        f.write(text)
    return path


def stdin_secrets():
    data = json.load(sys.stdin)
    url, auth = data.get("webhook_url", "").strip(), HEADER_PREFIX.sub("", data.get("authorization", "")).strip()
    if not url.startswith("https://") or not auth:
        fail(2, "stdin needs webhook_url (https) and authorization")
    return url, auth


def read_secrets(name):
    print(f"\nConnect Claude Code to {name}. In Grok Bot open {name}'s chat, click {name}'s name, Routines,")
    print('"claude-grok-bridge webhook", and copy its two values. What you paste stays hidden.\n')

    def ask(prompt, ok):
        for _ in range(3):
            value = HEADER_PREFIX.sub("", getpass.getpass(prompt)).strip()
            if ok(value):
                print("  OK")
                return value
            print("  That does not look right. Paste again, then press Enter.")
        fail(2, "Stopped after 3 attempts. Run the same command again.")

    return ask("1 of 2  Webhook URL: ", lambda v: v.startswith("https://")), ask("2 of 2  Authorization value: ", lambda v: len(v) >= 8)


def main():
    ap = argparse.ArgumentParser(prog="bridge.py", description="claude-grok-bridge, Claude Code side")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for kind, name, help_text in (("question", "ask", "ask a question"), ("request", "tell", "relay a task the user typed"), ("note", "note", "send an FYI")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("text", nargs="+")
        p.add_argument("--to")
        p.add_argument("--subject")
        p.add_argument("--context")
        p.add_argument("--option", action="append")
        p.add_argument("--recommend", dest="recommendation")
        p.add_argument("--ref", action="append", help="key=value, e.g. pr=https://...")
        p.add_argument("--label")
        p.add_argument("--thread", help="id of the first message, to continue a conversation")
        if kind == "request":
            p.add_argument("--owner-words", required=True)
        p.set_defaults(func=lambda a, k=kind: cmd_message(a, k))
    p = sub.add_parser("answer", help="answer a question an agent sent you")
    p.add_argument("in_reply_to")
    p.add_argument("text", nargs="+")
    p.add_argument("--to")
    p.add_argument("--status", default="answered", choices=STATUSES)
    p.add_argument("--thread")
    p.set_defaults(func=cmd_answer)
    p = sub.add_parser("hello", help="self-test: ask the agent for PONG")
    p.add_argument("--to")
    p.set_defaults(func=cmd_hello)
    p = sub.add_parser("send", help="send a prepared envelope file")
    p.add_argument("file")
    p.add_argument("--to")
    p.set_defaults(func=cmd_send)
    p = sub.add_parser("check")
    p.add_argument("--to")
    p.set_defaults(func=cmd_check)
    sub.add_parser("peers").set_defaults(func=cmd_peers)
    sub.add_parser("version").set_defaults(func=cmd_version)
    sub.add_parser("drop", help="leave an agent's message (stdin) for the local channel").set_defaults(func=cmd_drop)
    p = sub.add_parser("add-peer", help="register a Grok agent on this machine")
    p.add_argument("peer")
    p.add_argument("--name")
    p.add_argument("--inbox", help="Claude inbox routine id (trig_...)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--inbox-mode", action="store_true", help="zero-touch, no secrets")
    mode.add_argument("--stdin", action="store_true", help='fast lane from JSON on stdin: {"webhook_url", "authorization"}')
    p.add_argument("--no-fast-lane", action="store_true", help="with --inbox-mode: forget a webhook that no longer exists")
    p.set_defaults(func=cmd_add_peer)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
