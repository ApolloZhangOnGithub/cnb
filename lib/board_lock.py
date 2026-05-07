"""board_lock — git lock coordination: git-lock / git-unlock / git-lock-status."""

import subprocess
import time

from lib.board_db import BoardDB, ts

GIT_LOCK_TTL = 60


def _cleanup_stale(db: BoardDB) -> None:
    now_epoch = int(time.time())
    db.execute("DELETE FROM git_locks WHERE expires_at < ?", (now_epoch,))


def cmd_git_lock(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    reason = " ".join(args) if args else "git operation"

    _cleanup_stale(db)

    expires = int(time.time()) + GIT_LOCK_TTL
    did_insert = db.execute_changes(
        "INSERT OR IGNORE INTO git_locks(id, session, reason, expires_at) VALUES (1, ?, ?, ?)",
        (name, reason, expires),
    )
    if did_insert:
        print(f"OK git-lock acquired by {name} (expires in {GIT_LOCK_TTL}s)")
        return

    holder = db.scalar("SELECT session FROM git_locks WHERE id=1")
    if holder == name:
        new_expires = int(time.time()) + GIT_LOCK_TTL
        db.execute(
            "UPDATE git_locks SET expires_at=?, reason=?, "
            "acquired_at=strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime') WHERE id=1",
            (new_expires, reason),
        )
        print(f"OK git-lock extended (held by you, expires in {GIT_LOCK_TTL}s)")
        return

    expires_at = db.scalar("SELECT expires_at FROM git_locks WHERE id=1") or 0
    remaining = expires_at - int(time.time())
    lock_reason = db.scalar("SELECT reason FROM git_locks WHERE id=1") or ""
    print(
        f"BLOCKED: git lock held by '{holder}' ({lock_reason}, expires in {remaining}s)",
    )
    print(f"  Wait and retry, or force with: ./board --as {identity} git-unlock --force")
    raise SystemExit(1)


def cmd_git_unlock(db: BoardDB, identity: str, args: list[str]) -> None:
    assert db.env is not None
    name = identity.lower()
    force = "--force" in args

    _cleanup_stale(db)

    holder = db.scalar("SELECT session FROM git_locks WHERE id=1")
    if not holder:
        print("OK git lock is already free")
        return

    if holder != name and not force:
        print(f"ERROR: git lock held by '{holder}', not you. Use --force to override.")
        raise SystemExit(1)

    if holder != name and force:
        print(f"WARN: force-releasing git lock held by '{holder}'")
        now = ts()
        msg_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'SYSTEM', ?, ?)",
            (now, holder, f"[GIT-LOCK] {name} force-released your git lock"),
        )
        db.execute("INSERT INTO inbox(session, message_id) VALUES (?, ?)", (holder, msg_id))

    db.execute("DELETE FROM git_locks WHERE id=1")
    print("OK git-lock released")

    index_lock = db.env.project_root / ".git" / "index.lock"
    if index_lock.exists():
        r = subprocess.run(
            ["pgrep", "-f", f"git.*{db.env.project_root}"],
            capture_output=True,
        )
        if r.returncode != 0:
            index_lock.unlink()
            print("  Also removed stale .git/index.lock")
        else:
            print("  WARN: .git/index.lock exists and a git process is running")


def cmd_git_lock_status(db: BoardDB) -> None:
    assert db.env is not None
    _cleanup_stale(db)

    row = db.query_one("SELECT session, reason, acquired_at, expires_at FROM git_locks WHERE id=1")
    if not row:
        print("FREE: no session holds the git lock")
    else:
        holder, reason, acquired, expires_at = row
        remaining = expires_at - int(time.time())
        print(f"LOCKED by {holder}")
        print(f"  Reason: {reason}")
        print(f"  Acquired: {acquired}")
        print(f"  Expires in: {remaining}s")

    index_lock = db.env.project_root / ".git" / "index.lock"
    if index_lock.exists():
        try:
            lock_age = int(time.time()) - int(index_lock.stat().st_mtime)
        except OSError:
            lock_age = 0
        print(f"  .git/index.lock exists (age: {lock_age}s)")
