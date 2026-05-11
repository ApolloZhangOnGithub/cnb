"""board_files — shared file listing and retrieval."""

import glob
import os

from lib.board_db import BoardDB
from lib.common import escape_like


def cmd_files(db: BoardDB) -> None:
    assert db.env is not None
    print("=== 共享文件 ===\n")
    rows = db.query("SELECT hash, original_name, sender, ts FROM files ORDER BY ts DESC")
    if not rows:
        print("  (none)")
    else:
        for h, orig, sender, date in rows:
            size = 0
            for f in glob.glob(str(db.env.claudes_dir / "files" / f"{h}.*")):
                if os.path.isfile(f):
                    size = os.path.getsize(f)
                    break
            print(f"  {h:<14s} {orig:<30s} {size:>6d} bytes  by {sender:<6s}  {date}")
    print("\n查看文件: board get <hash前缀或文件名>")


def cmd_get(db: BoardDB, args: list[str]) -> None:
    assert db.env is not None
    if not args:
        print("Usage: board get <hash-prefix|filename>")
        raise SystemExit(1)
    query = args[0]
    row = db.query_one(
        "SELECT hash, original_name, sender, ts, stored_path FROM files "
        "WHERE hash LIKE ? ESCAPE '\\' OR original_name=? LIMIT 1",
        (escape_like(query) + "%", query),
    )
    if not row:
        print(f"ERROR: no file matching '{query}'")
        raise SystemExit(1)
    h, orig, sender, date, path = row
    print("--- 文件信息 ---")
    print(f"  Name: {orig}")
    print(f"  Hash: {h}")
    print(f"  Sender: {sender}")
    print(f"  Date: {date}")
    print("\n--- 内容 ---")
    full_path = db.env.claudes_dir / path
    if full_path.is_file():
        print(full_path.read_text(), end="")
    else:
        print("(file content not on disk)")
