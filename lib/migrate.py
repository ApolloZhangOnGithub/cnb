"""migrate — schema migration runner for cnb.

Tracks applied migrations in the `meta` table (key='schema_version').
Migrations live in the `migrations/` directory alongside schema.sql.
"""

import sqlite3
import sys
from pathlib import Path


def _migrations_dir(claudes_home: Path) -> Path:
    d = claudes_home / "migrations"
    if not d.is_dir():
        print(f"FATAL: migrations directory not found: {d}", file=sys.stderr)
        raise SystemExit(1)
    return d


def _applied_versions(c: sqlite3.Connection) -> set[int]:
    """Return the set of already-applied migration version numbers."""
    try:
        row = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row:
            return set(range(1, int(row[0]) + 1))
    except sqlite3.OperationalError:
        pass  # meta table may not exist yet (first init)
    return set()


def _record_version(c: sqlite3.Connection, version: int) -> None:
    c.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(version),),
    )


def _discover_migrations(mdir: Path) -> list[tuple[int, Path]]:
    """Find migration files named NNN_description.sql, sorted by version."""
    migs: list[tuple[int, Path]] = []
    for f in mdir.glob("*.sql"):
        prefix = f.name[:3]
        if prefix.isdigit():
            migs.append((int(prefix), f))
    migs.sort()
    return migs


def run_migrations(db_path: Path, claudes_home: Path) -> int:
    """Apply all pending migrations. Returns number of migrations applied."""
    mdir = _migrations_dir(claudes_home)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    applied = 0
    try:
        done = _applied_versions(conn)
        all_migs = _discover_migrations(mdir)

        for ver, path in all_migs:
            if ver in done:
                continue
            sql = path.read_text()
            print(f"  Applying migration {path.name} ...", end=" ", flush=True)
            conn.executescript(sql)
            _record_version(conn, ver)
            conn.commit()
            print("OK")
            applied += 1

    except Exception as e:
        conn.rollback()
        print(f"\nFATAL: migration failed: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    finally:
        conn.close()

    return applied


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Run pending migrations. Called from init and doctor."""
    # Resolve CLAUDES_HOME relative to this file
    claudes_home = Path(__file__).resolve().parent.parent
    db_path = claudes_home / ".claudes" / "board.db"

    # Prefer the DB path from the current project
    from pathlib import Path as _P

    cwd_db = _P.cwd() / ".claudes" / "board.db"
    if cwd_db.exists():
        db_path = cwd_db

    if not db_path.exists():
        print("ERROR: board.db not found. Run: cnb init <sessions>", flush=True)
        raise SystemExit(1)

    n = run_migrations(db_path, claudes_home)
    if n > 0:
        print(f"Applied {n} migration(s).")


if __name__ == "__main__":
    main()
