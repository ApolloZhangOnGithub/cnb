"""Tests for lib/resources.py — resource monitoring.

Covers: BatteryInfo/MemoryInfo/CPUInfo dataclasses, notify_if_changed
state transitions and dedup, to_json serialization, state file management.
"""

import json
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
    notify_if_changed,
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
