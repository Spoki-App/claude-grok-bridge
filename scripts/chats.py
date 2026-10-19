#!/usr/bin/env python3
"""Render the README use-case chats to assets/chat-*.svg. Edit CHATS, then run: python3 scripts/chats.py"""
import pathlib
import textwrap
from xml.sax.saxutils import escape

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"
WIDTH, PAD, MAX_CHARS, CHAR_W, LINE_H = 760, 24, 56, 7.7, 22
STYLE = {
    "grok": {"label": "Grok Bot", "fill": "#0b0b0b", "stroke": "#3a3a3a", "text": "#ffffff", "side": "left"},
    "claude": {"label": "Claude Code", "fill": "#D97757", "stroke": "#D97757", "text": "#ffffff", "side": "right"},
    "you": {"label": "you", "fill": "#e9e9eb", "stroke": "#d0d0d4", "text": "#1c1c1e", "side": "left"},
}

CHATS = {
    "unblock": [
        ("you", "ask Grok Bot whether to merge develop now or wait for the migration PR"),
        ("grok", "B. Wait: the migration touches the same model, you'd resolve the conflict twice."),
        ("claude", "Waiting, then. I'll pick up the next task meanwhile."),
    ],
    "delegate": [
        ("you", "tell Grok Bot to move card #1234 to review and ping the reviewer"),
        ("grok", "accepted. Card moved, reviewer pinged on chat.", "done"),
    ],
    "context": [
        ("claude", "This PR has no card. Asking Grok Bot."),
        ("grok", "It belongs to card #1234. Dana owns it, Sam reviews."),
        ("claude", "Linked the PR to #1234 in the description."),
    ],
    "note": [
        ("you", "note to Grok Bot: PR 42 is merged, staging is next"),
        ("grok", "(updates its board and follow-ups)"),
    ],
    "agent-asks": [
        ("you", "ask Claude Code which services still call the v1 billing endpoint", "to Grok Bot"),
        ("claude", "Three: checkout, invoices, the nightly export job.", "new cloud session, read-only"),
        ("grok", "Claude Code says three services: checkout, invoices, nightly export."),
    ],
    "steer": [
        ("grok", "[note] The spec changed: use the v2 endpoint, v1 is frozen."),
        ("claude", "Got it from Grok Bot. Switching the client to v2 before I open the PR."),
    ],
}


def bubble(y, who, text, tag=None):
    s = STYLE[who]
    lines = textwrap.wrap(text, MAX_CHARS)
    w = int(max(len(line) for line in lines) * CHAR_W) + 32
    h = len(lines) * LINE_H + 18
    x = PAD if s["side"] == "left" else WIDTH - PAD - w
    anchor_x = x + 4 if s["side"] == "left" else x + w - 4
    anchor = "start" if s["side"] == "left" else "end"
    label = s["label"] + (f" · {tag}" if tag else "")
    out = [f'<text class="l" x="{anchor_x}" y="{y + 13}" text-anchor="{anchor}">{escape(label)}</text>',
           f'<rect x="{x}" y="{y + 22}" width="{w}" height="{h}" rx="16" fill="{s["fill"]}" stroke="{s["stroke"]}"/>']
    out += [f'<text class="b" x="{x + 16}" y="{y + 22 + 27 + i * LINE_H}" fill="{s["text"]}">{escape(line)}</text>'
            for i, line in enumerate(lines)]
    return out, 22 + h + 16


def render(messages):
    y, parts = PAD - 8, []
    for who, text, *tag in messages:
        drawn, used = bubble(y, who, text, tag[0] if tag else None)
        parts += drawn
        y += used
    height = y + PAD - 16
    transcript = " / ".join(f"{STYLE[m[0]]['label']}: {m[1]}" for m in messages)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
            f'role="img" aria-label="{escape(transcript, {chr(34): "&quot;"})}">\n'
            "<style>text{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Inter,Helvetica,Arial,sans-serif}"
            ".b{font-size:15px}.l{font-size:12px;font-weight:600;fill:#8a8a8e;letter-spacing:.02em}</style>\n"
            + "\n".join(parts) + "\n</svg>\n")


if __name__ == "__main__":
    for name, messages in CHATS.items():
        (ASSETS / f"chat-{name}.svg").write_text(render(messages))
    print(f"rendered {len(CHATS)} chats to {ASSETS}")
