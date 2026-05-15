import shutil
import sqlite3

import pytest

from lib.board_maintenance import cmd_backup, cmd_prune, cmd_restore

OLD_TS = "2000-01-01 00:00:00"
NEW_TS = "2999-01-01 00:00:00"


def _message(db, ts: str, recipient: str = "alice") -> int:
    return db.execute(
        "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
        (ts, "bob", recipient, f"message at {ts}"),
    )


def _inbox(db, message_id: int, *, read: int = 0, delivered_at: str = NEW_TS) -> int:
    return db.execute(
        "INSERT INTO inbox(session, message_id, delivered_at, read) VALUES (?, ?, ?, ?)",
        ("alice", message_id, delivered_at, read),
    )


def test_prune_dry_run_reports_old_messages_and_inbox_without_deleting(db, capsys):
    old_message = _message(db, OLD_TS)
    new_message = _message(db, NEW_TS)
    _inbox(db, old_message, read=0, delivered_at=OLD_TS)
    _inbox(db, new_message, read=1, delivered_at=OLD_TS)

    cmd_prune(db, ["--before", "90", "--dry-run"])

    out = capsys.readouterr().out
    assert "1 messages older than 90 days" in out
    assert "1 inbox entries referencing old messages" in out
    assert "1 already-read inbox entries" in out
    assert db.scalar("SELECT COUNT(*) FROM messages") == 2
    assert db.scalar("SELECT COUNT(*) FROM inbox") == 2


def test_prune_deletes_old_messages_and_stale_read_inbox(db, capsys):
    old_message = _message(db, OLD_TS)
    new_message = _message(db, NEW_TS)
    _inbox(db, old_message, read=0, delivered_at=OLD_TS)
    stale_read_inbox = _inbox(db, new_message, read=1, delivered_at=OLD_TS)

    cmd_prune(db, ["--before", "90"])

    out = capsys.readouterr().out
    assert "OK pruned 2 rows" in out
    assert db.scalar("SELECT COUNT(*) FROM messages WHERE id=?", (old_message,)) == 0
    assert db.scalar("SELECT COUNT(*) FROM messages WHERE id=?", (new_message,)) == 1
    assert db.scalar("SELECT COUNT(*) FROM inbox WHERE id=?", (stale_read_inbox,)) == 0


def test_backup_writes_verifiable_database_to_custom_output(db, tmp_path, capsys):
    output = tmp_path / "manual-backup.db"

    cmd_backup(db, ["--output", str(output)])

    out = capsys.readouterr().out
    assert f"OK backup saved: {output}" in out
    assert output.exists()
    conn = sqlite3.connect(str(output))
    try:
        assert conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() is not None
    finally:
        conn.close()


def test_backup_removes_output_when_verification_fails(db, tmp_path, monkeypatch, capsys):
    output = tmp_path / "bad-backup.db"

    def write_invalid_backup(_source, destination):
        destination.write_text("not sqlite")

    monkeypatch.setattr(shutil, "copy2", write_invalid_backup)

    with pytest.raises(SystemExit):
        cmd_backup(db, ["--output", str(output)])

    assert "ERROR: backup verification failed" in capsys.readouterr().out
    assert not output.exists()


def test_restore_force_replaces_current_database(db, tmp_path, capsys):
    backup = tmp_path / "restore-source.db"
    shutil.copy2(db.db_path, backup)
    conn = sqlite3.connect(str(backup))
    try:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('restore-test', 'from-backup')")
        conn.commit()
    finally:
        conn.close()

    assert db.scalar("SELECT value FROM meta WHERE key='restore-test'") is None

    cmd_restore(db, [str(backup), "--force"])

    out = capsys.readouterr().out
    assert f"OK restored from {backup}" in out
    assert db.scalar("SELECT value FROM meta WHERE key='restore-test'") == "from-backup"
