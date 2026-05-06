"""board_maintenance — data maintenance: prune, backup, restore."""

import shutil
import time
from pathlib import Path

from lib.board_db import BoardDB

# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


def cmd_prune(db: BoardDB, args: list[str]) -> None:
    """Prune old messages and inbox entries.

    Usage: board --as <name> prune [--before YYYY-MM-DD] [--keep N] [--dry-run]
    """
    usage = "Usage: board --as <name> prune [--before YYYY-MM-DD] [--keep N] [--dry-run]"

    before_days = 90  # default: keep 90 days
    keep_count: int | None = None
    dry_run = False
    positional: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--before" and i + 1 < len(args):
            before_days = _parse_days(args[i + 1])
            i += 2
        elif args[i] == "--keep" and i + 1 < len(args):
            try:
                keep_count = int(args[i + 1])
            except ValueError:
                print(f"ERROR: --keep requires a number, got '{args[i + 1]}'")
                raise SystemExit(1)
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        else:
            positional.append(args[i])
            i += 1

    if positional:
        print(usage)
        raise SystemExit(1)

    cutoff = _days_ago_ts(before_days)

    # Count what would be deleted
    old_inbox = db.scalar(
        "SELECT COUNT(*) FROM inbox WHERE message_id IN "
        "(SELECT id FROM messages WHERE ts < ?)",
        (cutoff,),
    ) or 0
    old_messages = db.scalar(
        "SELECT COUNT(*) FROM messages WHERE ts < ?",
        (cutoff,),
    ) or 0

    # Also count old read inbox entries (not just those linked to old messages)
    old_read_inbox = db.scalar(
        "SELECT COUNT(*) FROM inbox WHERE read=1 AND "
        "delivered_at < ?",
        (cutoff,),
    ) or 0

    if dry_run:
        print("=== DRY RUN: would delete ===")
        print(f"  {old_messages} messages older than {before_days} days")
        print(f"  {old_inbox} inbox entries referencing old messages")
        print(f"  {old_read_inbox} already-read inbox entries")
        total = old_messages + old_inbox + old_read_inbox
        if total == 0:
            print("  Nothing to prune.")
        else:
            print(f"  Total: {total} rows")
        return

    total_deleted = 0

    # Delete old messages (cascades to inbox via FK)
    if old_messages > 0:
        db.execute("DELETE FROM messages WHERE ts < ?", (cutoff,))
        total_deleted += old_messages

    # Delete old read inbox entries (not covered by message FK cascade)
    if old_read_inbox > 0:
        db.execute("DELETE FROM inbox WHERE read=1 AND delivered_at < ?", (cutoff,))
        total_deleted += old_read_inbox

    if total_deleted == 0:
        print("OK nothing to prune")
    else:
        print(f"OK pruned {total_deleted} rows (messages older than {before_days} days)")


def _parse_days(arg: str) -> int:
    """Parse a date or day-count argument.

    Accepts: 'YYYY-MM-DD' (exact date), or integer (days ago).
    """
    from datetime import datetime

    try:
        target = datetime.strptime(arg, "%Y-%m-%d")
        now = datetime.now()
        return (now - target).days
    except ValueError:
        pass
    try:
        return int(arg)
    except ValueError:
        print(f"ERROR: invalid date/days: '{arg}'. Use YYYY-MM-DD or a number.")
        raise SystemExit(1)


def _days_ago_ts(days: int) -> str:
    """Return a timestamp string for *days* ago."""
    from datetime import datetime, timedelta

    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------


def cmd_backup(db: BoardDB, args: list[str]) -> None:
    """Backup board.db to a timestamped file.

    Usage: board backup [--output <path>]
    """
    import shutil as _shutil

    output: Path | None = None
    for arg in args:
        if arg.startswith("--output="):
            output = Path(arg.split("=", 1)[1])
        elif arg == "--output" and len(args) > args.index(arg) + 1:
            output = Path(args[args.index(arg) + 1])
        elif arg == "--help":
            print("Usage: board backup [--output <path>]")
            return

    if output is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        output = db.db_path.parent / f"backup-{stamp}.db"

    _shutil.copy2(db.db_path, output)

    # Verify the backup
    import sqlite3

    try:
        conn = sqlite3.connect(str(output))
        conn.execute("SELECT COUNT(*) FROM meta")
        conn.close()
    except sqlite3.Error as e:
        print(f"ERROR: backup verification failed: {e}")
        if output.exists():
            output.unlink()
        raise SystemExit(1)

    size = output.stat().st_size
    print(f"OK backup saved: {output}")
    print(f"  Size: {size} bytes")


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------


def cmd_restore(db: BoardDB, args: list[str]) -> None:
    """Restore board.db from a backup file.

    Usage: board restore <backup-file> [--force]
    """
    force = False
    source: Path | None = None
    for arg in args:
        if arg in ("--force", "-f"):
            force = True
        elif arg in ("--help", "-h"):
            print("Usage: board restore <backup-file> [--force]")
            print()
            print("  --force  Skip confirmation prompt")
            return
        else:
            source = Path(arg)

    if source is None:
        print("Usage: board restore <backup-file> [--force]")
        raise SystemExit(1)
    if not source.exists():
        print(f"ERROR: backup file not found: {source}")
        raise SystemExit(1)

    # Verify the backup
    import sqlite3

    try:
        conn = sqlite3.connect(str(source))
        conn.execute("PRAGMA integrity_check")
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        if not tables:
            print("ERROR: backup file contains no tables")
            raise SystemExit(1)
    except sqlite3.Error as e:
        print(f"ERROR: invalid backup file: {e}")
        raise SystemExit(1)

    if not force:
        print("About to restore board.db from:")
        print(f"  {source}")
        print("This will OVERWRITE the current database.")
        try:
            answer = input("Continue? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return

    # Atomic restore: copy to temp, rename
    tmp = db.db_path.with_suffix(".db.restore-tmp")
    shutil.copy2(source, tmp)
    tmp.replace(db.db_path)

    print(f"OK restored from {source}")
    print("  Sessions may need to restart to pick up changes.")
