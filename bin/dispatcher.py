#!/usr/bin/env python3
"""dispatcher.py -- Session keepalive + health monitoring daemon.

Decomposed from the original 770-line bash god-loop into concern classes,
each with its own check interval and state.

Concerns:
  1. CoralManager       -- dispatcher Claude session lifecycle
  2. SessionKeepAlive   -- detect dead dev sessions
  3. IdleDetector       -- batch screen snapshot comparison
  4. IdleKiller         -- kill sessions idle >30min
  5. IdleNudger         -- nudge idle sessions to continue working
  6. InboxNudger        -- detect unread inboxes, nudge sessions
  7. HealthChecker      -- periodic full status report to Coral
  8. BugSLAChecker      -- check overdue bugs
  9. ResourceMonitor    -- battery/memory/CPU via lib/resources.py
  10. TimeAnnouncer     -- hourly/daily announcements
  11. CoralPoker        -- periodic heartbeat to dispatcher session
  12. FileWatcher       -- kqueue-based instant inbox detection (native thread)
  13. MentorNotifier    -- (stub, TODO)
  14. OKRThroughput     -- (stub, TODO)
  15. AdaptiveThrottle  -- slow down main loop when CPU is high
"""

import hashlib
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Set

# Ensure project root is on sys.path so `lib.*` imports work
_self = Path(__file__).resolve()
CLAUDES_HOME = _self.parent.parent
sys.path.insert(0, str(CLAUDES_HOME))

from lib.common import ClaudesEnv, DB, is_suspended, date_to_epoch
from lib.resources import check_battery, check_cpu, check_memory

# ---------------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------------

env = ClaudesEnv.load()
PREFIX = env.prefix
PROJECT_ROOT = env.project_root
CLAUDES_DIR = env.claudes_dir
SESSIONS_DIR = env.sessions_dir
BOARD_DB = env.board_db
SUSPENDED_FILE = env.suspended_file

DISPATCHER_SESSION = os.environ.get("DISPATCHER_SESSION", "dispatcher")
CORAL_SESS = f"{PREFIX}-{DISPATCHER_SESSION}"
BOARD_SH = str(PROJECT_ROOT / "board.sh")
LOG_DIR = PROJECT_ROOT / ".swarm-logs"
OKR_DIR = CLAUDES_DIR / "okr"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Fail fast if paths are wrong
for _required in [SESSIONS_DIR, CLAUDES_DIR, BOARD_SH]:
    p = Path(_required)
    if not p.exists():
        print(f"FATAL: missing {p}", file=sys.stderr)
        print(f"  PROJECT_ROOT={PROJECT_ROOT}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[dispatcher] {time.strftime('%H:%M:%S')} {msg}", flush=True)


def tmux(*args: str) -> Optional[str]:
    """Run a tmux command, return stdout or None on failure."""
    try:
        r = subprocess.run(
            ["tmux", *args], capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def tmux_ok(*args: str) -> bool:
    """Run a tmux command, return True on success."""
    try:
        r = subprocess.run(["tmux", *args], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def tmux_send(sess: str, text: str) -> None:
    """Send literal text + Enter to a tmux session."""
    subprocess.run(["tmux", "send-keys", "-t", sess, "-l", text], timeout=5)
    subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], timeout=5)


def is_claude_running(sess: str) -> bool:
    """Check if the pane's current command is an active Claude process."""
    if not tmux_ok("has-session", "-t", sess):
        return False
    cmd = tmux("list-panes", "-t", sess, "-F", "#{pane_current_command}")
    if not cmd:
        return False
    first = cmd.splitlines()[0] if cmd else ""
    return first not in ("zsh", "bash", "sh", "-zsh", "-bash", "")


def get_sessions() -> List[str]:
    """Auto-detect dev session names from tmux (excludes dispatcher and lead)."""
    raw = tmux("list-sessions", "-F", "#{session_name}")
    if not raw:
        return []
    names = []
    pfx = f"{PREFIX}-"
    for line in raw.splitlines():
        if line.startswith(pfx):
            name = line[len(pfx):]
            if name not in ("dispatcher", "lead"):
                names.append(name)
    return names


