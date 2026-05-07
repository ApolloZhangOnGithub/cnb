"""FileWatcher — kqueue-based instant inbox detection (background thread)."""

import os
import threading

from lib.common import is_suspended

from .base import Concern
from .config import DispatcherConfig
from .helpers import log
from .nudge_coordinator import NudgeCoordinator


class FileWatcher(Concern):
    interval = 1

    def __init__(self, cfg: DispatcherConfig, nudge: NudgeCoordinator) -> None:
        super().__init__()
        self.cfg = cfg
        self.nudge = nudge
        self._queue: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        try:
            import select as sel

            if not hasattr(sel, "kqueue"):
                log("kqueue unavailable, using polling only")
                return False
        except ImportError:
            return False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="file-watcher")
        self._thread.start()
        log("File watcher thread started")
        return True

    def _loop(self) -> None:
        import select as sel

        kq = sel.kqueue()
        dir_fd = -1
        file_fds: dict[str, int] = {}
        try:
            watch_dir = str(self.cfg.sessions_dir)
            dir_fd = os.open(watch_dir, os.O_RDONLY)
            kq.control(
                [
                    sel.kevent(
                        dir_fd,
                        filter=sel.KQ_FILTER_VNODE,
                        flags=sel.KQ_EV_ADD | sel.KQ_EV_CLEAR,
                        fflags=sel.KQ_NOTE_WRITE,
                    )
                ],
                0,
            )

            def refresh() -> None:
                for f in os.listdir(watch_dir):
                    if not f.endswith(".md"):
                        continue
                    path = os.path.join(watch_dir, f)
                    if path in file_fds:
                        continue
                    fd = -1
                    try:
                        fd = os.open(path, os.O_RDONLY)
                        kq.control(
                            [
                                sel.kevent(
                                    fd,
                                    filter=sel.KQ_FILTER_VNODE,
                                    flags=sel.KQ_EV_ADD | sel.KQ_EV_CLEAR,
                                    fflags=sel.KQ_NOTE_WRITE | sel.KQ_NOTE_EXTEND,
                                )
                            ],
                            0,
                        )
                        file_fds[path] = fd
                    except OSError:
                        if fd >= 0:
                            os.close(fd)

            refresh()
            while not self._stop.is_set():
                fd_to_path = {fd: p for p, fd in file_fds.items()}
                try:
                    events = kq.control(None, 8, 2.0)
                except (InterruptedError, OSError):
                    if self._stop.is_set():
                        break
                    continue
                if not events:
                    refresh()
                    continue
                changed: set[str] = set()
                for ev in events:
                    if ev.ident == dir_fd:
                        refresh()
                    elif ev.ident in fd_to_path:
                        changed.add(os.path.basename(fd_to_path[ev.ident]).replace(".md", ""))
                if changed:
                    with self._lock:
                        self._queue.extend(changed)
        finally:
            for fd in file_fds.values():
                try:
                    os.close(fd)
                except OSError:
                    pass
            if dir_fd >= 0:
                try:
                    os.close(dir_fd)
                except OSError:
                    pass
            kq.close()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def tick(self, now: int) -> None:
        with self._lock:
            names = list(self._queue)
            self._queue.clear()
        for name in names:
            if not is_suspended(name, self.cfg.suspended_file):
                self.nudge.check_session(name, now)
