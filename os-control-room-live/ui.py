"""
ui.py - Terminal colour, boxes and tables for the live Control Room.

Pure presentation, no OS logic. ANSI escape codes only (no dependencies).
Set NO_COLOR=1 to disable colour.
"""

import os
import shutil

_COLOR = os.environ.get("NO_COLOR") is None

_CODES = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "underline": "\033[4m", "reverse": "\033[7m",
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
    "white": "\033[37m", "grey": "\033[90m",
    "bright_red": "\033[91m", "bright_green": "\033[92m",
    "bright_yellow": "\033[93m", "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m", "bright_cyan": "\033[96m",
}


def color(text, *styles):
    if not _COLOR or not styles:
        return text
    return "".join(_CODES.get(s, "") for s in styles) + text + _CODES["reset"]


def _strip(text):
    out, i = [], 0
    while i < len(text):
        if text[i] == "\033":
            while i < len(text) and text[i] != "m":
                i += 1
            i += 1
        else:
            out.append(text[i]); i += 1
    return "".join(out)


def vlen(text):
    return len(_strip(text))


def pad(text, width, align="left"):
    gap = width - vlen(text)
    if gap <= 0:
        return text
    if align == "right":
        return " " * gap + text
    if align == "center":
        l = gap // 2
        return " " * l + text + " " * (gap - l)
    return text + " " * gap


def term_width(default=100):
    try:
        return shutil.get_terminal_size((default, 24)).columns
    except OSError:
        return default


def clear():
    print("\033[2J\033[H", end="" if _COLOR else "\n")


def banner(text):
    return color(pad(f"  {text}", term_width() - 1), "bold", "reverse", "bright_cyan")


def rule(label):
    w = term_width() - 2
    head = f"== {label} "
    return color(head + "=" * max(w - vlen(head), 0), "grey")


def ok(m):   return color("[ ok ] ", "bright_green") + m
def warn(m): return color("[warn] ", "bright_yellow") + m
def err(m):  return color("[fail] ", "bright_red") + m
def info(m): return color("[info] ", "bright_blue") + m


def shellhint(cmd):
    """Show the real Linux command behind an action, so it's never hidden."""
    return color("   $ " + cmd, "dim")


_BOX = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"}


def panel(title, body_lines, width=None):
    ctitle = color(f" {title} ", "bold", "bright_cyan")
    if width is None:
        content = max([vlen(l) for l in body_lines] + [vlen(ctitle) + 3])
        width = min(content + 3, term_width() - 2)
    inner = width - 2
    dash = inner - 1 - vlen(ctitle)
    top = _BOX["tl"] + _BOX["h"] + ctitle + _BOX["h"] * max(dash, 0) + _BOX["tr"]
    out = [color(top, "grey")]
    for line in body_lines:
        out.append(color(_BOX["v"], "grey") + " " + pad(line, inner - 1) + color(_BOX["v"], "grey"))
    out.append(color(_BOX["bl"] + _BOX["h"] * inner + _BOX["br"], "grey"))
    return "\n".join(out)


def table(headers, rows, aligns=None):
    n = len(headers)
    aligns = aligns or ["left"] * n
    w = [vlen(h) for h in headers]
    for r in rows:
        for i in range(n):
            w[i] = max(w[i], vlen(str(r[i])) if i < len(r) else 0)

    def fmt(cells):
        return "  ".join(pad(str(cells[i]) if i < len(cells) else "", w[i], aligns[i])
                         for i in range(n))

    lines = [color(fmt(headers), "bold", "underline")]
    if not rows:
        lines.append(color("(none)", "dim"))
    for r in rows:
        lines.append(fmt(r))
    return lines


def ask(prompt):
    try:
        return input(color(prompt, "bold", "bright_magenta")).strip()
    except EOFError:
        return "exit"


def confirm(prompt):
    return ask(prompt + " [y/N] ").lower().startswith("y")


# ---- live-dashboard visuals -------------------------------------------

_SPARK = "▁▂▃▄▅▆▇█"


def spark(values, width=8, vmax=100.0):
    """Sparkline of the last <width> values (oldest left, newest right)."""
    vals = list(values)[-width:]
    out = ""
    for v in vals:
        if v is None:
            out += " "
            continue
        v = max(0.0, min(v, vmax))
        out += _SPARK[int(v / vmax * (len(_SPARK) - 1) + 0.5)]
    return out.rjust(width)


def bar(frac, width=10, styles=("bright_green",), empty="░"):
    """A horizontal meter: colored filled blocks + dim empty track."""
    if frac is None:
        return color(empty * width, "grey")
    frac = max(0.0, min(1.0, frac))
    full = int(frac * width + 0.5)
    return color("█" * full, *styles) + color(empty * (width - full), "grey")


def alert(text, bell=True):
    """Full-width red alarm bar (optionally rings the terminal bell)."""
    line = pad(f"  ⚠  {text}", term_width() - 3)
    return ("\a" if bell else "") + color(line, "bold", "reverse", "bright_red")


def goodbar(text):
    """Full-width green all-clear bar."""
    line = pad(f"  ✔  {text}", term_width() - 3)
    return color(line, "bold", "reverse", "bright_green")


# 5-row block font for the boot banner / winner screen (only the letters
# this tool actually prints; anything else falls back to plain text).
_FONT = {
    "C": ["█████", "█    ", "█    ", "█    ", "█████"],
    "O": ["█████", "█   █", "█   █", "█   █", "█████"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "S": ["█████", "█    ", "█████", "    █", "█████"],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "I": ["███", " █ ", " █ ", " █ ", "███"],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    " ": ["  ", "  ", "  ", "  ", "  "],
}


def bigtext(text, *styles):
    """Render text in the block font; returns a list of 5 strings."""
    rows = []
    for r in range(5):
        row = " ".join(_FONT[ch][r] if ch in _FONT else ch for ch in text.upper())
        rows.append(color(row, *styles) if styles else row)
    return rows
