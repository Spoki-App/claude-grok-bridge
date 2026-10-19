#!/usr/bin/env python3
"""Claude Code side: send a claude-grok-bridge/1 question, request or note to a Grok Bot agent's routine webhook.

Usage:
  python3 -I send_to_grok.py --check [--peer cos]
  python3 -I send_to_grok.py --peer cos --envelope question.json
  python3 -I send_to_grok.py --peers

Config, first match wins:
  env   GROK_BRIDGE_<PEER>_URL, GROK_BRIDGE_<PEER>_AUTH, GROK_BRIDGE_INBOX_ROUTINE
  file  $GROK_BRIDGE_CONFIG or ~/.config/grok-bridge/config.json (chmod 600):
        {"inbox_routine": "trig_...",
         "peers": {"cos": {"name": "CoS", "webhook_url": "https://...", "authorization": "Bearer ..."}}}

The webhook URL and Authorization value are secrets: this script never prints them.
Exit codes: 0 delivered, 2 config problem, 3 HTTP or network error, 4 invalid envelope.
"""

import argparse
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.request

PROTOCOL = "claude-grok-bridge/1"
DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".config", "grok-bridge", "config.json")
LONG_TOKEN = re.compile(r"[A-Za-z0-9_\-\.]{24,}")
MAX_BYTES = 60_000
OUTBOUND_TYPES = {"question", "request", "note"}


def fail(code, msg):
    print(msg)
    sys.exit(code)


def load_file_config():
    path = os.environ.get("GROK_BRIDGE_CONFIG", DEFAULT_CONFIG)
    if not os.path.exists(path):
        return {}, path
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        fail(2, f"CONFIG_INSECURE: {path} is readable by group/others ({oct(mode)}). Run: chmod 600 {path}")
    try:
        with open(path) as f:
            return json.load(f), path
    except (OSError, ValueError) as e:
        fail(2, f"CONFIG_INVALID: cannot parse {path} ({type(e).__name__})")


def resolve(peer):
    cfg, path = load_file_config()
    key = re.sub(r"[^A-Z0-9]", "_", peer.upper())
    url = os.environ.get(f"GROK_BRIDGE_{key}_URL")
    auth = os.environ.get(f"GROK_BRIDGE_{key}_AUTH")
    entry = (cfg.get("peers") or {}).get(peer, {})
    url, auth = url or entry.get("webhook_url", ""), auth or entry.get("authorization", "")
    inbox = os.environ.get("GROK_BRIDGE_INBOX_ROUTINE") or cfg.get("inbox_routine", "")
    if not url.startswith("https://") or not auth:
        fail(2, f"CONFIG_MISSING: no webhook for peer '{peer}' in env GROK_BRIDGE_{key}_URL/_AUTH or {path}")
    return url, auth, inbox, entry.get("name", peer)


def list_peers():
    cfg, path = load_file_config()
    names = set((cfg.get("peers") or {}).keys())
    names |= {m.group(1).lower() for k in os.environ if (m := re.match(r"GROK_BRIDGE_(.+)_URL$", k))}
    print("PEERS: " + (", ".join(sorted(names)) or "<none>"))
    print("INBOX_ROUTINE: " + (os.environ.get("GROK_BRIDGE_INBOX_ROUTINE") or cfg.get("inbox_routine") or "<unset>"))


def validate(env):
    kind = env.get("type")
    if env.get("protocol") != PROTOCOL or kind not in OUTBOUND_TYPES:
        fail(4, f"ENVELOPE_INVALID: need protocol={PROTOCOL} and type in {sorted(OUTBOUND_TYPES)}")
    missing = [k for k in ("id", "from", kind) if not env.get(k)]
    if missing:
        fail(4, f"ENVELOPE_INVALID: missing fields {missing}")
    if env.get("on_behalf_of") and (kind != "request" or not env.get("owner_words")):
        fail(4, "ENVELOPE_INVALID: on_behalf_of is only for a request and needs owner_words")
    raw = json.dumps(env, ensure_ascii=False).encode()
    if len(raw) > MAX_BYTES:
        fail(4, f"ENVELOPE_TOO_LARGE: {len(raw)} bytes, max {MAX_BYTES}")
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--peer", default="cos")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--peers", action="store_true")
    ap.add_argument("--envelope", help="path to the question envelope JSON")
    args = ap.parse_args()

    if args.peers:
        list_peers()
        return
    url, auth, inbox, name = resolve(args.peer)
    if args.check:
        print(f"CONFIG_OK peer={args.peer} name={name} inbox_routine={inbox or '<unset>'}")
        return
    if not args.envelope:
        ap.error("--envelope is required")
    with open(args.envelope) as f:
        env = json.load(f)
    if inbox:
        env.setdefault("reply_to", {}).setdefault("inbox_routine", inbox)
    raw = validate(env)

    req = urllib.request.Request(url, data=raw, method="POST", headers={"Content-Type": "application/json", "Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, text = resp.status, resp.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read(2000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        fail(3, "NETWORK_ERROR: " + LONG_TOKEN.sub("<redacted>", str(e).replace(url, "<url>")))

    clean = LONG_TOKEN.sub("<redacted>", text.replace(url, "<url>").replace(auth, "<redacted>")).strip()
    print(f"HTTP {status} id={env['id']}")
    print("BODY: " + (clean or "<empty>"))
    sys.exit(0 if 200 <= status < 300 else 3)


if __name__ == "__main__":
    main()
