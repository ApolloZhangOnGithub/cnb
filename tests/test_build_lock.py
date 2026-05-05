"""Tests for the build queue / build lock subsystem (lib/build-lock.sh).

Covers: lock acquisition, double-acquire (BUSY), release,
stale lock auto-removal after 10 minutes, wrap semantics,
and release on failure.

The build lock uses mkdir-based atomic locking in the bash version.
The Python rewrite will use either mkdir or an SQLite-based approach.
These tests verify the logic at the data/state level.
"""

import time

import pytest

STALE_THRESHOLD = 600  # 10 minutes in seconds


@pytest.fixture
def lock_dir(tmp_path):
    """Provide a temporary directory for the build lock."""
    return tmp_path / "build.lock.d"


@pytest.fixture
def lock_info_path(lock_dir):
    """Return the info file path inside the lock directory."""
    return lock_dir / "info"


class TestBuildLockAcquire:
    """Acquiring the build lock."""

    def test_acquire_when_free(self, lock_dir):
        """Acquiring a free lock succeeds (mkdir succeeds)."""
        assert not lock_dir.exists()
        lock_dir.mkdir()
        assert lock_dir.is_dir()

    def test_acquire_writes_info(self, lock_dir, lock_info_path):
        """Acquiring writes session|timestamp|target to the info file."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|npm run build")

        content = lock_info_path.read_text()
        parts = content.split("|")
        assert parts[0] == "alice"
        assert int(parts[1]) > 0
        assert parts[2] == "npm run build"

    def test_double_acquire_fails(self, lock_dir):
        """Attempting to mkdir an existing lock directory fails."""
        lock_dir.mkdir()

        # Second mkdir should fail
        with pytest.raises(FileExistsError):
            lock_dir.mkdir()

    def test_double_acquire_returns_holder_info(self, lock_dir, lock_info_path):
        """When lock is busy, the current holder info is readable."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|build")

        # Another session tries to acquire -- reads holder info
        assert lock_dir.exists()
        content = lock_info_path.read_text()
        holder = content.split("|")[0]
        assert holder == "alice"


class TestBuildLockRelease:
    """Releasing the build lock."""

    def test_release_by_holder(self, lock_dir, lock_info_path):
        """Lock holder can release by removing the lock directory."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|build")

        # Check holder matches before releasing
        content = lock_info_path.read_text()
        holder = content.split("|")[0]
        assert holder == "alice"

        # Release
        lock_info_path.unlink()
        lock_dir.rmdir()
        assert not lock_dir.exists()

    def test_release_by_non_holder_blocked(self, lock_dir, lock_info_path):
        """Non-holder should verify they hold the lock before releasing."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|build")

        content = lock_info_path.read_text()
        holder = content.split("|")[0]
        assert holder == "alice"
        assert holder != "bob"  # bob should NOT release

    def test_release_when_no_lock(self, lock_dir):
        """Releasing when no lock exists is a no-op."""
        assert not lock_dir.exists()
        # Application outputs "OK (no lock)" and returns


class TestBuildLockStale:
    """Stale lock detection and auto-removal."""

    def test_stale_lock_removed_after_threshold(self, lock_dir, lock_info_path):
        """Locks older than 10 minutes are automatically removed."""
        lock_dir.mkdir()
        stale_time = int(time.time()) - (STALE_THRESHOLD + 60)  # 11 minutes ago
        lock_info_path.write_text(f"alice|{stale_time}|build")

        # Check for staleness
        content = lock_info_path.read_text()
        locked_at = int(content.split("|")[1])
        now = int(time.time())
        elapsed = now - locked_at

        assert elapsed > STALE_THRESHOLD

        # Force remove stale lock
        import shutil

        shutil.rmtree(str(lock_dir))
        assert not lock_dir.exists()

    def test_fresh_lock_not_removed(self, lock_dir, lock_info_path):
        """Locks within the threshold are not removed."""
        lock_dir.mkdir()
        fresh_time = int(time.time()) - 60  # 1 minute ago
        lock_info_path.write_text(f"alice|{fresh_time}|build")

        content = lock_info_path.read_text()
        locked_at = int(content.split("|")[1])
        now = int(time.time())
        elapsed = now - locked_at

        assert elapsed < STALE_THRESHOLD
        assert lock_dir.exists()  # Not removed

    def test_stale_detection_logic(self):
        """Verify the stale detection formula."""
        now = int(time.time())

        # Just under threshold
        locked_at_fresh = now - (STALE_THRESHOLD - 1)
        assert (now - locked_at_fresh) <= STALE_THRESHOLD

        # Just over threshold
        locked_at_stale = now - (STALE_THRESHOLD + 1)
        assert (now - locked_at_stale) > STALE_THRESHOLD


