"""Small ANSI formatting helpers for cnb CLI output."""

from __future__ import annotations

import os
import sys
from typing import TextIO

BOLD = "1"
GREEN = "32"
YELLOW = "33"
RED = "31"
CYAN = "36"
DIM = "2"
RESET = "\033[0m"


def color_enabled(stream: TextIO | None = None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CNB_FORCE_COLOR"):
        return True
    target = stream or sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def style(text: str, *codes: str, stream: TextIO | None = None) -> str:
    if not codes or not color_enabled(stream):
        return text
    return f"\033[{';'.join(codes)}m{text}{RESET}"


def ok(text: str, stream: TextIO | None = None) -> str:
    return style(text, GREEN, stream=stream)


def warn(text: str, stream: TextIO | None = None) -> str:
    return style(text, YELLOW, stream=stream)


def error(text: str, stream: TextIO | None = None) -> str:
    return style(text, RED, stream=stream)


def heading(text: str, stream: TextIO | None = None) -> str:
    return style(text, BOLD, CYAN, stream=stream)


def active(text: str, stream: TextIO | None = None) -> str:
    return style(text, GREEN, stream=stream)


def pending(text: str, stream: TextIO | None = None) -> str:
    return style(text, YELLOW, stream=stream)


def done(text: str, stream: TextIO | None = None) -> str:
    return style(text, DIM, stream=stream)
