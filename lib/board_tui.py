"""board_tui — interactive curses-based team UI (inspired by Claude Code Teams)."""

import curses
import subprocess
import time

from lib.board_db import BoardDB


def _tmux_has_session(name: str) -> bool:
    try:
        r = subprocess.run(["tmux", "has-session", "-t", name], capture_output=True, timeout=3)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _tmux_pane_command(name: str) -> str:
    try:
        r = subprocess.run(
            ["tmux", "list-panes", "-t", name, "-F", "#{pane_current_command}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _tmux_capture(name: str, lines: int = 15) -> list[str]:
    try:
        r = subprocess.run(
            ["tmux", "capture-pane", "-t", name, "-p", "-S", str(-lines)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0:
            return r.stdout.rstrip("\n").split("\n")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


class _TeammateInfo:
    __slots__ = ("active", "inbox_count", "name", "online", "status", "task", "tmux_session")

    def __init__(self, name: str, tmux_session: str):
        self.name = name
        self.tmux_session = tmux_session
        self.online = False
        self.active = False
        self.status = ""
        self.inbox_count = 0
        self.task = ""


def _refresh_teammates(db: BoardDB, prefix: str) -> list[_TeammateInfo]:
    teammates = []
    for (name,) in db.query("SELECT name FROM sessions WHERE name != 'all' ORDER BY name"):
        sess = f"{prefix}-{name}"
        t = _TeammateInfo(name, sess)

        if _tmux_has_session(sess):
            t.online = True
            cmd = _tmux_pane_command(sess)
            t.active = cmd not in ("zsh", "bash", "sh", "-zsh", "-bash", "")
        t.inbox_count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        row = db.query_one("SELECT status FROM sessions WHERE name=?", (name,))
        if row and row[0]:
            t.status = row[0][:60]
        task_row = db.query_one(
            "SELECT description FROM tasks WHERE session=? AND status='active' ORDER BY id ASC LIMIT 1",
            (name,),
        )
        if task_row:
            t.task = task_row[0][:50]
        teammates.append(t)
    return teammates


def _get_recent_messages(db: BoardDB, limit: int = 5) -> list[str]:
    rows = db.query(
        "SELECT '[' || ts || '] ' || sender || ' → ' || recipient || ': ' || substr(body, 1, 60) "
        "FROM messages ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [r[0] for r in reversed(rows)]


def cmd_tui(db: BoardDB) -> None:
    """Launch interactive team UI."""
    if not db.env:
        print("ERROR: 需要完整环境才能启动 TUI")
        raise SystemExit(1)
    prefix = db.env.prefix
    try:
        curses.wrapper(_tui_main, db, prefix)
    except KeyboardInterrupt:
        pass


def _tui_main(stdscr, db: BoardDB, prefix: str) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(1000)

    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # running
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # idle/dead
        curses.init_pair(3, curses.COLOR_RED, -1)  # offline
        curses.init_pair(4, curses.COLOR_CYAN, -1)  # header
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)  # selected
        curses.init_pair(6, curses.COLOR_WHITE, -1)  # dim

    selected = 0
    mode = "list"  # list | detail
    detail_name = ""
    last_refresh = 0.0
    teammates: list[_TeammateInfo] = []
    messages: list[str] = []

    while True:
        now = time.time()
        if now - last_refresh > 1.5:
            teammates = _refresh_teammates(db, prefix)
            messages = _get_recent_messages(db, 5)
            last_refresh = now

        stdscr.erase()
        h, w = stdscr.getmaxyx()

        if mode == "list":
            _draw_list(stdscr, teammates, messages, selected, h, w)
        else:
            _draw_detail(stdscr, teammates, detail_name, prefix, h, w)

        stdscr.refresh()

        try:
            ch = stdscr.getch()
        except curses.error:
            ch = -1

        if ch == -1:
            continue

        if ch == ord("q") or ch == 27:  # q or Esc
            if mode == "detail":
                mode = "list"
            else:
                break
        elif mode == "list":
            if ch == curses.KEY_UP or ch == ord("k"):
                selected = max(0, selected - 1)
            elif ch == curses.KEY_DOWN or ch == ord("j"):
                selected = min(len(teammates) - 1, selected + 1)
            elif ch == 10 or ch == curses.KEY_RIGHT:  # Enter or →
                if teammates:
                    detail_name = teammates[selected].name
                    mode = "detail"
            elif ch == ord("K"):  # Kill
                if teammates and teammates[selected].online:
                    sess = teammates[selected].tmux_session
                    subprocess.run(["tmux", "send-keys", "-t", sess, "C-c", ""], capture_output=True)
                    subprocess.run(["tmux", "send-keys", "-t", sess, "/exit", "Enter"], capture_output=True)
                    last_refresh = 0.0
            elif ch == ord("m"):  # send Message
                _send_message_prompt(stdscr, db, teammates, selected, h, w)
                last_refresh = 0.0
        elif mode == "detail" and (ch == curses.KEY_LEFT or ch == ord("h")):
            mode = "list"


def _draw_list(stdscr, teammates: list[_TeammateInfo], messages: list[str], selected: int, h: int, w: int) -> None:
    # Header
    title = "◆ cnb team"
    _safe_addstr(stdscr, 0, 0, title, curses.color_pair(4) | curses.A_BOLD)
    count = len([t for t in teammates if t.online])
    subtitle = f"  {count}/{len(teammates)} online"
    _safe_addstr(stdscr, 0, len(title), subtitle, curses.color_pair(6))

    # Teammate list
    y = 2
    for i, t in enumerate(teammates):
        if y >= h - 8:
            break
        is_sel = i == selected
        pointer = "❯ " if is_sel else "  "

        if t.online and t.active:
            symbol = "●"
            color = curses.color_pair(1)
        elif t.online:
            symbol = "○"
            color = curses.color_pair(2)
        else:
            symbol = "·"
            color = curses.color_pair(3)

        name_str = f"@{t.name}"
        inbox_str = f" [{t.inbox_count}msg]" if t.inbox_count else ""

        line = f"{pointer}{symbol} {name_str:<12s}{inbox_str}"
        attr = curses.color_pair(5) | curses.A_BOLD if is_sel else color
        _safe_addstr(stdscr, y, 0, line[: w - 1], attr)

        if t.task:
            task_display = f"  → {t.task}"
            _safe_addstr(stdscr, y, len(line), task_display[: w - len(line) - 1], curses.color_pair(6))
        elif t.status:
            status_display = f"  {t.status[:40]}"
            _safe_addstr(stdscr, y, len(line), status_display[: w - len(line) - 1], curses.color_pair(6))

        y += 1

    # Separator
    y += 1
    if y < h - 6:
        _safe_addstr(stdscr, y, 0, "─" * min(w - 1, 60), curses.color_pair(6))
        y += 1

    # Recent messages
    if y < h - 2:
        _safe_addstr(stdscr, y, 0, "Recent:", curses.color_pair(4))
        y += 1
        for msg in messages:
            if y >= h - 2:
                break
            _safe_addstr(stdscr, y, 2, msg[: w - 3], curses.color_pair(6))
            y += 1

    # Footer
    footer = "↑↓ select · Enter view · K kill · m msg · q quit"
    _safe_addstr(stdscr, h - 1, 0, footer[: w - 1], curses.color_pair(4) | curses.A_DIM)


def _draw_detail(stdscr, teammates: list[_TeammateInfo], name: str, prefix: str, h: int, w: int) -> None:
    t = next((t for t in teammates if t.name == name), None)
    if not t:
        _safe_addstr(stdscr, 0, 0, f"@{name} not found", curses.color_pair(3))
        return

    # Header
    if t.online and t.active:
        state = "● running"
        color = curses.color_pair(1)
    elif t.online:
        state = "○ idle"
        color = curses.color_pair(2)
    else:
        state = "· offline"
        color = curses.color_pair(3)

    _safe_addstr(stdscr, 0, 0, f"@{name} ", curses.color_pair(4) | curses.A_BOLD)
    _safe_addstr(stdscr, 0, len(name) + 2, state, color)

    y = 2
    if t.status:
        _safe_addstr(stdscr, y, 0, "Status:", curses.color_pair(6))
        _safe_addstr(stdscr, y + 1, 2, t.status[: w - 3], curses.A_NORMAL)
        y += 3

    if t.task:
        _safe_addstr(stdscr, y, 0, "Task:", curses.color_pair(6))
        _safe_addstr(stdscr, y + 1, 2, t.task[: w - 3], curses.A_NORMAL)
        y += 3

    # Live output
    y += 1
    _safe_addstr(stdscr, y, 0, "Output:", curses.color_pair(4))
    y += 1
    sess = f"{prefix}-{name}"
    lines = _tmux_capture(sess, min(h - y - 2, 15))
    for line in lines:
        if y >= h - 2:
            break
        _safe_addstr(stdscr, y, 2, line[: w - 3], curses.A_NORMAL)
        y += 1

    # Footer
    footer = "← back · Esc list · q quit"
    _safe_addstr(stdscr, h - 1, 0, footer[: w - 1], curses.color_pair(4) | curses.A_DIM)


def _send_message_prompt(stdscr, db: BoardDB, teammates: list[_TeammateInfo], selected: int, h: int, w: int) -> None:
    if not teammates:
        return
    target = teammates[selected].name
    curses.curs_set(1)
    stdscr.nodelay(False)

    prompt = f"Send to @{target}: "
    _safe_addstr(stdscr, h - 1, 0, " " * (w - 1), curses.A_NORMAL)
    _safe_addstr(stdscr, h - 1, 0, prompt, curses.color_pair(4))
    stdscr.refresh()

    curses.echo()
    try:
        msg_bytes = stdscr.getstr(h - 1, len(prompt), w - len(prompt) - 2)
        msg = msg_bytes.decode("utf-8", errors="replace").strip()
    except (curses.error, UnicodeDecodeError):
        msg = ""
    curses.noecho()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(1000)

    if msg:
        from lib.board_db import ts

        now = ts()
        sessions = [r[0] for r in db.query("SELECT name FROM sessions ORDER BY name LIMIT 1")]
        sender = sessions[0] if sessions else "user"
        with db.conn() as c:
            msg_id = db.execute(
                "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
                (now, sender, target, msg),
                c=c,
            )
            db.deliver_to_inbox(sender, target, msg_id, c=c)


def _safe_addstr(stdscr, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    try:
        stdscr.addstr(y, x, text[: w - x], attr)
    except curses.error:
        pass
