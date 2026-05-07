"""Tests for lib/resources.py — resource monitoring.

Covers: BatteryInfo/MemoryInfo/CPUInfo dataclasses, notify_if_changed
state transitions and dedup, to_json serialization, state file management.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.resources import (
    BATTERY_CRITICAL,
    BATTERY_LOW,
    BatteryInfo,
    CPUInfo,
    MemoryInfo,
    _load_prev_state,
    _run,
    _save_state,
    check_battery,
    check_cpu,
    check_memory,
    get_all,
    main,
    notify_if_changed,
    print_status,
    to_json,
)


@pytest.fixture
def state_file(tmp_path):
    sf = tmp_path / "resource-monitor-state"
    with patch("lib.resources._state_file", return_value=sf):
        yield sf


class TestNotifyIfChanged:
    def _batt(self, status="AC", pct=100):
        return BatteryInfo(status=status, pct=pct, on_battery=status != "AC", remaining="—")

    def _mem(self, status="OK"):
        return MemoryInfo(status=status, used_pct=50, pressure="normal")

    def _cpu(self, status="OK"):
        return CPUInfo(status=status, usage=30)

    def test_no_notification_on_same_state(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        notify_if_changed(self._batt(), self._mem(), self._cpu())
        assert state_file.read_text().strip() == "AC|OK|OK"

    def test_saves_new_state(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        notify_if_changed(self._batt("LOW", 25), self._mem(), self._cpu())
        assert state_file.read_text().strip() == "LOW|OK|OK"

    def test_creates_state_file(self, state_file):
        assert not state_file.exists()
        notify_if_changed(self._batt(), self._mem(), self._cpu())
        assert state_file.exists()

    def test_battery_critical_sends_notification(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        sent = []
        with patch("lib.resources.subprocess") as mock_sub:
            mock_sub.run = lambda *a, **kw: sent.append(a)
            notify_if_changed(self._batt("CRITICAL", 10), self._mem(), self._cpu(), board_cmd="/fake/board")
        assert any("CRITICAL" in str(call) for call in sent)

    def test_battery_low_sends_notification(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        sent = []
        with patch("lib.resources.subprocess") as mock_sub:
            mock_sub.run = lambda *a, **kw: sent.append(a)
            notify_if_changed(self._batt("LOW", 25), self._mem(), self._cpu(), board_cmd="/fake/board")
        assert any("LOW" in str(call) for call in sent)

    def test_switch_to_battery_sends_notification(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        sent = []
        with patch("lib.resources.subprocess") as mock_sub:
            mock_sub.run = lambda *a, **kw: sent.append(a)
            notify_if_changed(self._batt("ON_BATTERY", 80), self._mem(), self._cpu(), board_cmd="/fake/board")
        assert any("battery" in str(call).lower() for call in sent)

    def test_memory_critical_sends_notification(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        sent = []
        with patch("lib.resources.subprocess") as mock_sub:
            mock_sub.run = lambda *a, **kw: sent.append(a)
            notify_if_changed(self._batt(), self._mem("CRITICAL"), self._cpu(), board_cmd="/fake/board")
        assert any("MEMORY" in str(call) for call in sent)

    def test_cpu_saturated_sends_notification(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        sent = []
        with patch("lib.resources.subprocess") as mock_sub:
            mock_sub.run = lambda *a, **kw: sent.append(a)
            notify_if_changed(self._batt(), self._mem(), self._cpu("SATURATED"), board_cmd="/fake/board")
        assert any("CPU" in str(call) for call in sent)

    def test_no_notification_without_board_cmd(self, state_file):
        state_file.write_text("AC|OK|OK\n")
        with patch("lib.resources.subprocess") as mock_sub:
            notify_if_changed(self._batt("LOW", 25), self._mem(), self._cpu())
            mock_sub.run.assert_not_called()

    def test_dedup_same_critical_state(self, state_file):
        state_file.write_text("CRITICAL|OK|OK\n")
        sent = []
        with patch("lib.resources.subprocess") as mock_sub:
            mock_sub.run = lambda *a, **kw: sent.append(a)
            notify_if_changed(self._batt("CRITICAL", 8), self._mem(), self._cpu(), board_cmd="/fake/board")
        assert len(sent) == 0


class TestToJson:
    def test_valid_json(self):
        batt = BatteryInfo(status="AC", pct=85, on_battery=False, remaining="—")
        mem = MemoryInfo(status="OK", used_pct=60, pressure="normal")
        cpu = CPUInfo(status="OK", usage=25)
        result = json.loads(to_json(batt, mem, cpu))
        assert result["battery"]["status"] == "AC"
        assert result["battery"]["pct"] == 85
        assert result["memory"]["used_pct"] == 60
        assert result["cpu"]["usage"] == 25

    def test_all_fields_present(self):
        batt = BatteryInfo(status="LOW", pct=20, on_battery=True, remaining="1:30 remaining")
        mem = MemoryInfo(status="WARNING", used_pct=85, pressure="warn")
        cpu = CPUInfo(status="SATURATED", usage=95)
        result = json.loads(to_json(batt, mem, cpu))
        assert result["battery"]["on_battery"] is True
        assert result["battery"]["remaining"] == "1:30 remaining"
        assert result["memory"]["pressure"] == "warn"
        assert result["cpu"]["status"] == "SATURATED"


class TestThresholds:
    def test_battery_low_threshold(self):
        assert BATTERY_LOW == 30

    def test_battery_critical_threshold(self):
        assert BATTERY_CRITICAL == 15
        assert BATTERY_CRITICAL < BATTERY_LOW


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


class TestRun:
    def test_returns_stdout(self):
        result = _run("echo hello")
        assert result == "hello"

    def test_returns_default_on_failure(self):
        result = _run("false", default="fallback")
        assert result == "fallback"

    def test_returns_default_on_timeout(self):
        with patch("lib.resources.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = _run("sleep 999", default="timed-out")
        assert result == "timed-out"


# ---------------------------------------------------------------------------
# check_battery
# ---------------------------------------------------------------------------


class TestCheckBattery:
    def test_no_pmset_returns_na(self):
        with patch("shutil.which", return_value=None):
            info = check_battery()
        assert info.status == "N/A"
        assert info.pct == 100
        assert info.on_battery is False

    def test_ac_power(self):
        pmset_output = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=123)\t85%; AC attached; not charging"
        with (
            patch("shutil.which", return_value="/usr/bin/pmset"),
            patch("lib.resources._run", return_value=pmset_output),
        ):
            info = check_battery()
        assert info.status == "AC"
        assert info.pct == 85
        assert info.on_battery is False

    def test_battery_power_low(self):
        pmset_output = "Now drawing from 'Battery Power'\n -InternalBattery-0\t25%; discharging; 2:30 remaining"
        with (
            patch("shutil.which", return_value="/usr/bin/pmset"),
            patch("lib.resources._run", return_value=pmset_output),
        ):
            info = check_battery()
        assert info.status == "LOW"
        assert info.pct == 25
        assert info.on_battery is True
        assert "2:30" in info.remaining

    def test_battery_power_critical(self):
        pmset_output = "Now drawing from 'Battery Power'\n -InternalBattery-0\t8%; discharging; 0:15 remaining"
        with (
            patch("shutil.which", return_value="/usr/bin/pmset"),
            patch("lib.resources._run", return_value=pmset_output),
        ):
            info = check_battery()
        assert info.status == "CRITICAL"
        assert info.pct == 8

    def test_battery_power_normal(self):
        pmset_output = "Now drawing from 'Battery Power'\n -InternalBattery-0\t75%; discharging"
        with (
            patch("shutil.which", return_value="/usr/bin/pmset"),
            patch("lib.resources._run", return_value=pmset_output),
        ):
            info = check_battery()
        assert info.status == "ON_BATTERY"
        assert info.pct == 75


# ---------------------------------------------------------------------------
# check_memory
# ---------------------------------------------------------------------------


class TestCheckMemory:
    def test_normal_memory(self):
        vm_stat_output = (
            "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
            "Pages free:                              100000.\n"
            "Pages speculative:                        50000.\n"
            "Pages active:                            200000.\n"
        )

        def fake_run(cmd, default=""):
            if "vm_stat" in cmd:
                return vm_stat_output
            return "17179869184"

        with (
            patch("shutil.which", return_value="/usr/bin/vm_stat"),
            patch("lib.resources._run", side_effect=fake_run),
        ):
            info = check_memory()
        assert info.status == "OK"
        assert info.pressure == "normal"

    def test_critical_pressure(self):
        with (
            patch("shutil.which", return_value="/usr/bin/cmd"),
            patch(
                "lib.resources._run",
                side_effect=lambda cmd, **kw: (
                    "System is in critical memory pressure" if "memory_pressure" in cmd else ""
                ),
            ),
        ):
            info = check_memory()
        assert info.status == "CRITICAL"
        assert info.pressure == "critical"

    def test_warn_pressure(self):
        with (
            patch("shutil.which", return_value="/usr/bin/cmd"),
            patch(
                "lib.resources._run",
                side_effect=lambda cmd, **kw: "System is in warn memory pressure" if "memory_pressure" in cmd else "",
            ),
        ):
            info = check_memory()
        assert info.status == "WARNING"
        assert info.pressure == "warn"


# ---------------------------------------------------------------------------
# check_cpu
# ---------------------------------------------------------------------------


class TestCheckCpu:
    def test_normal_cpu(self):
        top_output = "Processes: 400\nCPU usage: 15.0% user, 5.0% sys, 80.0% idle"
        with patch("shutil.which", return_value="/usr/bin/top"), patch("lib.resources._run", return_value=top_output):
            info = check_cpu()
        assert info.status == "OK"
        assert info.usage == 20

    def test_saturated_cpu(self):
        top_output = "Processes: 400\nCPU usage: 85.0% user, 10.0% sys, 5.0% idle"
        with patch("shutil.which", return_value="/usr/bin/top"), patch("lib.resources._run", return_value=top_output):
            info = check_cpu()
        assert info.status == "SATURATED"
        assert info.usage == 95

    def test_no_top_command(self):
        with patch("shutil.which", return_value=None):
            info = check_cpu()
        assert info.status == "OK"
        assert info.usage == 0


# ---------------------------------------------------------------------------
# _load_prev_state / _save_state
# ---------------------------------------------------------------------------


class TestStateFile:
    def test_load_default_when_missing(self, state_file):
        assert not state_file.exists()
        result = _load_prev_state()
        assert result == "AC|normal|OK"

    def test_load_existing_state(self, state_file):
        state_file.write_text("LOW|OK|OK\n")
        result = _load_prev_state()
        assert result == "LOW|OK|OK"

    def test_save_and_load(self, state_file):
        _save_state("CRITICAL|WARNING|SATURATED")
        assert _load_prev_state() == "CRITICAL|WARNING|SATURATED"


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


class TestGetAll:
    def test_returns_tuple_of_three(self):
        with (
            patch("lib.resources.check_battery", return_value=BatteryInfo("AC", 100, False, "—")),
            patch("lib.resources.check_memory", return_value=MemoryInfo("OK", 50, "normal")),
            patch("lib.resources.check_cpu", return_value=CPUInfo("OK", 10)),
        ):
            result = get_all()
        assert len(result) == 3
        assert isinstance(result[0], BatteryInfo)
        assert isinstance(result[1], MemoryInfo)
        assert isinstance(result[2], CPUInfo)


# ---------------------------------------------------------------------------
# print_status
# ---------------------------------------------------------------------------


class TestPrintStatus:
    def _mock_get_all(self):
        return (
            BatteryInfo("AC", 85, False, "—"),
            MemoryInfo("OK", 50, "normal"),
            CPUInfo("OK", 20),
        )

    def test_status_mode(self, capsys):
        with patch("lib.resources.get_all", return_value=self._mock_get_all()):
            print_status("status")
        out = capsys.readouterr().out
        assert "Resource Monitor" in out
        assert "Battery:" in out
        assert "nominal" in out

    def test_json_mode(self, capsys):
        with patch("lib.resources.get_all", return_value=self._mock_get_all()):
            print_status("json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["battery"]["status"] == "AC"

    def test_shows_battery_warning(self, capsys):
        info = (
            BatteryInfo("LOW", 20, True, "1:00 remaining"),
            MemoryInfo("OK", 50, "normal"),
            CPUInfo("OK", 10),
        )
        with patch("lib.resources.get_all", return_value=info):
            print_status("status")
        out = capsys.readouterr().out
        assert "low" in out.lower()

    def test_shows_critical_battery(self, capsys):
        info = (
            BatteryInfo("CRITICAL", 5, True, "0:10 remaining"),
            MemoryInfo("OK", 50, "normal"),
            CPUInfo("OK", 10),
        )
        with patch("lib.resources.get_all", return_value=info):
            print_status("status")
        out = capsys.readouterr().out
        assert "CRITICAL" in out

    def test_shows_memory_warning(self, capsys):
        info = (
            BatteryInfo("AC", 100, False, "—"),
            MemoryInfo("WARNING", 85, "warn"),
            CPUInfo("OK", 10),
        )
        with patch("lib.resources.get_all", return_value=info):
            print_status("status")
        out = capsys.readouterr().out
        assert "Memory pressure" in out

    def test_shows_cpu_saturated(self, capsys):
        info = (
            BatteryInfo("AC", 100, False, "—"),
            MemoryInfo("OK", 50, "normal"),
            CPUInfo("SATURATED", 95),
        )
        with patch("lib.resources.get_all", return_value=info):
            print_status("status")
        out = capsys.readouterr().out
        assert "CPU saturated" in out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    def test_default_status_mode(self, capsys):
        with (
            patch.object(sys, "argv", ["resources.py"]),
            patch("lib.resources.print_status") as mock_ps,
        ):
            main()
        mock_ps.assert_called_once_with("status")

    def test_json_mode(self, capsys):
        with (
            patch.object(sys, "argv", ["resources.py", "--json"]),
            patch("lib.resources.print_status") as mock_ps,
        ):
            main()
        mock_ps.assert_called_once_with("json")
