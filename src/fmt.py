"""Terminal color and formatting utilities for cnb CLI output.

Auto-detects TTY; degrades to plain text when piped or redirected.
"""

import os
import sys

_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _esc(code: str) -> str:
    return f"\033[{code}m" if _COLOR else ""


# --- raw codes ---
RESET = _esc("0")
BOLD = _esc("1")
DIM = _esc("2")
RED = _esc("31")
GREEN = _esc("32")
YELLOW = _esc("33")
BLUE = _esc("34")
MAGENTA = _esc("35")
CYAN = _esc("36")
WHITE = _esc("37")
BOLD_RED = _esc("1;31")
BOLD_GREEN = _esc("1;32")
BOLD_YELLOW = _esc("1;33")
BOLD_BLUE = _esc("1;34")
BOLD_CYAN = _esc("1;36")


# --- composable helpers ---


def bold(s: str) -> str:
    return f"{BOLD}{s}{RESET}"


def dim(s: str) -> str:
    return f"{DIM}{s}{RESET}"


def red(s: str) -> str:
    return f"{RED}{s}{RESET}"


def green(s: str) -> str:
    return f"{GREEN}{s}{RESET}"


def yellow(s: str) -> str:
    return f"{YELLOW}{s}{RESET}"


def blue(s: str) -> str:
    return f"{BLUE}{s}{RESET}"


def cyan(s: str) -> str:
    return f"{CYAN}{s}{RESET}"


def magenta(s: str) -> str:
    return f"{MAGENTA}{s}{RESET}"


# --- semantic helpers ---


def header(s: str) -> str:
    return f"{BOLD_CYAN}{s}{RESET}"


def subheader(s: str) -> str:
    return f"{BOLD}{s}{RESET}"


def ok(s: str) -> str:
    return f"{BOLD_GREEN}OK{RESET} {s}"


def err(s: str) -> str:
    return f"{BOLD_RED}ERROR:{RESET} {s}"


def warn(s: str) -> str:
    return f"{BOLD_YELLOW}WARN:{RESET} {s}"


def status_working(s: str) -> str:
    return f"{BOLD_GREEN}{s}{RESET}"


def status_idle(s: str) -> str:
    return f"{YELLOW}{s}{RESET}"


def status_offline(s: str) -> str:
    return f"{DIM}{s}{RESET}"


def status_blocked(s: str) -> str:
    return f"{BOLD_RED}{s}{RESET}"


def task_active(s: str) -> str:
    return f"{BOLD_GREEN}{s}{RESET}"


def task_pending(s: str) -> str:
    return f"{YELLOW}{s}{RESET}"


def task_done(s: str) -> str:
    return f"{DIM}{s}{RESET}"


def sender_name(s: str) -> str:
    return f"{BOLD_BLUE}{s}{RESET}"


def section_line() -> str:
    return dim("─" * 40)
