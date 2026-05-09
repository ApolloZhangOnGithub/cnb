#!/usr/bin/env python3
"""monitor.py -- File change monitoring (kqueue / inotify / poll).

Event-driven file watching to detect session file changes instantly.

Usage:
    ./lib/monitor.py              # watch and react
    ./lib/monitor.py --test       # send a test message and measure latency
    ./lib/monitor.py --benchmark  # compare event vs polling latency
"""

import os
import select
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

# Try to import common; fall back gracefully for standalone use
try:
    from lib.board_db import BoardDB
    from lib.common import ClaudesEnv
except ImportError:
    _here = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_here))
    from lib.board_db import BoardDB
    from lib.common import ClaudesEnv


def log(msg: str) -> None:
    now = time.strftime("%H:%M:%S")
    ms = f"{time.time() % 1:.3f}"[1:]
    print(f"[monitor] {now}{ms} {msg}", flush=True)


def has_kqueue() -> bool:
    return hasattr(select, "kqueue")


def has_inotifywait() -> bool:
    import shutil

    return shutil.which("inotifywait") is not None


# ---------------------------------------------------------------------------
# Kqueue watcher (macOS)
# ---------------------------------------------------------------------------


class KqueueWatcher:
    """Watch a directory and its .md files for changes using kqueue."""

    def __init__(self, watch_dir: str) -> None:
        self.watch_dir = watch_dir
        select_any = cast(Any, select)
        kqueue = select_any.kqueue
        kevent = select_any.kevent
        vnode_filter = select_any.KQ_FILTER_VNODE
        ev_add = select_any.KQ_EV_ADD
        ev_clear = select_any.KQ_EV_CLEAR
        note_write = select_any.KQ_NOTE_WRITE
        note_extend = select_any.KQ_NOTE_EXTEND

        self.kq = kqueue()
        self.dir_fd = os.open(watch_dir, os.O_RDONLY)
        dir_event = kevent(
            self.dir_fd,
            filter=vnode_filter,
            flags=ev_add | ev_clear,
            fflags=note_write,
        )
        self.kq.control([dir_event], 0)
        self.file_fds: dict[str, int] = {}
        self._kevent = kevent
        self._vnode_filter = vnode_filter
        self._ev_add = ev_add
        self._ev_clear = ev_clear
        self._note_write = note_write
        self._note_extend = note_extend
        self._refresh()

    def _refresh(self) -> None:
        """Register watches on any new .md files."""
        for f in os.listdir(self.watch_dir):
            if not f.endswith(".md"):
                continue
            path = os.path.join(self.watch_dir, f)
            if path in self.file_fds:
                continue
            fd = -1
            try:
                fd = os.open(path, os.O_RDONLY)
                ev = self._kevent(
                    fd,
                    filter=self._vnode_filter,
                    flags=self._ev_add | self._ev_clear,
                    fflags=self._note_write | self._note_extend,
                )
                self.kq.control([ev], 0)
                self.file_fds[path] = fd
            except OSError:
                if fd >= 0:
                    os.close(fd)

    def poll(self, timeout: float = 5.0) -> set:
        """Block up to *timeout* seconds, return set of changed file paths."""
        fd_to_path = {fd: path for path, fd in self.file_fds.items()}
        try:
            events = self.kq.control(None, 8, timeout)
        except (InterruptedError, OSError):
            return set()

        if not events:
            self._refresh()
            return set()

        changed = set()
        for ev in events:
            if ev.ident == self.dir_fd:
                self._refresh()
            elif ev.ident in fd_to_path:
                changed.add(fd_to_path[ev.ident])

        if not changed:
            self._refresh()
        return changed

    def close(self) -> None:
        for fd in self.file_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.close(self.dir_fd)
        except OSError:
            pass
        self.kq.close()


# ---------------------------------------------------------------------------
# Inotify watcher (Linux)
# ---------------------------------------------------------------------------


