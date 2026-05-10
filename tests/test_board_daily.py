"""Tests for board_daily: per-session daily report command."""

import pytest

from lib.board_daily import cmd_daily


class TestCmdDaily:
    def test_writes_daily_report_to_current_shift(self, db, tmp_project, capsys):
        cmd_daily(db, "alice", [])

        out = capsys.readouterr().out
        report = tmp_project / ".claudes" / "dailies" / "001" / "alice.md"

        assert "OK 日报已保存" in out
        assert report.exists()
        text = report.read_text()
        assert "# 日报 — alice" in text

    def test_appends_extra_context(self, db, tmp_project, capsys):
        cmd_daily(db, "alice", ["handoff", "ready"])
        capsys.readouterr()

        report = tmp_project / ".claudes" / "dailies" / "001" / "alice.md"
        text = report.read_text()

        assert "## 补充" in text
        assert "handoff ready" in text

    def test_uses_existing_shift_directory(self, db, tmp_project, capsys):
        dailies = tmp_project / ".claudes" / "dailies"
        (dailies / "003").mkdir(parents=True)
        (dailies / ".next_shift").write_text("4\n")

        cmd_daily(db, "alice", [])
        capsys.readouterr()

        assert (dailies / "003" / "alice.md").exists()
        assert not (dailies / "004" / "alice.md").exists()

    def test_rejects_unknown_identity(self, db):
        with pytest.raises(SystemExit):
            cmd_daily(db, "unknown", [])
