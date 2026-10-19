#!/usr/bin/env python3
"""Render the README demo, a looping replay of two real exchanges, to assets/demo.svg. Run: python3 scripts/demo.py

Pure CSS animation (no JavaScript), so GitHub plays it inside <img>. Times are the real UTC times from the
2026-10-19 logs; the waits on screen are shortened. With reduced motion, or no animation support, it shows every message.
"""
import pathlib
import sys
import textwrap
from xml.sax.saxutils import escape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from chats import CHAR_W, LINE_H, MAX_CHARS, PAD, STYLE, WIDTH  # noqa: E402

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"
CAPTION = "Replay of real exchanges from the 2026-10-19 logs. Real times shown, waits shortened."
LABELS = {"you": "you · in Claude Code", "cos": "CoS · Grok Bot", "claude": "Claude Code"}
COLORS = {"you": STYLE["you"], "cos": STYLE["grok"], "claude": STYLE["claude"]}
LOOP, START, STEP, TYPING, GAP = 16.0, 0.5, 1.2, 1.0, 0.8  # seconds on screen
MUTED = "#8a8a8e"

# (who, text, real UTC time or None, note or None); who "event" is a log line, not a chat bubble.
EXCHANGES = [
    ("1 · Claude Code asks the agent", [
        ("you", "ask CoS for a PONG", None, None),
        ("claude", "Sent question q-selftest-20261019-130932 to CoS.", "13:09:32", None),
        ("cos", "PONG", "13:10:17", "status answered"),
        ("event", "Claude inbox logged the answer", "13:10:23", None),
    ]),
    ("2 · The agent asks Claude Code", [
        ("cos", "What is 13 times 17? Answer with just the number.", None, "q-agent-test-0804"),
        ("event", "Claude inbox logged q-agent-test-0804", "12:35:51", None),
        ("event", "Claude Code cloud session started on its own", "12:37:52", None),
        ("claude", "221", "12:38:03", "TASK_STATE_COMPLETED"),
    ]),
]


def seconds(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def since(previous, now):
    d = seconds(now) - seconds(previous)
    return f"+{d // 60} min {d % 60} s" if d >= 60 else f"+{d} s"


def pct(t):
    return f"{t / LOOP * 100:.1f}".rstrip("0").rstrip(".")


def keyframes(name, show, hide=None):
    """Hidden until `show`, visible until `hide` (or the loop's fade-out), hidden again at the end."""
    end = f"{pct(hide)}%{{opacity:1}}{pct(hide + 0.2)}%,100%{{opacity:0}}" if hide else "94%{opacity:1;transform:none}97.5%,100%{opacity:0}"
    return f"@keyframes {name}{{0%,{pct(show)}%{{opacity:0;transform:translateY(6px)}}{pct(show + 0.4)}%{{opacity:1;transform:none}}{end}}}"


def bubble(y, who, text, label):
    s = COLORS[who]
    lines = textwrap.wrap(text, MAX_CHARS)
    w = max(int(max(len(line) for line in lines) * CHAR_W) + 32, 76)
    h = len(lines) * LINE_H + 18
    left = who != "claude"
    x, dx = (PAD, PAD) if left else (WIDTH - PAD - w, WIDTH - PAD - 64)
    tx, anchor = (PAD + 4, "start") if left else (WIDTH - PAD - 4, "end")
    out = [f'<text class="l" x="{tx}" y="{y + 13}" text-anchor="{anchor}">{escape(label)}</text>',
           f'<rect x="{x}" y="{y + 22}" width="{w}" height="{h}" rx="16" fill="{s["fill"]}" stroke="{s["stroke"]}"/>']
    out += [f'<text class="b" x="{x + 16}" y="{y + 49 + i * LINE_H}" fill="{s["text"]}">{escape(line)}</text>' for i, line in enumerate(lines)]
    typing = [f'<text class="l" x="{tx}" y="{y + 13}" text-anchor="{anchor}">{escape(LABELS[who])}</text>',
              f'<rect x="{dx}" y="{y + 22}" width="64" height="40" rx="16" fill="{s["fill"]}" stroke="{s["stroke"]}"/>']
    typing += [f'<circle class="d" cx="{dx + 20 + i * 12}" cy="{y + 42}" r="3.5" fill="{s["text"]}" style="animation-delay:{i * 0.2:.1f}s"/>' for i in range(3)]
    return out, 22 + h + 16, typing


def event(y, text):
    w = int(len(text) * 6.4) + 28
    x = (WIDTH - w) // 2
    return [f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" fill="none" stroke="{MUTED}" stroke-opacity=".45"/>',
            f'<text class="e" x="{WIDTH // 2}" y="{y + 17}" text-anchor="middle">{escape(text)}</text>'], 26 + 16


def render():
    y, t, n, groups, rules, transcript = 52, START, 0, [], [], []
    for heading, messages in EXCHANGES:
        if n:
            t += GAP
        previous, first = None, True
        for who, text, at, note in messages:
            delta = since(previous, at) if previous and at else None
            stamp = " · ".join(x for x in (f"{at} UTC", delta) if x) if at else None
            parts = [f'<text class="h" x="{PAD}" y="{y + 12}">{escape(heading)}</text>'] if first else []
            y += 28 if first else 0
            if who == "event":
                drawn, used = event(y, f"{text} · {stamp}")
                typing = None
            else:
                label = " · ".join(x for x in (LABELS[who], stamp, note) if x)
                drawn, used, typing = bubble(y, who, text, label)
            if typing and delta:
                groups.append(f'<g id="w{n}" class="r t">' + "".join(typing) + "</g>")
                rules.append(keyframes(f"w{n}", t, t + TYPING) + f"#w{n}{{animation-name:w{n}}}")
                t += TYPING
            groups.append(f'<g id="m{n}" class="r">' + "".join(parts + drawn) + "</g>")
            rules.append(keyframes(f"m{n}", t) + f"#m{n}{{animation-name:m{n}}}")
            transcript.append(f"{'log' if who == 'event' else LABELS[who]}{f' [{stamp}]' if stamp else ''}: {text}")
            previous, first, n, t, y = at or previous, False, n + 1, t + STEP, y + used
    height = y + PAD - 16
    label = escape(CAPTION + " " + " / ".join(transcript), {'"': "&quot;"})
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{label}">\n'
            "<style>text{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Inter,Helvetica,Arial,sans-serif}"
            f".b{{font-size:15px}}.l,.e,.h,.c{{font-size:12px;fill:{MUTED}}}.l{{font-weight:600;letter-spacing:.02em}}"
            ".h{font-weight:700;letter-spacing:.06em;text-transform:uppercase}.c{font-style:italic}"
            f".r{{animation-duration:{LOOP:g}s;animation-timing-function:ease-out;animation-iteration-count:infinite}}.t{{opacity:0}}"
            "@keyframes blink{0%,100%{opacity:.3}50%{opacity:1}}.d{animation:blink 1s infinite}\n"
            + "\n".join(rules) + "\n"
            "@media (prefers-reduced-motion:reduce){.r,.d{animation:none}}</style>\n"
            f'<text class="c" x="{WIDTH // 2}" y="24" text-anchor="middle">{escape(CAPTION)}</text>\n'
            + "\n".join(groups) + "\n</svg>\n")


if __name__ == "__main__":
    (ASSETS / "demo.svg").write_text(render())
    print(f"rendered the demo replay to {ASSETS / 'demo.svg'}")
