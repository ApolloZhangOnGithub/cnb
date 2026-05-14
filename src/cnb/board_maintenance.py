"""board_maintenance — data maintenance: prune, backup, restore."""

import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from lib.board_db import BoardDB
from lib.common import parse_flags

# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


def _parse_days(arg: str) -> int:
    try:
        target = datetime.strptime(arg, "%Y-%m-%d")
        return (datetime.now() - target).days
    except ValueError:
        pass
    try:
        return int(arg)
    except ValueError:
        print(f"ERROR: invalid date/days: '{arg}'. Use YYYY-MM-DD or a number.")
        raise SystemExit(1)


def _days_ago_ts(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def cmd_prune(db: BoardDB, args: list[str]) -> None:
    if "--help" in args or "-h" in args:
        print("Usage: board prune [--before YYYY-MM-DD|DAYS] [--dry-run]")
        return
    flags, positional = parse_flags(
        args,
        value_flags={"before": ["--before"]},
        bool_flags={"dry_run": ["--dry-run"]},
    )
    if positional:
        print("Usage: board prune [--before YYYY-MM-DD|DAYS] [--dry-run]")
        raise SystemExit(1)

    before_days = _parse_days(str(flags.get("before", "90")))
    dry_run = bool(flags.get("dry_run"))
    cutoff = _days_ago_ts(before_days)

    # Count what would be deleted
    old_inbox = (
        db.scalar(
            "SELECT COUNT(*) FROM inbox WHERE message_id IN (SELECT id FROM messages WHERE ts < ?)",
            (cutoff,),
        )
        or 0
    )
    old_messages = (
        db.scalar(
            "SELECT COUNT(*) FROM messages WHERE ts < ?",
            (cutoff,),
        )
        or 0
    )

    # Also count old read inbox entries (not just those linked to old messages)
    old_read_inbox = (
        db.scalar(
            "SELECT COUNT(*) FROM inbox WHERE read=1 AND delivered_at < ?",
            (cutoff,),
        )
        or 0
    )

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


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------


def cmd_backup(db: BoardDB, args: list[str]) -> None:
    if "--help" in args or "-h" in args:
        print("Usage: board backup [--output <path>]")
        return
    flags, positional = parse_flags(args, value_flags={"output": ["--output"]})
    if positional:
        print("Usage: board backup [--output <path>]")
        raise SystemExit(1)

    output_str = flags.get("output")
    output = Path(str(output_str)) if output_str else None
    if output is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        output = db.db_path.parent / f"backup-{stamp}.db"

    shutil.copy2(db.db_path, output)

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
    if "--help" in args or "-h" in args:
        print("Usage: board restore <backup-file> [--force]")
        return
    flags, positional = parse_flags(args, bool_flags={"force": ["--force", "-f"]})
    force = bool(flags.get("force"))

    if not positional:
        print("Usage: board restore <backup-file> [--force]")
        raise SystemExit(1)

    source = Path(positional[0])
    if not source.exists():
        print(f"ERROR: backup file not found: {source}")
        raise SystemExit(1)

    try:
        conn = sqlite3.connect(str(source))
        conn.execute("PRAGMA integrity_check")
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
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

    tmp = db.db_path.with_suffix(".db.restore-tmp")
    shutil.copy2(source, tmp)
    tmp.replace(db.db_path)

    print(f"OK restored from {source}")
    print("  Sessions may need to restart to pick up changes.")
