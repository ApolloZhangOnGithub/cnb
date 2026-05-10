"""Tests for lib/board_mail — persistent mail with CC and threading."""

import json
import sqlite3
from pathlib import Path

import pytest

from lib.board_db import BoardDB
from lib.board_mail import cmd_mail
from tests.conftest import SCHEMA_VERSION

SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"


def _setup_db(tmp_path: Path) -> BoardDB:
    db_path = tmp_path / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text())
    for name in ("alice", "bob", "charlie"):
        conn.execute("INSERT INTO sessions(name) VALUES (?)", (name,))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()
    return BoardDB(db_path)


def _send_mail(db: BoardDB, sender: str = "alice", to: str = "bob", subject: str = "Test", body: str = "hello") -> int:
    """Insert a mail row directly and return its id."""
    return db.execute(
        "INSERT INTO mail(sender, recipients, cc, subject, body) VALUES (?, ?, '[]', ?, ?)",
        (sender, json.dumps([to]), subject, body),
    )


class TestCmdRouting:
    def test_unknown_subcmd_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["bogus"])

    def test_default_is_list(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", [])
        out = capsys.readouterr().out
        assert "邮箱为空" in out


class TestMailSend:
    def test_sends_mail(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", ["send", "--to", "bob", "--subject", "Hi", "--body", "Hello Bob"])
        out = capsys.readouterr().out
        assert "OK mail #1 sent" in out
        assert "bob" in out

    def test_sends_with_cc(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", ["send", "--to", "bob", "--cc", "charlie", "--subject", "FYI", "--body", "Update"])
        out = capsys.readouterr().out
        assert "OK" in out
        assert "CC: charlie" in out

    def test_multiple_recipients(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", ["send", "--to", "bob,charlie", "--subject", "Team", "--body", "Hello all"])
        out = capsys.readouterr().out
        assert "bob" in out
        assert "charlie" in out

    def test_stored_in_db(self, tmp_path):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", ["send", "--to", "bob", "--subject", "Test", "--body", "Content"])
        row = db.query_one("SELECT sender, recipients, subject, body FROM mail WHERE id=1")
        assert row is not None
        assert row[0] == "alice"
        assert json.loads(row[1]) == ["bob"]
        assert row[2] == "Test"
        assert row[3] == "Content"

    def test_missing_fields_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["send", "--to", "bob"])
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["send", "--subject", "Hi"])

    def test_no_recipients_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["send", "--to", "", "--subject", "Hi", "--body", "x"])

    def test_body_from_positional(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", ["send", "--to", "bob", "--subject", "Hi", "body", "from", "positional"])
        out = capsys.readouterr().out
        assert "OK" in out
        row = db.query_one("SELECT body FROM mail WHERE id=1")
        assert row is not None
        assert row[0] == "body from positional"


class TestMailList:
    def test_empty_list(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_mail(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "邮箱为空" in out

    def test_shows_mail_for_recipient(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob", subject="Important", body="Read this")
        cmd_mail(db, "bob", ["list"])
        out = capsys.readouterr().out
        assert "邮箱" in out
        assert "Important" in out
        assert "alice" in out

    def test_shows_mail_for_sender(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "#1" in out

    def test_unread_filter(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        mid = _send_mail(db, sender="alice", to="bob")
        db.execute("UPDATE mail SET read_by=? WHERE id=?", (json.dumps(["bob"]), mid))
        cmd_mail(db, "bob", ["list", "--unread"])
        out = capsys.readouterr().out
        assert "无未读邮件" in out

    def test_unread_marker(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["list"])
        out = capsys.readouterr().out
        assert "●" in out
        assert "1 封未读" in out

    def test_all_flag(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "charlie", ["list", "--all"])
        out = capsys.readouterr().out
        assert "#1" in out

    def test_list_does_not_match_name_prefix(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["list"])
        out = capsys.readouterr().out
        assert "#1" in out
        capsys.readouterr()
        cmd_mail(db, "charlie", ["list"])
        out = capsys.readouterr().out
        assert "邮箱为空" in out


class TestMailRead:
    def test_reads_mail(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob", subject="Review", body="Please review PR")
        cmd_mail(db, "bob", ["read", "1"])
        out = capsys.readouterr().out
        assert "Mail #1" in out
        assert "alice" in out
        assert "bob" in out
        assert "Review" in out
        assert "Please review PR" in out

    def test_marks_as_read(self, tmp_path):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["read", "1"])
        row = db.query_one("SELECT read_by FROM mail WHERE id=1")
        assert row is not None
        read_by = json.loads(row[0])
        assert "bob" in read_by

    def test_read_idempotent(self, tmp_path):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["read", "1"])
        cmd_mail(db, "bob", ["read", "1"])
        row = db.query_one("SELECT read_by FROM mail WHERE id=1")
        assert row is not None
        read_by = json.loads(row[0])
        assert read_by.count("bob") == 1

    def test_nonexistent_exits(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["read", "999"])
        out = capsys.readouterr().out
        assert "不存在" in out

    def test_no_args_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["read"])

    def test_invalid_id_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["read", "abc"])

    def test_hash_prefix_stripped(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["read", "#1"])
        out = capsys.readouterr().out
        assert "Mail #1" in out

    def test_shows_thread_replies(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        mid = _send_mail(db, sender="alice", to="bob", subject="Q", body="question")
        db.execute(
            "INSERT INTO mail(thread_id, sender, recipients, subject, body) VALUES (?, 'bob', ?, 'Re: Q', 'answer')",
            (mid, json.dumps(["alice"])),
        )
        cmd_mail(db, "alice", ["read", str(mid)])
        out = capsys.readouterr().out
        assert "1 条回复" in out
        assert "answer" in out


class TestMailReply:
    def test_replies_to_mail(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob", subject="Question", body="What do you think?")
        cmd_mail(db, "bob", ["reply", "1", "Looks good to me"])
        out = capsys.readouterr().out
        assert "OK mail #2 reply sent" in out
        assert "Re: Question" in out

    def test_reply_sets_thread_id(self, tmp_path):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["reply", "1", "reply body"])
        row = db.query_one("SELECT thread_id, sender, body FROM mail WHERE id=2")
        assert row is not None
        assert row[0] == 1
        assert row[1] == "bob"
        assert row[2] == "reply body"

    def test_reply_to_reply_uses_root_thread(self, tmp_path):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["reply", "1", "first reply"])
        cmd_mail(db, "alice", ["reply", "2", "second reply"])
        row = db.query_one("SELECT thread_id FROM mail WHERE id=3")
        assert row is not None
        assert row[0] == 1

    def test_reply_includes_all_parties(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        db.execute(
            "INSERT INTO mail(sender, recipients, cc, subject, body) VALUES (?, ?, ?, ?, ?)",
            ("alice", json.dumps(["bob"]), json.dumps(["charlie"]), "Team", "discuss"),
        )
        cmd_mail(db, "bob", ["reply", "1", "agreed"])
        capsys.readouterr()
        row = db.query_one("SELECT recipients FROM mail WHERE id=2")
        assert row is not None
        recipients = json.loads(row[0])
        assert "alice" in recipients
        assert "charlie" in recipients
        assert "bob" not in recipients

    def test_reply_nonexistent_exits(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["reply", "999", "text"])
        out = capsys.readouterr().out
        assert "不存在" in out

    def test_reply_no_args_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit):
            cmd_mail(db, "alice", ["reply"])

    def test_reply_no_body_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        with pytest.raises(SystemExit):
            cmd_mail(db, "bob", ["reply", "1"])

    def test_reply_marks_self_as_read(self, tmp_path):
        db = _setup_db(tmp_path)
        _send_mail(db, sender="alice", to="bob")
        cmd_mail(db, "bob", ["reply", "1", "noted"])
        row = db.query_one("SELECT read_by FROM mail WHERE id=2")
        assert row is not None
        read_by = json.loads(row[0])
        assert "bob" in read_by

    def test_re_prefix_not_duplicated(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        db.execute(
            "INSERT INTO mail(sender, recipients, subject, body) VALUES (?, ?, ?, ?)",
            ("alice", json.dumps(["bob"]), "Re: Original", "follow up"),
        )
        cmd_mail(db, "bob", ["reply", "1", "got it"])
        row = db.query_one("SELECT subject FROM mail WHERE id=2")
        assert row is not None
        assert row[0] == "Re: Original"
