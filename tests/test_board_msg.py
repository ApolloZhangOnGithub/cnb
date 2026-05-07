"""Tests for board_msg: send, inbox, ack, status, log commands."""

import pytest

from lib.board_msg import cmd_ack, cmd_inbox, cmd_log, cmd_send, cmd_status


class TestCmdSend:
    def test_send_basic(self, db, capsys):
        cmd_send(db, "alice", ["bob", "hello world"])
        assert "OK sent" in capsys.readouterr().out

    def test_send_creates_message_in_db(self, db, capsys):
        cmd_send(db, "alice", ["bob", "test message"])
        capsys.readouterr()
        row = db.query_one("SELECT sender, recipient, body FROM messages WHERE sender='alice'")
        assert row["sender"] == "alice"
        assert row["recipient"] == "bob"
        assert "test message" in row["body"]

    def test_send_delivers_to_inbox(self, db, capsys):
        cmd_send(db, "alice", ["bob", "check this"])
        capsys.readouterr()
        count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0")
        assert count == 1

    def test_send_to_all_delivers_to_everyone(self, db, capsys):
        cmd_send(db, "alice", ["all", "broadcast"])
        capsys.readouterr()
        for name in ["bob", "charlie"]:
            count = db.scalar(f"SELECT COUNT(*) FROM inbox WHERE session='{name}' AND read=0")
            assert count >= 1, f"{name} should receive broadcast"

    def test_send_empty_message_fails(self, db):
        with pytest.raises(SystemExit):
            cmd_send(db, "alice", ["bob"])

    def test_send_no_args_fails(self, db):
        with pytest.raises(SystemExit):
            cmd_send(db, "alice", [])

    def test_send_with_attachment(self, db, tmp_path, capsys):
        f = tmp_path / "test.txt"
        f.write_text("file content")
        cmd_send(db, "alice", ["bob", "see attached", "--attach", str(f)])
        out = capsys.readouterr().out
        assert "OK sent" in out
        row = db.query_one("SELECT body, attachment FROM messages WHERE sender='alice'")
        assert "附件" in row["body"]
        assert row["attachment"] is not None

    def test_send_attachment_missing_file(self, db):
        with pytest.raises(SystemExit):
            cmd_send(db, "alice", ["bob", "file", "--attach", "/nonexistent/file.txt"])

    def test_send_attachment_only_no_text(self, db, tmp_path, capsys):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c")
        cmd_send(db, "alice", ["bob", "--attach", str(f)])
        out = capsys.readouterr().out
        assert "OK sent" in out
        row = db.query_one("SELECT body FROM messages WHERE sender='alice'")
        assert "分享文件" in row["body"]


class TestCmdInbox:
    def test_empty_inbox(self, db, capsys):
        cmd_inbox(db, "alice")
        out = capsys.readouterr().out
        assert "收件箱为空" in out

    def test_inbox_shows_messages(self, db, capsys):
        cmd_send(db, "bob", ["alice", "hey there"])
        capsys.readouterr()

        cmd_inbox(db, "alice")
        out = capsys.readouterr().out
        assert "hey there" in out
        assert "bob" in out

    def test_inbox_shows_multiple_messages(self, db, capsys):
        cmd_send(db, "bob", ["alice", "first"])
        cmd_send(db, "charlie", ["alice", "second"])
        capsys.readouterr()

        cmd_inbox(db, "alice")
        out = capsys.readouterr().out
        assert "first" in out
        assert "second" in out

    def test_inbox_shows_task_queue(self, db, capsys):
        cmd_inbox(db, "alice")
        out = capsys.readouterr().out
        assert "任务队列" in out


class TestCmdAck:
    def test_ack_empty_inbox(self, db, capsys):
        cmd_ack(db, "alice")
        out = capsys.readouterr().out
        assert "已经是空的" in out

    def test_ack_clears_messages(self, db, capsys):
        cmd_send(db, "bob", ["alice", "hello"])
        capsys.readouterr()

        cmd_inbox(db, "alice")
        capsys.readouterr()

        cmd_ack(db, "alice")
        out = capsys.readouterr().out
        assert "1 条已清空" in out

        count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session='alice' AND read=0")
        assert count == 0

    def test_ack_only_clears_seen_messages(self, db, capsys):
        cmd_send(db, "bob", ["alice", "msg1"])
        capsys.readouterr()

        cmd_inbox(db, "alice")
        capsys.readouterr()

        cmd_send(db, "charlie", ["alice", "msg2"])
        capsys.readouterr()

        cmd_ack(db, "alice")
        capsys.readouterr()

        remaining = db.scalar("SELECT COUNT(*) FROM inbox WHERE session='alice' AND read=0")
        assert remaining == 1, "message arriving after inbox should not be acked"


class TestCmdStatus:
    def test_status_update(self, db, capsys):
        cmd_status(db, "alice", ["working on tests"])
        out = capsys.readouterr().out
        assert "OK status updated" in out

    def test_status_persisted_in_db(self, db, capsys):
        cmd_status(db, "alice", ["debugging issue 42"])
        capsys.readouterr()
        row = db.query_one("SELECT status FROM sessions WHERE name='alice'")
        assert "debugging issue 42" in row["status"]

    def test_status_no_args_fails(self, db):
        with pytest.raises(SystemExit):
            cmd_status(db, "alice", [])


class TestCmdLog:
    def test_log_shows_messages(self, db, capsys):
        cmd_send(db, "alice", ["bob", "hello"])
        cmd_send(db, "bob", ["alice", "world"])
        capsys.readouterr()

        cmd_log(db, "alice", [])
        out = capsys.readouterr().out
        assert "hello" in out
        assert "world" in out

    def test_log_limit(self, db, capsys):
        for i in range(5):
            cmd_send(db, "alice", ["bob", f"msg{i}"])
        capsys.readouterr()

        cmd_log(db, "alice", ["2"])
        out = capsys.readouterr().out
        lines = [l for l in out.strip().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_log_mine_filter(self, db, capsys):
        cmd_send(db, "alice", ["bob", "from alice"])
        cmd_send(db, "charlie", ["bob", "from charlie"])
        capsys.readouterr()

        cmd_log(db, "alice", ["--mine"])
        out = capsys.readouterr().out
        assert "from alice" in out
        assert "from charlie" not in out