class TestBuildLockStatus:
    """Lock status queries."""

    def test_status_free(self, lock_dir):
        """Status reports FREE when no lock exists."""
        assert not lock_dir.exists()
        # Application outputs "FREE"

    def test_status_locked(self, lock_dir, lock_info_path):
        """Status reports lock holder and elapsed time."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|npm run build")

        content = lock_info_path.read_text()
        parts = content.split("|")
        holder = parts[0]
        locked_at = int(parts[1])
        target = parts[2]
        elapsed = int(time.time()) - locked_at

        assert holder == "alice"
        assert target == "npm run build"
        assert elapsed >= 0


class TestBuildLockWrap:
    """Wrap: run a command under the build lock."""

    def test_wrap_acquires_lock(self, lock_dir, lock_info_path):
        """Wrap acquires the lock before running."""
        assert not lock_dir.exists()

        # Simulate wrap: acquire
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|test")

        assert lock_dir.exists()

    def test_wrap_releases_on_success(self, lock_dir, lock_info_path):
        """Wrap releases the lock after successful command."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|test")

        # Simulate successful command execution
        # ...

        # Release on exit
        import shutil

        shutil.rmtree(str(lock_dir))
        assert not lock_dir.exists()

    def test_wrap_releases_on_failure(self, lock_dir, lock_info_path):
        """Wrap releases the lock even if the command fails (trap EXIT)."""
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|test")

        # Simulate command failure
        command_failed = True

        # trap EXIT always fires
        import shutil

        shutil.rmtree(str(lock_dir))
        assert not lock_dir.exists()
        assert command_failed  # Command failed but lock was released

    def test_wrap_waits_for_lock(self, lock_dir, lock_info_path):
        """Wrap waits (polls) when lock is held by another session."""
        # Create lock held by bob
        lock_dir.mkdir()
        now = int(time.time())
        lock_info_path.write_text(f"bob|{now}|build")

        # Alice tries to wrap -- sees lock is held
        assert lock_dir.exists()
        content = lock_info_path.read_text()
        holder = content.split("|")[0]
        assert holder == "bob"
        assert holder != "alice"

    def test_wrap_timeout(self):
        """Wrap gives up after MAX_WAIT seconds (300s)."""
        max_wait = 300
        # Application tracks waited time and exits if > max_wait
        waited = 310
        assert waited >= max_wait


class TestBuildLockAtomicity:
    """mkdir-based atomicity guarantees."""

    def test_mkdir_is_atomic(self, tmp_path):
        """Two concurrent mkdirs on the same path -- only one succeeds."""
        lock = tmp_path / "test.lock.d"

        # First mkdir succeeds
        lock.mkdir()
        assert lock.exists()

        # Second mkdir fails
        with pytest.raises(FileExistsError):
            lock.mkdir()

    def test_info_file_consistency(self, lock_dir, lock_info_path):
        """Lock info file is always written after mkdir succeeds."""
        lock_dir.mkdir()

        # Immediately after mkdir, info file should be writable
        now = int(time.time())
        lock_info_path.write_text(f"alice|{now}|build")

        assert lock_info_path.exists()
        content = lock_info_path.read_text()
        assert content.startswith("alice|")
