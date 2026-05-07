"""Tests for AdaptiveThrottle concern."""

from unittest.mock import patch

from lib.concerns.adaptive_throttle import AdaptiveThrottle
from lib.concerns.base import Concern
from lib.resources import CPUInfo


class TestAdaptiveThrottle:
    def test_is_concern_subclass(self):
        assert issubclass(AdaptiveThrottle, Concern)

    def test_starts_at_multiplier_1(self):
        t = AdaptiveThrottle()
        assert t.multiplier == 1

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_high_cpu_doubles_multiplier(self, mock_cpu):
        mock_cpu.return_value = CPUInfo(status="SATURATED", usage=90)
        t = AdaptiveThrottle()

        t.tick(100)
        assert t.multiplier == 2

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_sustained_high_cpu_doubles_again(self, mock_cpu):
        mock_cpu.return_value = CPUInfo(status="SATURATED", usage=95)
        t = AdaptiveThrottle()

        t.tick(100)
        assert t.multiplier == 2
        t.tick(110)
        assert t.multiplier == 4

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_multiplier_capped_at_max(self, mock_cpu):
        mock_cpu.return_value = CPUInfo(status="SATURATED", usage=99)
        t = AdaptiveThrottle()

        for i in range(10):
            t.tick(100 + i * 10)

        assert t.multiplier == AdaptiveThrottle.MAX_MULT

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_low_cpu_restores_multiplier(self, mock_cpu):
        t = AdaptiveThrottle()
        t.multiplier = 4

        mock_cpu.return_value = CPUInfo(status="OK", usage=40)
        t.tick(100)
        assert t.multiplier == 1

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_mid_cpu_keeps_multiplier(self, mock_cpu):
        """CPU between LOW and HIGH thresholds: no change."""
        t = AdaptiveThrottle()
        t.multiplier = 2

        mock_cpu.return_value = CPUInfo(status="OK", usage=70)
        t.tick(100)
        assert t.multiplier == 2

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_boundary_at_high_threshold(self, mock_cpu):
        """Exactly at HIGH threshold: no increase (needs > HIGH)."""
        t = AdaptiveThrottle()
        mock_cpu.return_value = CPUInfo(status="OK", usage=AdaptiveThrottle.HIGH)
        t.tick(100)
        assert t.multiplier == 1

    @patch("lib.concerns.adaptive_throttle.check_cpu")
    def test_boundary_at_low_threshold(self, mock_cpu):
        """Exactly at LOW threshold: no restore (needs < LOW)."""
        t = AdaptiveThrottle()
        t.multiplier = 2
        mock_cpu.return_value = CPUInfo(status="OK", usage=AdaptiveThrottle.LOW)
        t.tick(100)
        assert t.multiplier == 2
