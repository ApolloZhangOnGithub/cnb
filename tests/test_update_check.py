"""Tests for lib/update_check — stale install detection + owner notification."""

import sys
from types import SimpleNamespace

import pytest

from lib import update_check
from lib.update_check import (
    cache_is_fresh,
    cached_latest_version,
    check_update,
    is_venv,
    normalize_version,
    notify_update_owner,
    read_update_owner,
    version_gt,
)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Redirect all on-disk state into tmp_path."""
    monkeypatch.setattr(update_check, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(update_check, "CACHE_LATEST", tmp_path / "latest-version")
    monkeypatch.setattr(update_check, "CACHE_NOTIFIED", tmp_path / "update-notified")
    return tmp_path


@pytest.fixture
def env(tmp_path):
    install_home = tmp_path / "install"
    claudes_dir = tmp_path / "proj" / ".cnb"
    claudes_dir.mkdir(parents=True)
    install_home.mkdir()
    (install_home / "bin").mkdir()
    (install_home / "bin" / "board").write_text("#!/bin/sh\nexit 0\n")
    (install_home / "bin" / "board").chmod(0o755)
    return SimpleNamespace(
        install_home=install_home,
        claudes_dir=claudes_dir,
        board_db=claudes_dir / "board.db",
    )


class TestNormalizeAndCompare:
    def test_strips_dev_suffix(self):
        assert normalize_version("0.5.67-dev") == (0, 5, 67, 0)

    def test_strips_pep440_dev(self):
        assert normalize_version("0.5.67.dev0") == (0, 5, 67, 0)

    def test_strips_prerelease(self):
        assert normalize_version("1.0.0-rc.1") == (1, 0, 0, 0)

    def test_strips_v_prefix(self):
        assert normalize_version("v1.2.3") == (1, 2, 3, 0)

    def test_pads_short_versions(self):
        assert normalize_version("1") == (1, 0, 0, 0)

    def test_version_gt_newer_wins(self):
        assert version_gt("0.6.0", "0.5.99") is True

    def test_version_gt_equal(self):
        assert version_gt("0.5.67-dev", "0.5.67-dev") is False

    def test_version_gt_dev_local_beats_released(self):
        # Local 0.5.67-dev is newer than published 0.5.44 — no update needed.
        assert version_gt("0.5.44", "0.5.67-dev") is False


class TestVenv:
    def test_detects_virtual_env(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/v")
        assert is_venv() is True

    def test_detects_sys_prefix_divergence(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "prefix", "/a")
        monkeypatch.setattr(sys, "base_prefix", "/b")
        assert is_venv() is True


class TestCache:
    def test_missing_cache_is_not_fresh(self, cache):
        assert cache_is_fresh() is False

    def test_recent_cache_is_fresh(self, cache):
        (cache / "latest-version").write_text("1.0.0")
        assert cache_is_fresh(ttl_seconds=3600) is True

    def test_stale_cache_is_not_fresh(self, cache):
        import os

        f = cache / "latest-version"
        f.write_text("1.0.0")
        old = f.stat().st_mtime - 10_000
        os.utime(f, (old, old))
        assert cache_is_fresh(ttl_seconds=60) is False

    def test_cached_latest_strips_whitespace(self, cache):
        (cache / "latest-version").write_text("  1.2.3\n")
        assert cached_latest_version() == "1.2.3"

    def test_empty_cache_returns_none(self, cache):
        (cache / "latest-version").write_text("")
        assert cached_latest_version() is None


class TestReadUpdateOwner:
    def test_env_var_wins(self, env, monkeypatch):
        monkeypatch.setenv("CNB_UPDATE_OWNER", "ops")
        assert read_update_owner(env) == "ops"

    def test_global_config_top_level(self, env, monkeypatch, tmp_path):
        monkeypatch.delenv("CNB_UPDATE_OWNER", raising=False)
        cache_dir = tmp_path / "fake-home-cnb"
        cache_dir.mkdir()
        (cache_dir / "config.toml").write_text('update_owner = "alice"\n')
        monkeypatch.setattr(update_check, "CACHE_DIR", cache_dir)
        assert read_update_owner(env) == "alice"

    def test_global_config_cnb_table(self, env, monkeypatch, tmp_path):
        monkeypatch.delenv("CNB_UPDATE_OWNER", raising=False)
        cache_dir = tmp_path / "fake-home-cnb"
        cache_dir.mkdir()
        (cache_dir / "config.toml").write_text('[cnb]\nmaintainer = "bob"\n')
        monkeypatch.setattr(update_check, "CACHE_DIR", cache_dir)
        assert read_update_owner(env) == "bob"

    def test_project_config_picks_lead_role(self, env, monkeypatch):
        monkeypatch.delenv("CNB_UPDATE_OWNER", raising=False)
        monkeypatch.setattr(update_check, "CACHE_DIR", env.claudes_dir.parent / "nonexistent")
        (env.claudes_dir / "config.toml").write_text('[session.alice]\nrole = "dev"\n[session.boss]\nrole = "lead"\n')
        assert read_update_owner(env) == "boss"

    def test_project_config_falls_back_to_first_session(self, env, monkeypatch):
        monkeypatch.delenv("CNB_UPDATE_OWNER", raising=False)
        monkeypatch.setattr(update_check, "CACHE_DIR", env.claudes_dir.parent / "nonexistent")
        (env.claudes_dir / "config.toml").write_text('sessions = ["alpha", "beta"]\n')
        assert read_update_owner(env) == "alpha"

    def test_missing_config_returns_none(self, env, monkeypatch):
        monkeypatch.delenv("CNB_UPDATE_OWNER", raising=False)
        monkeypatch.setattr(update_check, "CACHE_DIR", env.claudes_dir.parent / "nonexistent")
        assert read_update_owner(env) is None


class TestNotifyUpdateOwner:
    def test_skips_when_no_owner(self, env, cache, monkeypatch):
        monkeypatch.delenv("CNB_UPDATE_OWNER", raising=False)
        # claudes_dir has no config.toml in this test setup
        assert notify_update_owner(env, "1.0.0", "0.9.0") is False

    def test_skips_when_no_board_db(self, env, cache, monkeypatch):
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        # env.board_db doesn't exist — should skip
        assert env.board_db.is_file() is False
        assert notify_update_owner(env, "1.0.0", "0.9.0") is False

    def test_sends_when_owner_and_db_present(self, env, cache, monkeypatch):
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        assert notify_update_owner(env, "1.0.0", "0.9.0") is True
        assert any("boss" in arg for arg in calls[0])
        # suppression key written
        assert update_check.CACHE_NOTIFIED.read_text() == "boss:0.9.0->1.0.0"

    def test_suppresses_duplicate_for_same_pair(self, env, cache, monkeypatch):
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        update_check.CACHE_NOTIFIED.write_text("boss:0.9.0->1.0.0")
        sent_calls = []

        def fake_run(cmd, **kwargs):
            sent_calls.append(cmd)
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        assert notify_update_owner(env, "1.0.0", "0.9.0") is False
        assert sent_calls == []

    def test_sends_again_for_new_target_version(self, env, cache, monkeypatch):
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        update_check.CACHE_NOTIFIED.write_text("boss:0.9.0->1.0.0")
        sent_calls = []

        def fake_run(cmd, **kwargs):
            sent_calls.append(cmd)
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        assert notify_update_owner(env, "1.0.1", "0.9.0") is True
        assert len(sent_calls) == 1


class TestCheckUpdate:
    def test_short_circuits_in_venv(self, env, cache, monkeypatch):
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/v")
        assert check_update(env, "0.1.0") is False

    def test_no_cache_no_notify(self, env, cache, monkeypatch):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        # patch refresh to a no-op so we don't spawn npm
        monkeypatch.setattr(update_check, "refresh_latest_version_async", lambda: None)
        assert check_update(env, "0.1.0") is False

    def test_current_up_to_date_no_notify(self, env, cache, monkeypatch):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        update_check.CACHE_LATEST.write_text("0.5.44")
        assert check_update(env, "0.5.67-dev") is False

    def test_notifies_when_stale(self, env, cache, monkeypatch):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        update_check.CACHE_LATEST.write_text("9.99.99")

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        assert check_update(env, "0.5.67-dev") is True


class TestRefreshAsync:
    def test_spawns_background_process(self, cache, monkeypatch):
        spawned = []

        class FakePopen:
            def __init__(self, args, **kwargs):
                spawned.append(args)

        monkeypatch.setattr(update_check.subprocess, "Popen", FakePopen)
        update_check.refresh_latest_version_async()
        assert len(spawned) == 1
        assert spawned[0][0] == "sh"
        assert "npm view" in spawned[0][2]

    def test_swallows_os_error(self, cache, monkeypatch):
        def raise_oserror(*a, **kw):
            raise OSError("npm missing")

        monkeypatch.setattr(update_check.subprocess, "Popen", raise_oserror)
        # Should not raise
        update_check.refresh_latest_version_async()


class TestCmdUpdateCheck:
    def test_venv_short_circuit(self, env, cache, monkeypatch, capsys):
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/v")
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, [])
        out = capsys.readouterr().out
        assert "skipped" in out
        assert "venv" in out

    def test_reports_up_to_date(self, env, cache, monkeypatch, capsys):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("0.5.44")
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, [])
        out = capsys.readouterr().out
        assert "up to date" in out
        assert "0.5.67-dev" in out
        assert "0.5.44" in out

    def test_reports_notified_when_stale(self, env, cache, monkeypatch, capsys):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("9.99.99")

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, [])
        out = capsys.readouterr().out
        assert "notified boss" in out
        assert "v0.5.67-dev -> v9.99.99" in out

    def test_force_clears_suppression(self, env, cache, monkeypatch, capsys):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("9.99.99")
        # Pre-existing suppression for the same pair
        update_check.CACHE_NOTIFIED.write_text("boss:0.5.67-dev->9.99.99")

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        # avoid the 2s sleep slowing the test
        monkeypatch.setattr(update_check.time, "sleep", lambda *_: None)
        monkeypatch.setattr(update_check, "refresh_latest_version_async", lambda: None)
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, ["--force"])
        out = capsys.readouterr().out
        # --force cleared CACHE_NOTIFIED, so notify proceeds
        assert "notified boss" in out

    def test_quiet_mode_silent_when_stale(self, env, cache, monkeypatch, capsys):
        """--quiet suppresses all stdout but still notifies the owner."""
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("9.99.99")
        called = []

        def fake_run(cmd, **kwargs):
            called.append(cmd)
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(update_check.subprocess, "run", fake_run)
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, ["--quiet"])
        out = capsys.readouterr().out
        assert out == ""
        # owner still notified
        assert any("boss" in arg for arg in called[0])

    def test_quiet_mode_silent_when_up_to_date(self, env, cache, monkeypatch, capsys):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("0.5.44")
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, ["--quiet"])
        assert capsys.readouterr().out == ""

    def test_terminal_mode_silent_when_up_to_date(self, env, cache, monkeypatch, capsys):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("0.5.44")
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, ["--terminal"])
        assert capsys.readouterr().out == ""

    def test_terminal_mode_prints_yellow_when_stale(self, env, cache, monkeypatch, capsys):
        """--terminal prints the user-facing yellow banner line, no OK summary."""
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(sys, "base_prefix", sys.prefix)
        monkeypatch.setenv("CNB_UPDATE_OWNER", "boss")
        env.board_db.write_text("")
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("9.99.99")
        monkeypatch.setattr(update_check.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, ["--terminal"])
        out = capsys.readouterr().out
        assert "已发布" in out
        assert "9.99.99" in out
        assert "0.5.67-dev" in out
        assert "npm install -g claude-nb" in out
        assert "OK" not in out  # no status summary in --terminal mode

    def test_terminal_mode_silent_in_venv(self, env, cache, monkeypatch, capsys):
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/v")
        (env.install_home / "VERSION").write_text("0.5.67-dev")
        update_check.CACHE_LATEST.write_text("9.99.99")
        db = SimpleNamespace(env=env)
        update_check.cmd_update_check(db, ["--terminal"])
        assert capsys.readouterr().out == ""