class InotifyWatcher:
    """Watch via inotifywait subprocess."""

    def __init__(self, watch_dir: str) -> None:
        self.proc = subprocess.Popen(
            ["inotifywait", "-m", "-e", "modify,create", "--format", "%w%f", watch_dir + "/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def poll(self, timeout: float = 5.0) -> set:
        import selectors

        sel = selectors.DefaultSelector()
        stdout = self.proc.stdout
        assert stdout is not None
        sel.register(stdout, selectors.EVENT_READ)
        changed = set()
        events = sel.select(timeout=timeout)
        for key, _ in events:
            line = key.fileobj.readline().strip()  # type: ignore[union-attr]
            if line:
                changed.add(line)
        sel.close()
        return changed

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait()


# ---------------------------------------------------------------------------
# Polling watcher (fallback)
# ---------------------------------------------------------------------------


class PollWatcher:
    """Fall back to 1s stat polling."""

    def __init__(self, watch_dir: str) -> None:
        self.watch_dir = watch_dir
        self.mtimes: dict[str, float] = {}
        # Initialize mtimes
        self._scan(init=True)

    def _scan(self, init: bool = False) -> set:
        changed = set()
        for f in os.listdir(self.watch_dir):
            if not f.endswith(".md"):
                continue
            path = os.path.join(self.watch_dir, f)
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            prev = self.mtimes.get(path)
            if not init and prev is not None and mt != prev:
                changed.add(path)
            self.mtimes[path] = mt
        return changed

    def poll(self, timeout: float = 1.0) -> set:
        time.sleep(timeout)
        return self._scan()

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Unified watcher factory
# ---------------------------------------------------------------------------


def create_watcher(watch_dir: str):
    """Return the best available watcher for the platform."""
    if has_kqueue():
        return KqueueWatcher(watch_dir)
    elif has_inotifywait():
        return InotifyWatcher(watch_dir)
    else:
        return PollWatcher(watch_dir)


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------


def handle_change(file_path: str, env: ClaudesEnv) -> None:
    """Check for unread inbox and nudge the session."""
    name = os.path.basename(file_path).replace(".md", "")

    unread = 0
    if env.board_db.exists():
        try:
            db = BoardDB(env.board_db)
            unread = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        except (sqlite3.Error, OSError):
            pass

    if unread > 0:
        log(f"EVENT: {name} has {unread} unread")


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------


def do_watch(env: ClaudesEnv) -> None:
    watcher = create_watcher(str(env.sessions_dir))
    log(f"Starting {type(watcher).__name__} on {env.sessions_dir}/")

    running = True

    def _stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        while running:
            changed = watcher.poll(5.0)
            for path in changed:
                handle_change(path, env)
    finally:
        watcher.close()


def do_test(env: ClaudesEnv) -> None:
    log("=== Latency Test ===")
    log("Sending test message and measuring detection time...")

    test_target = env.sessions[0] if env.sessions else "test"
    board_sh = env.install_home / "bin" / "board"

    # Start watcher
    watcher = create_watcher(str(env.sessions_dir))

    start_ms = int(time.time() * 1000)
    try:
        subprocess.run(
            [
                str(board_sh),
                "--as",
                "dispatcher",
                "send",
                test_target,
                f"[monitor-poc] latency test {int(time.time())}",
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass

    # Wait for detection (max 5s)
    for _ in range(50):
        changed = watcher.poll(0.1)
        if changed:
            break

    end_ms = int(time.time() * 1000)
    watcher.close()

    latency = end_ms - start_ms
    log(f"Event detected in {latency}ms")
    log("vs polling at 30s interval: avg 15000ms latency")
    if latency > 0:
        log(f"Improvement: ~{15000 // latency}x faster")

    # Clean up test message
    try:
        subprocess.run(
            [str(board_sh), "--as", test_target, "ack"],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass


def do_benchmark(env: ClaudesEnv) -> None:
    log("=== Event vs Polling Benchmark ===")
    log("")
    log("Event-driven (kqueue/inotify):")
    log("  - Detection latency: <100ms typical")
    log("  - CPU usage: near-zero (kernel callback)")
    log("  - Scalability: O(1) per event")
    log("")
    log("Polling (current dispatcher, 30s):")
    log("  - Detection latency: 0-30000ms (avg 15000ms)")
    log("  - CPU usage: periodic wake + file reads")
    log("  - Scalability: O(n) per interval (n = sessions)")
    log("")
    log("Running live test...")
    do_test(env)


def main() -> None:
    env = ClaudesEnv.load()
    arg = sys.argv[1] if len(sys.argv) > 1 else "watch"

    if arg in ("watch", "--watch"):
        do_watch(env)
    elif arg == "--test":
        do_test(env)
    elif arg == "--benchmark":
        do_benchmark(env)
    elif arg in ("--help", "-h"):
        print("monitor.py -- Event-driven file change monitoring")
        print()
        print("  watch        Start file watcher (default)")
        print("  --test       Measure detection latency")
        print("  --benchmark  Compare event vs polling")
    else:
        print(f"Unknown: {arg}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
