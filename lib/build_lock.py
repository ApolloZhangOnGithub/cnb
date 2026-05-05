#!/usr/bin/env python3
"""build_lock.py -- Build queue with mkdir-based atomic locking.

Serialize builds to prevent CPU saturation.
Only one session can build at a time; others wait or skip.

Uses mkdir-based locking for atomicity: mkdir is atomic on all POSIX
systems, so two concurrent callers cannot both succeed.

Usage:
    ./lib/build_lock.py acquire <session> <target>
    ./lib/build_lock.py release <session>
    ./lib/build_lock.py status
    ./lib/build_lock.py wrap <session> <command...>
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# Try to import common; fall back gracefully
try:
    from lib.common import ClaudesEnv
except ImportError:
    _here = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_here))
    from lib.common import ClaudesEnv


MAX_WAIT = 300  # seconds to wait before giving up
STALE_THRESHOLD = 600  # 10 minutes


class BuildLock:
    """Mkdir-based atomic build lock."""

    def __init__(self, lock_dir: Path) -> None:
        self.lock_dir = lock_dir
        self.info_file = lock_dir / "info"

    def read_info(self) -> Tuple[str, int, str]:
        """Parse the info file. Returns (holder, locked_at, target)."""
        if self.info_file.exists():
            try:
                parts = self.info_file.read_text().strip().split("|", 2)
                holder = parts[0] if len(parts) > 0 else "unknown"
                locked_at = int(parts[1]) if len(parts) > 1 else 0
                target = parts[2] if len(parts) > 2 else "unknown"
                return holder, locked_at, target
            except Exception:
                pass
        return "unknown", 0, "unknown"

    def _try_mkdir(self) -> bool:
        """Attempt atomic mkdir. Returns True if we got the lock."""
        try:
            os.mkdir(self.lock_dir)
            return True
        except FileExistsError:
            return False

    def _force_release_stale(self) -> bool:
        """Remove a stale lock (>10 min). Returns True if removed."""
        holder, locked_at, target = self.read_info()
        now = int(time.time())
        if locked_at > 0 and (now - locked_at) > STALE_THRESHOLD:
            print(f"Stale lock from {holder} (>10min), forcing release")
            self._remove()
            return True
        return False

    def _remove(self) -> None:
        """Remove the lock directory tree."""
        import shutil
        try:
            shutil.rmtree(self.lock_dir)
        except FileNotFoundError:
            pass

    def _write_info(self, session: str, target: str) -> None:
        """Write metadata into the lock directory."""
        self.info_file.write_text(f"{session}|{int(time.time())}|{target}")

    def acquire(self, session: str, target: str = "unknown") -> Tuple[bool, str]:
        """Try to get the build lock.

        Returns (success, message) where message is e.g. "OK|sess|target"
        or "BUSY|holder|target".
        """
        if self._try_mkdir():
            self._write_info(session, target)
            return True, f"OK|{session}|{target}"

        # Lock exists -- check for staleness
        if self._force_release_stale():
            if self._try_mkdir():
                self._write_info(session, target)
                return True, f"OK|{session}|{target}"

        holder, _, lock_target = self.read_info()
        return False, f"BUSY|{holder}|{lock_target}"

    def release(self, session: str) -> Tuple[bool, str]:
        """Release the build lock held by *session*."""
        if not self.lock_dir.is_dir():
            return True, "OK (no lock)"
        holder, _, _ = self.read_info()
        if holder == session:
            self._remove()
            return True, "OK released"
        return False, f"ERR: lock held by {holder}, not {session}"

    def status(self) -> str:
        """Return a human-readable status string."""
        if not self.lock_dir.is_dir():
            return "FREE"
        holder, locked_at, target = self.read_info()
        elapsed = int(time.time()) - locked_at
        return f"LOCKED by {holder} ({target}) for {elapsed}s"

    def wrap(self, session: str, command: list) -> int:
        """Acquire lock, run command, release on exit.

        Returns the command's exit code.
        """
        target = command[0] if command else "unknown"

        waited = 0
        while not self._try_mkdir():
            if self.lock_dir.is_dir():
                holder, locked_at, lock_target = self.read_info()
                now = int(time.time())

                # Stale check
                if locked_at > 0 and (now - locked_at) > STALE_THRESHOLD:
                    print(f"[build-queue] Stale lock from {holder}, forcing release")
                    self._remove()
                    continue

                if waited >= MAX_WAIT:
                    print(f"[build-queue] Timeout waiting for lock (held by {holder})")
                    return 1

                if waited % 30 == 0:
                    print(f"[build-queue] Waiting for {holder} to finish building... ({waited}s)")

            time.sleep(5)
            waited += 5

        # We hold the lock
        self._write_info(session, target)
        print(f"[build-queue] {session} acquired lock, running: {' '.join(command)}")

        try:
            result = subprocess.run(command)
            exit_code = result.returncode
        except Exception as e:
            print(f"[build-queue] Command failed: {e}", file=sys.stderr)
            exit_code = 1
        finally:
            self._remove()

        print(f"[build-queue] Build finished (exit {exit_code})")
        return exit_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    env = ClaudesEnv.load()
    lock = BuildLock(env.claudes_dir / "build.lock.d")

    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    if cmd == "acquire":
        if len(args) < 2:
            print("Usage: build_lock.py acquire <session> <target>", file=sys.stderr)
            sys.exit(1)
        session = args[1]
        target = args[2] if len(args) > 2 else "unknown"
        ok, msg = lock.acquire(session, target)
        print(msg)
        if not ok:
            sys.exit(1)

    elif cmd == "release":
        if len(args) < 2:
            print("Usage: build_lock.py release <session>", file=sys.stderr)
            sys.exit(1)
        ok, msg = lock.release(args[1])
        print(msg)
        if not ok:
            sys.exit(1)

    elif cmd == "status":
        print(lock.status())

    elif cmd == "wrap":
        if len(args) < 3:
            print("Usage: build_lock.py wrap <session> <command...>", file=sys.stderr)
            sys.exit(1)
        session = args[1]
        command = args[2:]
        sys.exit(lock.wrap(session, command))

    else:
        print("Usage: build_lock.py {acquire|release|status|wrap} [args...]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
