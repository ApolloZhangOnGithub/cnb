"""Tests for health monitoring concerns: SessionKeepAlive, HealthChecker, ResourceMonitor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.health import HealthChecker, ResourceMonitor, SessionKeepAlive
from lib.resources import BatteryInfo, CPUInfo, MemoryInfo

PREFIX = "cc-test"


def make_cfg(tmp_path: Path, sessions: list[str] | None = None) -> DispatcherConfig:
    sessions = sessions or ["alice", "bob"]
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


def _ok_resources():
    return (
        BatteryInfo(status="AC", pct=100, on_battery=False, remaining=""),
        MemoryInfo(status="OK", used_pct=50, pressure="normal"),
        CPUInfo(status="OK", usage=30),
    )


# ===========================================================================
# SessionKeepAlive
# ===========================================================================


class TestSessionKeepAlive:
    @patch("lib.concerns.health.is_claude_running", return_value=False)
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.is_suspended", return_value=False)
    def test_logs_exited_agent(self, mock_susp, mock_devs, mock_ok, mock_running, tmp_path, capsys):
        cfg = make_cfg(tmp_path)
        ka = SessionKeepAlive(cfg)
        ka.tick(1000)

    @patch("lib.concerns.health.is_claude_running", return_value=True)
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.is_suspended", return_value=False)
    def test_running_agent_no_action(self, mock_susp, mock_devs, mock_ok, mock_running, tmp_path):
        cfg = make_cfg(tmp_path)
        ka = SessionKeepAlive(cfg)
        ka.tick(1000)

    @patch("lib.concerns.health.is_claude_running", return_value=False)
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.is_suspended", return_value=True)
    def test_suspended_session_skipped(self, mock_susp, mock_devs, mock_ok, mock_running, tmp_path):
        cfg = make_cfg(tmp_path)
        ka = SessionKeepAlive(cfg)
        ka.tick(1000)


# ===========================================================================
# HealthChecker
# ===========================================================================


class TestHealthChecker:
    def _make(self, tmp_path):
        cfg = make_cfg(tmp_path, ["alice", "bob"])
        poker = MagicMock()
        poker.poke = MagicMock(return_value=True)
        coral = MagicMock()
        coral.in_grace_period = MagicMock(return_value=False)
        return cfg, poker, coral

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice", "bob"])
    def test_pokes_coral_with_status(self, mock_devs, mock_ok, mock_board, tmp_path):
        cfg, poker, coral = self._make(tmp_path)
        hc = HealthChecker(cfg, poker, coral)

        hc.tick(1000)
        poker.poke.assert_called_once()
        msg = poker.poke.call_args[0][0]
        assert "alice" in msg
        assert "bob" in msg

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    def test_interval_doubles_each_tick(self, mock_devs, mock_ok, mock_board, tmp_path):
        cfg, poker, coral = self._make(tmp_path)
        hc = HealthChecker(cfg, poker, coral)
        initial = hc.interval

        hc.tick(1000)
        assert hc.interval == initial * 2

        hc.tick(2000)
        assert hc.interval == initial * 4

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    def test_interval_capped_at_max(self, mock_devs, mock_ok, mock_board, tmp_path):
        cfg, poker, coral = self._make(tmp_path)
        hc = HealthChecker(cfg, poker, coral)

        for i in range(20):
            hc.tick(1000 + i * 1000)

        assert hc.interval <= HealthChecker.MAX

    @patch("lib.concerns.health.db")
    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.is_claude_running", return_value=True)
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.is_suspended", return_value=False)
    def test_all_idle_triggers_alert(self, mock_susp, mock_devs, mock_ok, mock_running, mock_board, mock_db, tmp_path):
        cfg, poker, coral = self._make(tmp_path)
        hc = HealthChecker(cfg, poker, coral)

        now = 5000
        mock_db.return_value.scalar.return_value = "2026-05-08 00:00:00"
        with patch("lib.concerns.health.date_to_epoch", return_value=now - HealthChecker.IDLE_THRESHOLD - 1):
            hc.tick(now)

        board_calls = [c for c in mock_board.call_args_list if "lead" in str(c)]
        assert len(board_calls) >= 1

    @patch("lib.concerns.health.db")
    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.is_claude_running", return_value=True)
    @patch("lib.concerns.health.tmux_ok", return_value=True)
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.is_suspended", return_value=False)
    def test_idle_alert_has_cooldown(self, mock_susp, mock_devs, mock_ok, mock_running, mock_board, mock_db, tmp_path):
        cfg, poker, coral = self._make(tmp_path)
        hc = HealthChecker(cfg, poker, coral)

        now = 5000
        mock_db.return_value.scalar.return_value = "2026-05-08 00:00:00"
        with patch("lib.concerns.health.date_to_epoch", return_value=now - HealthChecker.IDLE_THRESHOLD - 1):
            hc.tick(now)
            assert any("lead" in str(c) for c in mock_board.call_args_list)

            mock_board.reset_mock()
            hc.tick(now + 100)
            second_count = len([c for c in mock_board.call_args_list if "lead" in str(c)])
            assert second_count == 0, "should not re-alert within 1 hour"


# ===========================================================================
# ResourceMonitor
# ===========================================================================


class TestResourceMonitor:
    @patch("lib.concerns.health.tmux_send")
    @patch("lib.concerns.health.is_claude_running", return_value=True)
    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_critical_battery_alerts(
        self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, mock_running, mock_tmux, tmp_path
    ):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="CRITICAL", pct=10, on_battery=True, remaining="15 min")
        mock_mem.return_value = MemoryInfo(status="OK", used_pct=50, pressure="normal")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_board.assert_called()
        board_msg = mock_board.call_args_list[0][0][2]
        assert "电池严重不足" in board_msg

    @patch("lib.concerns.health.tmux_send")
    @patch("lib.concerns.health.is_claude_running", return_value=True)
    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_low_battery_alerts(
        self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, mock_running, mock_tmux, tmp_path
    ):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="LOW", pct=25, on_battery=True, remaining="30 min")
        mock_mem.return_value = MemoryInfo(status="OK", used_pct=50, pressure="normal")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_board.assert_called()
        board_msg = mock_board.call_args_list[0][0][2]
        assert "电池低" in board_msg

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_critical_memory_alerts(self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="AC", pct=100, on_battery=False, remaining="")
        mock_mem.return_value = MemoryInfo(status="CRITICAL", used_pct=95, pressure="critical")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_board.assert_called()
        msg = mock_board.call_args_list[0][0][2]
        assert "内存压力严重" in msg

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_warning_memory_alerts(self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="AC", pct=100, on_battery=False, remaining="")
        mock_mem.return_value = MemoryInfo(status="WARNING", used_pct=85, pressure="warn")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_board.assert_called()
        msg = mock_board.call_args_list[0][0][2]
        assert "内存压力升高" in msg

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=[])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_no_alert_when_all_ok(self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="AC", pct=100, on_battery=False, remaining="")
        mock_mem.return_value = MemoryInfo(status="OK", used_pct=50, pressure="normal")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_board.assert_not_called()

    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=[])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_no_repeat_alert_for_same_state(self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="LOW", pct=25, on_battery=True, remaining="30 min")
        mock_mem.return_value = MemoryInfo(status="OK", used_pct=50, pressure="normal")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_board.reset_mock()

        rm.tick(1060)
        mock_board.assert_not_called()

    @patch("lib.concerns.health.tmux_send")
    @patch("lib.concerns.health.is_claude_running", return_value=True)
    @patch("lib.concerns.health.board_send")
    @patch("lib.concerns.health.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.health.check_cpu")
    @patch("lib.concerns.health.check_memory")
    @patch("lib.concerns.health.check_battery")
    def test_critical_battery_notifies_sessions(
        self, mock_batt, mock_mem, mock_cpu, mock_devs, mock_board, mock_running, mock_tmux, tmp_path
    ):
        cfg = make_cfg(tmp_path)
        rm = ResourceMonitor(cfg)

        mock_batt.return_value = BatteryInfo(status="CRITICAL", pct=8, on_battery=True, remaining="10 min")
        mock_mem.return_value = MemoryInfo(status="OK", used_pct=50, pressure="normal")
        mock_cpu.return_value = CPUInfo(status="OK", usage=30)

        rm.tick(1000)
        mock_tmux.assert_called()
        msg = mock_tmux.call_args[0][1]
        assert "电池严重不足" in msg
