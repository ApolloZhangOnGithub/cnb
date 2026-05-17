"""Tests for lib.fmt ANSI formatting helpers."""

from io import StringIO

from lib import fmt


class NonTTY(StringIO):
    def isatty(self):
        return False


class TTY(StringIO):
    def isatty(self):
        return True


def test_non_tty_output_has_no_ansi(monkeypatch):
    monkeypatch.delenv("CNB_FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    assert fmt.ok("OK sent", stream=NonTTY()) == "OK sent"
    assert fmt.error("ERROR: bad", stream=NonTTY()) == "ERROR: bad"


def test_tty_output_uses_ansi(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CNB_FORCE_COLOR", raising=False)

    value = fmt.ok("OK sent", stream=TTY())

    assert value.startswith("\033[32m")
    assert value.endswith(fmt.RESET)
    assert "OK sent" in value


def test_no_color_disables_tty_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("CNB_FORCE_COLOR", raising=False)

    assert fmt.warn("careful", stream=TTY()) == "careful"


def test_force_color_enables_non_tty_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CNB_FORCE_COLOR", "1")

    value = fmt.heading("Title", stream=NonTTY())

    assert value.startswith("\033[1;36m")
    assert value.endswith(fmt.RESET)
