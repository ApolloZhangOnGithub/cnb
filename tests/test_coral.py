"""Tests for CoralManager and CoralPoker concerns."""

import time
from pathlib import Path
from unittest.mock import patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.coral import CoralManager, CoralPoker

PREFIX = "cc-test"


def make_cfg(tmp_path: Path, sessions: list[str] | None = None) -> DispatcherConfig:
    sessions = sessions or ["alice"]
    cd = tmp_path / ".claudes"
    cd.mkdir(exist_ok=True)
    db_path = cd / "board.db"
    db_path.touch()
    return DispatcherConfig(
        prefix=PREFIX,
        project_root=tmp_path,
        claudes_dir=cd,
        sessions_dir=cd / "sessions",
        board_db=db_path,
        suspended_file=cd / "suspended",
        board_sh="./board",
        coral_sess=f"{PREFIX}-lead",
        dispatcher_session=f"{PREFIX}-dispatcher",
        log_dir=cd / "logs",
        okr_dir=cd / "okr",
        dev_sessions=sessions,
    )


# ===========================================================================
# CoralManager
# ===========================================================================


class TestCoralManager:
    def test_record_boot(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cm = CoralManager(cfg)
        cm.record_boot("alice")
        assert "alice" in cm.boot_times

    def test_in_grace_period_true(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cm = CoralManager(cfg)
        now = int(time.time())
        cm.boot_times["alice"] = now
        assert cm.in_grace_period("alice", now + 10) is True

    def test_in_grace_period_false_after_expiry(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cm = CoralManager(cfg)
        now = int(time.time())
        cm.boot_times["alice"] = now
        assert cm.in_grace_period("alice", now + CoralManager.BOOT_GRACE + 1) is False

    def test_in_grace_period_false_for_unknown(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cm = CoralManager(cfg)
        assert cm.in_grace_period("unknown", int(time.time())) is False

    def test_agent_cmd_defaults_to_claude(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cm = CoralManager(cfg)
        with patch.dict("os.environ", {}, clear=True):
            cmd = cm._agent_cmd()
        assert cmd.startswith("claude --name dispatcher")

    def test_agent_cmd_codex_highest_permissions(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cm = CoralManager(cfg)
        with patch.dict("os.environ", {"CNB_AGENT": "codex"}, clear=True):
            cmd = cm._agent_cmd()
        assert cmd.startswith("codex ")
        assert "--dangerously-bypass-approvals-and-sandbox" in cmd
        assert "--ask-for-approval" not in cmd
        assert "--sandbox" not in cmd
        assert "--cd" in cmd

    @patch("lib.concerns.coral.is_suspended", return_value=False)
    @patch("lib.concerns.coral.is_claude_running")
    def test_tick_ensures_coral_when_devs_alive(self, mock_running, mock_susp, tmp_path):
        cfg = make_cfg(tmp_path, ["alice"])
        cm = CoralManager(cfg)

        mock_running.side_effect = lambda sess: sess == f"{PREFIX}-alice"

        with patch.object(cm, "_ensure") as mock_ensure:
            cm.tick(1000)
            mock_ensure.assert_called_once()

    @patch("lib.concerns.coral.is_suspended", return_value=False)
    @patch("lib.concerns.coral.is_claude_running", return_value=False)
    def test_tick_skips_when_no_devs(self, mock_running, mock_susp, tmp_path):
        cfg = make_cfg(tmp_path, ["alice"])
        cm = CoralManager(cfg)

        with patch.object(cm, "_ensure") as mock_ensure:
            cm.tick(1000)
            mock_ensure.assert_not_called()

    @patch("lib.concerns.coral.is_suspended", return_value=True)
    @patch("lib.concerns.coral.is_claude_running", return_value=True)
    def test_tick_skips_when_dispatcher_suspended(self, mock_running, mock_susp, tmp_path):
        cfg = make_cfg(tmp_path, ["alice"])
        cm = CoralManager(cfg)

        with patch.object(cm, "_ensure") as mock_ensure:
            cm.tick(1000)
            mock_ensure.assert_not_called()


# ===========================================================================
# CoralPoker
# ===========================================================================


class TestCoralPoker:
    @patch("lib.concerns.coral.tmux_send", return_value=True)
    @patch("lib.concerns.coral.pane_md5", return_value="same")
    @patch("lib.concerns.coral.tmux", return_value="output\n❯")
    @patch("lib.concerns.coral.is_claude_running", return_value=True)
    @patch("lib.concerns.coral.tmux_ok", return_value=True)
    @patch("time.sleep")
    def test_poke_sends_message(self, mock_sleep, mock_ok, mock_running, mock_tmux, mock_md5, mock_send, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = CoralPoker(cfg)

        result = poker.poke("hello coral")
        assert result is True
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == "hello coral"

    @patch("lib.concerns.coral.is_claude_running", return_value=False)
    @patch("lib.concerns.coral.tmux_ok", return_value=False)
    def test_poke_fails_when_offline(self, mock_ok, mock_running, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = CoralPoker(cfg)

        result = poker.poke("hello")
        assert result is False

    @patch("lib.concerns.coral.tmux", return_value="output\n❯ typing something long")
    @patch("lib.concerns.coral.is_claude_running", return_value=True)
    @patch("lib.concerns.coral.tmux_ok", return_value=True)
    def test_poke_skips_when_typing(self, mock_ok, mock_running, mock_tmux, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = CoralPoker(cfg)

        result = poker.poke("hello")
        assert result is False

    @patch("lib.concerns.coral.tmux_send", return_value=True)
    @patch("lib.concerns.coral.pane_md5")
    @patch("lib.concerns.coral.tmux", return_value="output\n❯")
    @patch("lib.concerns.coral.is_claude_running", return_value=True)
    @patch("lib.concerns.coral.tmux_ok", return_value=True)
    @patch("time.sleep")
    def test_poke_skips_when_pane_changing(
        self, mock_sleep, mock_ok, mock_running, mock_tmux, mock_md5, mock_send, tmp_path
    ):
        cfg = make_cfg(tmp_path)
        poker = CoralPoker(cfg)

        call_count = [0]

        def changing_md5(sess):
            call_count[0] += 1
            return f"hash{call_count[0]}"

        mock_md5.side_effect = changing_md5

        result = poker.poke("hello")
        assert result is False
        mock_send.assert_not_called()

    @patch("lib.concerns.coral.db")
    @patch("lib.concerns.coral.tmux_ok", return_value=True)
    @patch("lib.concerns.coral.is_claude_running", return_value=True)
    @patch("lib.concerns.coral.tmux", return_value="output\n❯")
    @patch("lib.concerns.coral.pane_md5", return_value="same")
    @patch("lib.concerns.coral.tmux_send", return_value=True)
    @patch("time.sleep")
    def test_tick_pokes_on_unread(
        self, mock_sleep, mock_send, mock_md5, mock_tmux, mock_running, mock_ok, mock_db, tmp_path
    ):
        cfg = make_cfg(tmp_path)
        poker = CoralPoker(cfg)
        mock_db.return_value.scalar.return_value = 3

        poker.tick(int(time.time()) + 200)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][1]
        assert "未读" in msg
