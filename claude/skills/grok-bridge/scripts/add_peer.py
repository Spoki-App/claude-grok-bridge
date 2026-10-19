#!/usr/bin/env python3
"""Add or update a Grok Bot agent in the local grok-bridge config, typing secrets with hidden input.

Usage:
  python3 -I add_peer.py --peer cos --name CoS [--inbox trig_...]            (you, guided hidden prompts)
  echo '{"webhook_url": "...", "authorization": "..."}' | python3 -I add_peer.py --peer cos --stdin   (an agent)

Writes $GROK_BRIDGE_CONFIG or ~/.config/grok-bridge/config.json (folder 700, file 600) and never
prints the webhook URL or the Authorization value.
"""

import argparse
import getpass
import json
import os
import re
import sys

DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".config", "grok-bridge", "config.json")
BOLD, DIM, GREEN, RESET = ("\033[1m", "\033[2m", "\033[32m", "\033[0m") if sys.stdout.isatty() else ("", "", "", "")


def clean_auth(value):
    """Accept a pasted 'Authorization: Bearer x' header line as well as the bare 'Bearer x' value."""
    return re.sub(r"(?i)^\s*authorization\s*:\s*", "", value).strip()


def ask(prompt, valid, error):
    for _ in range(3):
        value = getpass.getpass(prompt).strip()
        if valid(value):
            return value
        print(f"  {error} Try again (paste, then press Enter).")
    sys.exit("Stopped after 3 attempts. Run the same command again when you have the value.")


def guided(name):
    print(f"""
{BOLD}Connect Claude Code to {name}{RESET}
{DIM}You need two values from {name}'s "Claude Code bridge" routine in Grok Bot:
  open the chat with {name}, click {name}'s name at the top (or press Cmd+Shift+I),
  open Routines, then "Claude Code bridge". If {name} sent you links to them, use those.
Pasted text stays hidden: nothing appears while you paste. That is normal.{RESET}
""")
    url = ask(f"{BOLD}1 of 2{RESET}  Paste the Webhook URL, then press Enter: ", lambda v: v.startswith("https://"), "That does not look like a URL starting with https://.")
    print(f"  {GREEN}OK{RESET}")
    auth = clean_auth(ask(f"{BOLD}2 of 2{RESET}  Paste the Authorization value (often starts with 'Bearer'), then press Enter: ", lambda v: len(clean_auth(v)) >= 8, "That value looks empty or too short."))
    print(f"  {GREEN}OK{RESET}")
    return url, auth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--peer", required=True, help="short key, e.g. cos")
    ap.add_argument("--name", help="display name, e.g. CoS")
    ap.add_argument("--inbox", help="Claude inbox routine id (trig_...)")
    ap.add_argument("--stdin", action="store_true", help='read {"webhook_url", "authorization"} JSON from stdin (for agents)')
    ap.add_argument("--inbox-mode", action="store_true", help="zero-touch: no webhook values, messages go through the inbox")
    args = ap.parse_args()
    name = args.name or args.peer

    path = os.environ.get("GROK_BRIDGE_CONFIG", DEFAULT_CONFIG)
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    os.chmod(folder, 0o700)
    cfg = {}
    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)

    if args.inbox_mode:
        url = auth = None
    elif args.stdin:
        data = json.load(sys.stdin)
        url, auth = data.get("webhook_url", "").strip(), clean_auth(data.get("authorization", ""))
        if not url.startswith("https://") or not auth:
            sys.exit("stdin must hold webhook_url (https) and authorization")
    else:
        url, auth = guided(name)

    existing = (cfg.get("peers") or {}).get(args.peer) or {}
    if args.inbox_mode and existing.get("webhook_url"):
        entry = {**existing, "name": name}
        print(f"Kept the existing fast lane (webhook) for '{args.peer}'.")
    elif args.inbox_mode:
        entry = {"name": name, "mode": "inbox"}
    else:
        entry = {"name": name, "webhook_url": url, "authorization": auth}
    cfg.setdefault("peers", {})[args.peer] = entry
    if args.inbox:
        cfg["inbox_routine"] = args.inbox

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(path, 0o600)
    print(f"Saved '{args.peer}' to {path} (only you can read it).")
    if not args.stdin and not args.inbox_mode:
        print(f"""
{GREEN}{BOLD}+------------------------------------------------------------+
|  NEXT STEP: go back to {name}'s chat in Grok Bot and write "done".
|  {name} will run a quick test and tell you when the bridge is ready.
+------------------------------------------------------------+{RESET}
""")


if __name__ == "__main__":
    main()
