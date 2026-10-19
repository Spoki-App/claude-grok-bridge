#!/usr/bin/env python3
"""Add or update a Grok Bot agent in the local grok-bridge config, typing secrets with hidden input.

Usage:
  python3 -I add_peer.py --peer cos --name CoS [--inbox trig_...]            (you, hidden prompts)
  echo '{"webhook_url": "...", "authorization": "..."}' | python3 -I add_peer.py --peer cos --stdin   (an agent)

Writes $GROK_BRIDGE_CONFIG or ~/.config/grok-bridge/config.json (folder 700, file 600) and never
prints the webhook URL or the Authorization value.
"""

import argparse
import getpass
import json
import os
import sys

DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".config", "grok-bridge", "config.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--peer", required=True, help="short key, e.g. cos")
    ap.add_argument("--name", help="display name, e.g. CoS")
    ap.add_argument("--inbox", help="Claude inbox routine id (trig_...)")
    ap.add_argument("--stdin", action="store_true", help='read {"webhook_url", "authorization"} JSON from stdin (for agents)')
    args = ap.parse_args()

    path = os.environ.get("GROK_BRIDGE_CONFIG", DEFAULT_CONFIG)
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    os.chmod(folder, 0o700)
    cfg = {}
    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)

    if args.stdin:
        data = json.load(sys.stdin)
        url, auth = data.get("webhook_url", "").strip(), data.get("authorization", "").strip()
    else:
        url = getpass.getpass(f"Webhook URL of {args.name or args.peer}'s Grok Bot routine (hidden): ").strip()
        auth = getpass.getpass("Authorization header value, e.g. 'Bearer ...' (hidden): ").strip()
    if not url.startswith("https://"):
        sys.exit("The webhook URL must start with https://")
    if not auth:
        sys.exit("Authorization value is empty")

    cfg.setdefault("peers", {})[args.peer] = {"name": args.name or args.peer, "webhook_url": url, "authorization": auth}
    if args.inbox:
        cfg["inbox_routine"] = args.inbox

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(path, 0o600)
    print(f"Saved peer '{args.peer}' to {path} (chmod 600). Peers: {', '.join(sorted(cfg['peers']))}")


if __name__ == "__main__":
    main()