def pane_capture_md5(sess: str) -> str:
    """Capture a tmux pane and return its md5 hex digest."""
    content = tmux("capture-pane", "-t", sess, "-p") or ""
    return hashlib.md5(content.encode()).hexdigest()


def board_send(target: str, msg: str) -> None:
    """Send a board message as dispatcher."""
    try:
        subprocess.run(
            [BOARD_SH, "--as", "dispatcher", "send", target, msg],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def run_tool(script: str, *args: str) -> str:
    """Run a script from PROJECT_ROOT/tools/ and return stdout."""
    try:
        r = subprocess.run(
            [str(PROJECT_ROOT / "tools" / script), *args],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip()
    except Exception:
        return ""


# Build DEV_SESSIONS from session files (everything except dispatcher)
DEV_SESSIONS: List[str] = []
if SESSIONS_DIR.is_dir():
    for sf in sorted(SESSIONS_DIR.glob("*.md")):
        name = sf.stem
        if name != "dispatcher":
            DEV_SESSIONS.append(name)


# ═══════════════════════════════════════════════════════════════════════════
# Concern classes
# ═══════════════════════════════════════════════════════════════════════════

class Concern:
    """Base class for dispatcher concerns."""

    interval: int = 5  # seconds between ticks

    def __init__(self) -> None:
        self.last_tick: int = 0

    def should_tick(self, now: int) -> bool:
        return (now - self.last_tick) >= self.interval

    def tick(self, now: int) -> None:
        raise NotImplementedError

    def maybe_tick(self, now: int) -> None:
        if self.should_tick(now):
            self.tick(now)
            self.last_tick = now


# ---------------------------------------------------------------------------
# 1. CoralManager -- ensure dispatcher Claude session is running
# ---------------------------------------------------------------------------

class CoralManager(Concern):
    interval = 5
    BOOT_WAIT = 8

    def __init__(self) -> None:
        super().__init__()
        self.boot_grace_dir = LOG_DIR / "boot-time"
        self.boot_grace_dir.mkdir(parents=True, exist_ok=True)

    def record_boot_time(self, name: str) -> None:
        (self.boot_grace_dir / name).write_text(str(int(time.time())))

    def ensure_dispatcher(self) -> None:
        if is_claude_running(CORAL_SESS):
            return
        log("Starting Coral...")
        tmux("kill-session", "-t", CORAL_SESS)
        tmux("new-session", "-d", "-s", CORAL_SESS, "-x", "200", "-y", "50")
        tmux_send(CORAL_SESS, f"cd '{PROJECT_ROOT}'")
        time.sleep(0.5)
        tmux_send(
            CORAL_SESS,
            "claude --name dispatcher --append-system-prompt '你是 Coral。启动后运行 cat dispatcher-role.md，然后等指令。回复不超过3行。'",
        )
        self.record_boot_time("dispatcher")
        log(f"Coral started, waiting {self.BOOT_WAIT}s...")
        time.sleep(self.BOOT_WAIT)

    def tick(self, now: int) -> None:
        # Only start Coral if at least one dev session is running
        dev_alive = any(
            is_claude_running(f"{PREFIX}-{s}") for s in DEV_SESSIONS
        )
        if dev_alive and not is_suspended("dispatcher", SUSPENDED_FILE):
            self.ensure_dispatcher()


# ---------------------------------------------------------------------------
# 2. SessionKeepAlive -- detect dead dev sessions
# ---------------------------------------------------------------------------

class SessionKeepAlive(Concern):
    interval = 5

    def tick(self, now: int) -> None:
        for name in get_sessions():
            if is_suspended(name, SUSPENDED_FILE):
                continue
            sess = f"{PREFIX}-{name}"
            if not tmux_ok("has-session", "-t", sess):
                continue
            if not is_claude_running(sess):
                log(f"{name}: agent exited, NOT restarting (idle policy)")


# ---------------------------------------------------------------------------
# 3. IdleDetector -- batch screen snapshot comparison
# ---------------------------------------------------------------------------

class IdleDetector(Concern):
    """Capture all sessions, sleep 1s, re-capture, compare md5 hashes.
    Also checks for tool processes spawned by Claude."""

    interval = 5

    def __init__(self) -> None:
        super().__init__()
        self.cache: dict[str, str] = {}  # sess -> "idle"|"busy"

    def is_idle(self, sess: str) -> bool:
        return self.cache.get(sess) == "idle"

    def tick(self, now: int) -> None:
        self.cache.clear()
        raw = tmux("list-sessions", "-F", "#{session_name}")
        if not raw:
            return

        all_sessions = [s for s in raw.splitlines() if s.startswith(f"{PREFIX}-")]

        # First pass: check typing and tool processes
        need_snapshot: list[str] = []
        for sess in all_sessions:
            # Check if user is typing
            pane_content = tmux("capture-pane", "-t", sess, "-p") or ""
            prompt_lines = [l for l in pane_content.splitlines() if l.startswith("❯")]
            if prompt_lines:
                last_prompt = prompt_lines[-1]
                if re.match(r"^❯ .{3,}", last_prompt):
                    self.cache[sess] = "busy"
                    continue

            # Check for transient tool processes
            has_tool = False
            pane_pid = tmux("display-message", "-t", sess, "-p", "#{pane_pid}")
            if pane_pid:
                try:
                    r = subprocess.run(
                        ["pgrep", "-P", pane_pid],
                        capture_output=True, text=True, timeout=3,
                    )
                    claude_pid = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
                    if claude_pid:
                        r2 = subprocess.run(
                            ["pgrep", "-P", claude_pid],
                            capture_output=True, text=True, timeout=3,
                        )
                        for cpid in r2.stdout.strip().splitlines():
                            if not cpid:
                                continue
                            try:
                                r3 = subprocess.run(
                                    ["ps", "-p", cpid, "-o", "comm="],
                                    capture_output=True, text=True, timeout=3,
                                )
                                cname = r3.stdout.strip().rsplit("/", 1)[-1]
                                if cname and cname not in ("caffeinate", "uv", ""):
                                    has_tool = True
                                    break
                            except Exception:
                                pass
                except Exception:
                    pass

            if has_tool:
                self.cache[sess] = "busy"
                continue

            need_snapshot.append(sess)

        # Snapshot phase: capture md5, sleep 1s, re-capture
        if not need_snapshot:
            return

        snap1: dict[str, str] = {}
        for sess in need_snapshot:
            snap1[sess] = pane_capture_md5(sess)

        time.sleep(1)

        for sess in need_snapshot:
            h2 = pane_capture_md5(sess)
            if snap1[sess] == h2:
                self.cache[sess] = "idle"
            else:
                self.cache[sess] = "busy"


# ---------------------------------------------------------------------------
# 4. IdleKiller -- kill sessions idle >30min
# ---------------------------------------------------------------------------

class IdleKiller(Concern):
    interval = 5
    IDLE_THRESHOLD = 1800  # 30 min
    BOOT_GRACE_SECONDS = 120

    def __init__(self, idle_detector: IdleDetector, coral: CoralManager) -> None:
        super().__init__()
        self.idle_detector = idle_detector
        self.coral = coral
        self.idle_since_dir = LOG_DIR / "idle-since"
        self.idle_since_dir.mkdir(parents=True, exist_ok=True)

    def _in_grace_period(self, name: str, now: int) -> bool:
        boot_file = self.coral.boot_grace_dir / name
        if not boot_file.exists():
            return False
        try:
            boot_ts = int(boot_file.read_text().strip())
            return (now - boot_ts) < self.BOOT_GRACE_SECONDS
        except Exception:
            return False

    def tick(self, now: int) -> None:
        for name in get_sessions():
            sess = f"{PREFIX}-{name}"
            if not tmux_ok("has-session", "-t", sess):
                continue
            if not is_claude_running(sess):
                continue

            # Record boot time for newly discovered sessions
            boot_file = self.coral.boot_grace_dir / name
            if not boot_file.exists():
                self.coral.record_boot_time(name)

            if self._in_grace_period(name, now):
                continue

            idle_file = self.idle_since_dir / name
            if self.idle_detector.is_idle(sess):
                if not idle_file.exists():
                    idle_file.write_text(str(now))
                else:
                    try:
                        since = int(idle_file.read_text().strip())
                    except Exception:
                        since = now
                    elapsed = now - since
                    if elapsed >= self.IDLE_THRESHOLD:
                        log(f"{name}: idle {elapsed}s (>30min), killing session")
                        tmux("kill-session", "-t", sess)
                        idle_file.unlink(missing_ok=True)
                        board_send("All", f"[Dispatcher] {name} 闲置超过 30 分钟，已终止。")
            else:
                idle_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 5. IdleNudger -- nudge idle sessions to continue working
# ---------------------------------------------------------------------------

class IdleNudger(Concern):
    interval = 5
    COOLDOWN = 300

    def __init__(self, idle_detector: IdleDetector) -> None:
        super().__init__()
        self.idle_detector = idle_detector
        self.nudge_dir = LOG_DIR / "idle-nudged"
        self.nudge_dir.mkdir(parents=True, exist_ok=True)

    def tick(self, now: int) -> None:
        for name in get_sessions():
            if is_suspended(name, SUSPENDED_FILE):
                continue
            sess = f"{PREFIX}-{name}"
            if not tmux_ok("has-session", "-t", sess):
                continue
            if not is_claude_running(sess):
                continue
            if not self.idle_detector.is_idle(sess):
                continue

            nudge_file = self.nudge_dir / name
            if nudge_file.exists():
                try:
                    last_nudge = int(nudge_file.read_text().strip())
                    if (now - last_nudge) < self.COOLDOWN:
                        continue
                except Exception:
                    pass

            log(f"{name}: idle, nudging autonomous loop")
            tmux_send(
                sess,
                f"继续工作。检查你的 OKR ({OKR_DIR}/{name}.md)，推进你的活跃 KR。自己决定优先级。",
            )
            nudge_file.write_text(str(now))


# ---------------------------------------------------------------------------
# 6. InboxNudger -- detect unread inboxes, nudge sessions
# ---------------------------------------------------------------------------

class InboxNudger(Concern):
    interval = 5

    def nudge_if_unread(self, name: str) -> None:
        """Check if session has unread messages; if so, inject inbox command."""
        unread = 0
        if BOARD_DB.exists():
            try:
                db = DB(BOARD_DB)
                unread = db.scalar(
                    "SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)
                ) or 0
            except Exception:
                pass
        else:
            try:
                r = subprocess.run(
                    [BOARD_SH, "--as", name, "inbox"],
                    capture_output=True, text=True, timeout=10,
                )
                m = re.search(r"(\d+) 条未读", r.stdout)
                unread = int(m.group(1)) if m else 0
            except Exception:
                pass

        if unread <= 0:
            return

        sess = f"{PREFIX}-{name}"
        if not tmux_ok("has-session", "-t", sess):
            return
        if not is_claude_running(sess):
            return

        log(f"INBOX: {name} has {unread} unread -> nudging")
        tmux_send(sess, f"./board.sh --as {name} inbox")

    def tick(self, now: int) -> None:
        for name in get_sessions():
            self.nudge_if_unread(name)


# ---------------------------------------------------------------------------
# 7. HealthChecker -- periodic full status report to Coral
# ---------------------------------------------------------------------------

class HealthChecker(Concern):
    INITIAL_INTERVAL = 600
    MAX_INTERVAL = 3600

    def __init__(self, coral_poker: "CoralPoker", idle_checker: "IdleSessionChecker") -> None:
        super().__init__()
        self.interval = self.INITIAL_INTERVAL
        self.coral_poker = coral_poker
        self.idle_checker = idle_checker

    def _compact_status(self) -> str:
        parts = []
        for name in get_sessions():
            online = "on" if tmux_ok("has-session", "-t", f"{PREFIX}-{name}") else "off"
            parts.append(f"{name}:{online}")
        return " ".join(parts)

    def tick(self, now: int) -> None:
        status = self._compact_status()
        log(f"Health check (interval:{self.interval}s): {status}")
        self.coral_poker.poke(f"[Dispatcher] 健康巡检 {time.strftime('%H:%M:%S')}: {status}")

        # Exponential backoff
        self.interval = min(self.interval * 2, self.MAX_INTERVAL)

        # Also run idle session check
        self.idle_checker.check(now)


# ---------------------------------------------------------------------------
# 8. BugSLAChecker -- check overdue bugs
# ---------------------------------------------------------------------------

class BugSLAChecker(Concern):
    interval = 600

    def __init__(self, coral_poker: "CoralPoker") -> None:
        super().__init__()
        self.coral_poker = coral_poker

    def tick(self, now: int) -> None:
        try:
            r = subprocess.run(
                [BOARD_SH, "bug", "overdue"],
                capture_output=True, text=True, timeout=10,
            )
            overdue = r.stdout.strip()
        except Exception:
            overdue = ""

        if overdue and "No overdue" not in overdue:
            log(f"Bug SLA alert: {overdue}")
            self.coral_poker.poke(f"[Dispatcher] Bug SLA 超时: {overdue}")


# ---------------------------------------------------------------------------
# 9. ResourceMonitor -- battery/memory/CPU
# ---------------------------------------------------------------------------

class ResourceMonitorConcern(Concern):
    interval = 60
    CPU_HIGH_THRESHOLD = 80
    CPU_LOW_THRESHOLD = 60

    def __init__(self) -> None:
        super().__init__()
        self.last_state = ""

    def tick(self, now: int) -> None:
        batt = check_battery()
        mem = check_memory()
        cpu = check_cpu()

        state = f"{batt.status}|{batt.pct}|{mem.status}|{mem.pressure}|{cpu.status}|{cpu.usage}"
        if state == self.last_state:
            return
        self.last_state = state

        # Battery alerts
        if batt.status == "CRITICAL":
            log(f"RESOURCE: Battery CRITICAL ({batt.pct}%), suspending non-essential sessions")
            board_send("All", f"[Resource] 电池严重不足 ({batt.pct}%)，暂停非关键 session。")
            for name in get_sessions():
                sess = f"{PREFIX}-{name}"
                if is_claude_running(sess):
                    tmux_send(sess, "[系统] 电池严重不足，请立即保存状态。")
        elif batt.status == "LOW":
            log(f"RESOURCE: Battery LOW ({batt.pct}%)")
            board_send("All", f"[Resource] 电池低 ({batt.pct}%)，建议减少活跃 session 到 2-3 个。")

        # Memory alerts
        if mem.status == "CRITICAL":
            log("RESOURCE: Memory pressure CRITICAL")
            board_send("All", "[Resource] 内存压力严重！建议重启最大的 session 释放内存。")
        elif mem.status == "WARNING":
            log("RESOURCE: Memory pressure WARNING")
            board_send("All", "[Resource] 内存压力升高，关注中。")

        # CPU log
        if cpu.status == "SATURATED":
            log(f"RESOURCE: CPU saturated ({cpu.usage}%)")


# ---------------------------------------------------------------------------
# 10. TimeAnnouncer -- hourly/daily announcements
# ---------------------------------------------------------------------------

class TimeAnnouncer(Concern):
    interval = 30  # check every 30s so we don't miss :00

    def __init__(self) -> None:
        super().__init__()
        self.last_announced_hour = -1

    def tick(self, now: int) -> None:
        import datetime
        dt = datetime.datetime.now()
        hour = dt.hour
        minute = dt.minute
        day_of_week = dt.strftime("%A")

        if minute != 0:
            return
        if hour == self.last_announced_hour:
            return
        self.last_announced_hour = hour

        time_str = dt.strftime("%Y-%m-%d %H:%M")

        if hour == 9:
            msg = f"[Clock] {time_str} ({day_of_week}) — 新一天。检查 KR 列表，确认优先级。"
            board_send("All", msg)
            log("Daily announcement sent")
        else:
            msg = f"[Clock] 现在是 {time_str}。"
            board_send("All", msg)
            log(f"Hourly announcement: {hour}:00")


# ---------------------------------------------------------------------------
# 11. CoralPoker -- periodic heartbeat to dispatcher session
# ---------------------------------------------------------------------------

class CoralPoker(Concern):
    interval = 120

    def __init__(self) -> None:
        super().__init__()
        self.last_poke: int = int(time.time())

    def _is_coral_busy(self) -> bool:
        """Check if Coral is typing or actively processing."""
        if not tmux_ok("has-session", "-t", CORAL_SESS):
            return True
        if not is_claude_running(CORAL_SESS):
            return True

        # Check if user is typing
        content = tmux("capture-pane", "-t", CORAL_SESS, "-p") or ""
        prompt_lines = [l for l in content.splitlines() if l.startswith("❯")]
        if prompt_lines:
            last_prompt = prompt_lines[-1]
            if re.match(r"^❯ .{3,}", last_prompt):
                log("Coral: skip (typing)")
                return True

        # Check if screen is changing (Claude thinking/outputting)
        h1 = pane_capture_md5(CORAL_SESS)
        time.sleep(1)
        h2 = pane_capture_md5(CORAL_SESS)
        if h1 != h2:
            log("Coral: skip (busy)")
            return True
        return False

    def poke(self, msg: str) -> bool:
        """Send message to Coral, return True on success."""
        if self._is_coral_busy():
            return False
        log("Coral: poking")
        tmux_send(CORAL_SESS, msg)
        self.last_poke = int(time.time())
        return True

    def tick(self, now: int) -> None:
        # Check dispatcher unread
        dispatcher_unread = 0
        try:
            r = subprocess.run(
                [BOARD_SH, "--as", "dispatcher", "inbox"],
                capture_output=True, text=True, timeout=10,
            )
            m = re.search(r"(\d+) 条未读", r.stdout)
            dispatcher_unread = int(m.group(1)) if m else 0
        except Exception:
            pass

        if dispatcher_unread > 0:
            self.poke(f"[Dispatcher] 你有 {dispatcher_unread} 条未读消息")
        elif (now - self.last_poke) >= self.interval:
            self.poke(f"[Dispatcher] heartbeat {time.strftime('%H:%M:%S')}")


# ---------------------------------------------------------------------------
# 12. FileWatcher -- kqueue-based instant inbox detection (native thread)
# ---------------------------------------------------------------------------

class FileWatcher(Concern):
    """Watches session files for changes using kqueue, running in a
    background thread.  Detected changes are queued and drained by tick()."""

    interval = 1  # drain queue frequently

    def __init__(self, inbox_nudger: InboxNudger) -> None:
        super().__init__()
        self.inbox_nudger = inbox_nudger
        self._changed: list[str] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._available = hasattr(os, "O_RDONLY")  # always true, but we check kqueue below

    def start(self) -> bool:
        """Start background kqueue thread. Returns False if kqueue unavailable."""
        import select as sel_mod
        if not hasattr(sel_mod, "kqueue"):
            log("kqueue unavailable, using polling only")
            return False

        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="file-watcher")
        self._thread.start()
        log(f"File watcher thread started")
        return True

    def _watch_loop(self) -> None:
        """Kqueue watch loop running in a background thread."""
        import select as sel_mod

        watch_dir = str(SESSIONS_DIR)
        kq = sel_mod.kqueue()
        dir_fd = os.open(watch_dir, os.O_RDONLY)

        dir_event = sel_mod.kevent(
            dir_fd,
            filter=sel_mod.KQ_FILTER_VNODE,
            flags=sel_mod.KQ_EV_ADD | sel_mod.KQ_EV_CLEAR,
            fflags=sel_mod.KQ_NOTE_WRITE,
        )
        kq.control([dir_event], 0)

        file_fds: dict[str, int] = {}

        def refresh() -> None:
            for f in os.listdir(watch_dir):
                if not f.endswith(".md"):
                    continue
                path = os.path.join(watch_dir, f)
                if path in file_fds:
                    continue
                try:
                    fd = os.open(path, os.O_RDONLY)
                    ev = sel_mod.kevent(
                        fd,
                        filter=sel_mod.KQ_FILTER_VNODE,
                        flags=sel_mod.KQ_EV_ADD | sel_mod.KQ_EV_CLEAR,
                        fflags=sel_mod.KQ_NOTE_WRITE | sel_mod.KQ_NOTE_EXTEND,
                    )
                    kq.control([ev], 0)
                    file_fds[path] = fd
                except OSError:
                    pass

        refresh()

        while not self._stop_event.is_set():
            fd_to_path = {fd: path for path, fd in file_fds.items()}
            try:
                events = kq.control(None, 8, 2.0)  # 2s timeout to check stop
            except (InterruptedError, OSError):
                if self._stop_event.is_set():
                    break
                continue

            if not events:
                refresh()
                continue

            changed_names: set[str] = set()
            for ev in events:
                if ev.ident == dir_fd:
                    refresh()
                elif ev.ident in fd_to_path:
                    path = fd_to_path[ev.ident]
                    name = os.path.basename(path).replace(".md", "")
                    changed_names.add(name)

            if changed_names:
                with self._lock:
                    self._changed.extend(changed_names)

        # Cleanup
        for fd in file_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.close(dir_fd)
        except OSError:
            pass
        kq.close()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def tick(self, now: int) -> None:
        """Drain queued file-change events and nudge sessions."""
        with self._lock:
            names = list(self._changed)
            self._changed.clear()

        for name in names:
            if is_suspended(name, SUSPENDED_FILE):
                continue
            self.inbox_nudger.nudge_if_unread(name)


# ---------------------------------------------------------------------------
# 13. MentorNotifier (stub)
# ---------------------------------------------------------------------------

class MentorNotifier(Concern):
    interval = 300

    def __init__(self) -> None:
        super().__init__()
        mentor_dir = LOG_DIR / "mentor-notify"
        mentor_dir.mkdir(parents=True, exist_ok=True)

    def tick(self, now: int) -> None:
        pass  # TODO: implement mentor notification logic


# ---------------------------------------------------------------------------
# 14. OKRThroughput (stub)
# ---------------------------------------------------------------------------

class OKRThroughput(Concern):
    interval = 600

    def tick(self, now: int) -> None:
        pass  # TODO: implement OKR throughput checking


# ---------------------------------------------------------------------------
# 15. AdaptiveThrottle -- slow down when CPU is high
# ---------------------------------------------------------------------------

class AdaptiveThrottle(Concern):
    interval = 10
    CPU_HIGH = 80
    CPU_LOW = 60
    MAX_MULT = 4

    def __init__(self) -> None:
        super().__init__()
        self.multiplier: int = 1

    def tick(self, now: int) -> None:
        cpu = check_cpu()
        if cpu.usage > self.CPU_HIGH:
            if self.multiplier < self.MAX_MULT:
                self.multiplier = min(self.multiplier * 2, self.MAX_MULT)
                log(f"THROTTLE: CPU={cpu.usage}% > {self.CPU_HIGH}%, interval x{self.multiplier}")
        elif cpu.usage < self.CPU_LOW and self.multiplier > 1:
            self.multiplier = 1
            log(f"THROTTLE: CPU={cpu.usage}% < {self.CPU_LOW}%, restored normal interval")


# ---------------------------------------------------------------------------
# IdleSessionChecker -- team-wide idle detection (used by HealthChecker)
# ---------------------------------------------------------------------------

class IdleSessionChecker:
    """Check if all sessions are idle (status-update based)."""

    IDLE_THRESHOLD = 1800

    def __init__(self, coral: CoralManager) -> None:
        self.coral = coral
        self.last_idle_alert: int = 0

    def check(self, now: int) -> None:
        idle_list: list[str] = []
        total = 0

        for name in get_sessions():
            if is_suspended(name, SUSPENDED_FILE):
                continue
            sess = f"{PREFIX}-{name}"
            if not tmux_ok("has-session", "-t", sess):
                continue
            if not is_claude_running(sess):
                continue

            # Skip grace period
            boot_file = self.coral.boot_grace_dir / name
            if boot_file.exists():
                try:
                    boot_ts = int(boot_file.read_text().strip())
                    if (now - boot_ts) < 120:
                        continue
                except Exception:
                    pass

            total += 1

            # Check last update timestamp
            last_update = ""
            if BOARD_DB.exists():
                try:
                    db = DB(BOARD_DB)
                    row = db.scalar(
                        "SELECT updated_at FROM sessions WHERE name=?", (name,)
                    )
                    last_update = row or ""
                except Exception:
                    pass
            else:
                sf = SESSIONS_DIR / f"{name}.md"
                if sf.exists():
                    for i, line in enumerate(sf.read_text().splitlines()):
                        if line.startswith("## Status"):
                            rest = sf.read_text().splitlines()
                            if i + 1 < len(rest):
                                m = re.search(
                                    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", rest[i + 1]
                                )
                                if m:
                                    last_update = m.group(0)
                            break

            if last_update:
                update_epoch = date_to_epoch(last_update)
                age = now - update_epoch
                if age > self.IDLE_THRESHOLD:
                    idle_list.append(f"{name}({age}s)")

        idle_count = len(idle_list)
        if idle_count > 0 and idle_count == total:
            elapsed = now - self.last_idle_alert
            if elapsed > 3600:
                idle_str = " ".join(idle_list)
                log(f"All sessions idle: {idle_str}")
                board_send(
                    "lead",
                    f"[Dispatcher] 全员空闲超过 {self.IDLE_THRESHOLD // 60} 分钟:{idle_str}。可能需要分配工作。",
                )
                self.last_idle_alert = now


# ---------------------------------------------------------------------------
# IntegrityChecker -- run integrity-check.sh periodically
# ---------------------------------------------------------------------------

class IntegrityChecker(Concern):
    interval = 600

    def __init__(self, coral_poker: CoralPoker) -> None:
        super().__init__()
        self.coral_poker = coral_poker

    def tick(self, now: int) -> None:
        integrity = run_tool("integrity-check.sh", "check")
        if integrity.startswith("TAMPERED"):
            log(f"INTEGRITY VIOLATION: {integrity}")
            self.coral_poker.poke(f"[ALERT] 治理文件被篡改! {integrity}")
            board_send("lead", f"[INTEGRITY] 治理文件被篡改: {integrity}")


# ---------------------------------------------------------------------------
# UserLogSync -- sync user messages from JSONL to persistent log
# ---------------------------------------------------------------------------

class UserLogSync(Concern):
    interval = 5

    def tick(self, now: int) -> None:
        run_tool("user-log-sync.sh")


# ═══════════════════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    KEEPALIVE_INTERVAL = 2

    # Build concern graph
    coral = CoralManager()
    idle_detector = IdleDetector()
    idle_killer = IdleKiller(idle_detector, coral)
    idle_nudger = IdleNudger(idle_detector)
    inbox_nudger = InboxNudger()
    coral_poker = CoralPoker()
    idle_session_checker = IdleSessionChecker(coral)
    health_checker = HealthChecker(coral_poker, idle_session_checker)
    bug_sla = BugSLAChecker(coral_poker)
    resource_mon = ResourceMonitorConcern()
    time_announcer = TimeAnnouncer()
    file_watcher = FileWatcher(inbox_nudger)
    mentor = MentorNotifier()
    okr = OKRThroughput()
    throttle = AdaptiveThrottle()
    integrity = IntegrityChecker(coral_poker)
    user_log_sync = UserLogSync()

    # Order matters: idle_detector must run before idle_killer / idle_nudger
    concerns: list[Concern] = [
        coral,
        time_announcer,
        idle_detector,
        SessionKeepAlive(),
        idle_killer,
        inbox_nudger,
        idle_nudger,
        coral_poker,
        user_log_sync,
        integrity,
        bug_sla,
        health_checker,
        resource_mon,
        mentor,
        okr,
        file_watcher,
        throttle,
    ]

    log(f"Starting (keepalive:{KEEPALIVE_INTERVAL}s health:{health_checker.INITIAL_INTERVAL}s idle:{IdleKiller.IDLE_THRESHOLD}s)")
    log("Ctrl-C to stop")

    # Start kqueue file watcher thread
    has_kq = file_watcher.start()

    # Signal handling
    running = True

    def _shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while running:
            now = int(time.time())

            # If Coral session is gone, dispatcher shuts itself down
            if not tmux_ok("has-session", "-t", CORAL_SESS):
                log("Coral session gone. Dispatcher shutting down.")
                break

            # Tick all concerns
            for concern in concerns:
                concern.maybe_tick(now)

            # Adaptive sleep
            effective_sleep = KEEPALIVE_INTERVAL * throttle.multiplier
            # Sleep in small increments so we can respond to signals
            deadline = time.time() + effective_sleep
            while running and time.time() < deadline:
                time.sleep(min(0.5, deadline - time.time()))

    finally:
        log("Shutting down...")
        file_watcher.stop()
        log("Stopped.")


if __name__ == "__main__":
    main()
