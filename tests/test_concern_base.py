"""Tests for lib/concerns/base.py — Concern base class."""

import pytest

from lib.concerns.base import Concern


class TestConcernDefaults:
    def test_default_interval(self):
        c = Concern()
        assert c.interval == 5

    def test_initial_last_tick_is_zero(self):
        c = Concern()
        assert c.last_tick == 0

    def test_tick_raises_not_implemented(self):
        c = Concern()
        with pytest.raises(NotImplementedError):
            c.tick(1000)


class TestShouldTick:
    def test_true_when_enough_time_elapsed(self):
        c = Concern()
        c.last_tick = 100
        assert c.should_tick(105) is True

    def test_false_when_too_soon(self):
        c = Concern()
        c.last_tick = 100
        assert c.should_tick(103) is False

    def test_true_at_exact_interval(self):
        c = Concern()
        c.last_tick = 100
        assert c.should_tick(105) is True

    def test_true_when_never_ticked(self):
        c = Concern()
        assert c.should_tick(5) is True

    def test_false_at_time_zero(self):
        c = Concern()
        assert c.should_tick(0) is False

    def test_custom_interval(self):
        class FastConcern(Concern):
            interval = 1

            def tick(self, now):
                pass

        c = FastConcern()
        c.last_tick = 100
        assert c.should_tick(100) is False
        assert c.should_tick(101) is True

    def test_large_interval(self):
        class SlowConcern(Concern):
            interval = 300

            def tick(self, now):
                pass

        c = SlowConcern()
        c.last_tick = 1000
        assert c.should_tick(1200) is False
        assert c.should_tick(1300) is True


class TestMaybeTick:
    def test_calls_tick_when_due(self):
        called_with = []

        class TrackingConcern(Concern):
            interval = 5

            def tick(self, now):
                called_with.append(now)

        c = TrackingConcern()
        c.maybe_tick(10)
        assert called_with == [10]

    def test_skips_tick_when_not_due(self):
        called_with = []

        class TrackingConcern(Concern):
            interval = 5

            def tick(self, now):
                called_with.append(now)

        c = TrackingConcern()
        c.last_tick = 8
        c.maybe_tick(10)
        assert called_with == []

    def test_updates_last_tick_on_call(self):
        class SimpleConcern(Concern):
            interval = 5

            def tick(self, now):
                pass

        c = SimpleConcern()
        c.maybe_tick(10)
        assert c.last_tick == 10

    def test_does_not_update_last_tick_when_skipped(self):
        class SimpleConcern(Concern):
            interval = 5

            def tick(self, now):
                pass

        c = SimpleConcern()
        c.last_tick = 8
        c.maybe_tick(10)
        assert c.last_tick == 8

    def test_repeated_calls(self):
        ticks = []

        class TrackingConcern(Concern):
            interval = 5

            def tick(self, now):
                ticks.append(now)

        c = TrackingConcern()
        for t in range(0, 25):
            c.maybe_tick(t)

        assert ticks == [5, 10, 15, 20]

    def test_tick_exception_does_not_update_last_tick(self):
        class FailingConcern(Concern):
            interval = 5

            def tick(self, now):
                raise RuntimeError("boom")

        c = FailingConcern()
        with pytest.raises(RuntimeError):
            c.maybe_tick(10)
        assert c.last_tick == 0


class TestSubclassing:
    def test_subclass_overrides_interval(self):
        class Custom(Concern):
            interval = 42

            def tick(self, now):
                pass

        c = Custom()
        assert c.interval == 42
        assert c.last_tick == 0

    def test_subclass_inherits_should_tick(self):
        class Custom(Concern):
            interval = 10

            def tick(self, now):
                pass

        c = Custom()
        c.last_tick = 90
        assert c.should_tick(99) is False
        assert c.should_tick(100) is True
