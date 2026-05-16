"""Tests for lib/swarm.py and lib/swarm_backend.py.

Covers: SwarmConfig, SwarmManager (registration, prompts, attendance, role filtering),
and backend detection/dispatch.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from lib.common import ClaudesEnv
from lib.swarm import SwarmConfig, SwarmManager, auto_dispatcher_enabled
from lib.swarm_backend import ScreenBackend, SessionBackend, TmuxBackend, detect_backend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEFAULT_SESSIONS = ["alice", "bob", "charlie"]


class FakeBackend(SessionBackend):
    """In-memory backend that records calls without subprocess."""

    def __init__(self):
        self.calls: list[tuple[str, ...]] = []
        self._running: set[str] = set()

    def is_running(self, prefix: str, name: str) -> bool:
        self.calls.append(("is_running", prefix, name))
        return f"{prefix}-{name}" in self._running

    def start_session(self, prefix: str, name: str, project_root: Path, agent_cmd: str) -> str:
        self.calls.append(("start_session", prefix, name, agent_cmd))
        self._running.add(f"{prefix}-{name}")
        return f"{prefix}-{name}"

    def stop_session(self, prefix: str, name: str, save_cmd: str) -> None:
        self.calls.append(("stop_session", prefix, name))
        self._running.discard(f"{prefix}-{name}")

    def status_line(self, prefix: str, name: str, agent: str) -> str:
        return f"running (fake, agent: {agent})"

    def attach(self, prefix: str, name: str) -> None:
        self.calls.append(("attach", prefix, name))

    def inject(self, prefix: str, name: str, message: str) -> None:
        self.calls.append(("inject", prefix, name, message))

    def capture_pane(self, prefix: str, name: str) -> str:
        return ""

    def inject_initial_prompt(self, prefix: str, name: str, prompt: str, log_dir: Path) -> None:
        self.calls.append(("inject_initial_prompt", prefix, name))


@pytest.fixture
def fake_backend():
    return FakeBackend()


@pytest.fixture
def env(tmp_project) -> ClaudesEnv:
    cd = tmp_project / ".claudes"
    return ClaudesEnv(
        claudes_dir=cd,
        project_root=tmp_project,
        install_home=Path(__file__).parent.parent,
        board_db=cd / "board.db",
        sessions_dir=cd / "sessions",
        cv_dir=cd / "cv",
        log_dir=cd / "logs",
        prefix="cc-test",
        sessions=list(DEFAULT_SESSIONS),
        suspended_file=cd / "suspended.list",
        attendance_log=cd / "logs" / "attendance.log",
    )


@pytest.fixture
def mgr(env, fake_backend) -> SwarmManager:
    cfg = SwarmConfig(env=env, agent="claude", backend=fake_backend, install_home=env.install_home)
    return SwarmManager(cfg)


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------


class TestDetectBackend:
    def test_env_override_tmux(self):
        with patch.dict("os.environ", {"SWARM_MODE": "tmux"}):
            b = detect_backend()
        assert isinstance(b, TmuxBackend)

    def test_env_override_screen(self):
        with patch.dict("os.environ", {"SWARM_MODE": "screen"}):
            b = detect_backend()
        assert isinstance(b, ScreenBackend)

    @patch("shutil.which", return_value=None)
    def test_no_multiplexer_exits(self, mock_which):
        os_env = {k: v for k, v in __import__("os").environ.items() if k != "SWARM_MODE"}
        with patch.dict("os.environ", os_env, clear=True), pytest.raises(SystemExit):
            detect_backend()


# ---------------------------------------------------------------------------
# SwarmManager — prompts
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_system_prompt_contains_name(self, mgr):
        p = mgr.build_system_prompt("alice")
        assert "alice" in p
        assert "inbox" in p

    def test_agent_cmd_claude(self, mgr):
        cmd = mgr.build_agent_cmd("alice")
        assert "claude" in cmd
        assert "--name 'alice'" in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_agent_cmd_unknown_exits(self, mgr):
        mgr.cfg.agent = "unknown_agent"
        with pytest.raises(SystemExit):
            mgr.build_agent_cmd("alice")

    def test_agent_cmd_codex_highest_permissions(self, mgr):
        mgr.cfg.agent = "codex"
        cmd = mgr.build_agent_cmd("alice")
        assert cmd.startswith("codex features enable goals")
        assert "; codex " in cmd
        assert "--dangerously-bypass-approvals-and-sandbox" in cmd
        assert "--ask-for-approval" not in cmd
        assert "--sandbox" not in cmd
        assert "--cd" in cmd
        assert "alice" in cmd
        assert "/goal <目标>" in cmd
        assert "--append-system-prompt" not in cmd

    def test_agent_cmd_codex_standby_does_not_resume_historical_work(self, mgr):
        mgr.cfg.agent = "codex"
        cmd = mgr.build_agent_cmd("alice", standby=True)
        assert "standby/smoke" in cmd
        assert "不要继续" in cmd
        assert "不要读取 ROADMAP.md" in cmd
        assert "如果没有明确任务，读 ROADMAP.md 自主找活" not in cmd

    def test_initial_prompt_contains_session_dir(self, mgr):
        p = mgr.build_initial_prompt("bob")
        assert "bob" in p
        assert "inbox" in p


class TestDispatcherAutostart:
    def test_default_enabled(self, monkeypatch):
        monkeypatch.delenv("CNB_AUTO_DISPATCHER", raising=False)

        assert auto_dispatcher_enabled() is True

    def test_can_disable_with_env(self, monkeypatch):
        monkeypatch.setenv("CNB_AUTO_DISPATCHER", "0")

        assert auto_dispatcher_enabled() is False

    def test_start_launches_dispatcher_watchdog(self, mgr, monkeypatch, capsys):
        calls = []

        class FakePopen:
            pid = 4321

            def __init__(self, args, **kwargs):
                calls.append((args, kwargs))

        monkeypatch.delenv("CNB_AUTO_DISPATCHER", raising=False)
        monkeypatch.setattr("lib.swarm.subprocess.Popen", FakePopen)

        mgr.start(["alice"])

        assert calls
        assert calls[0][0][-1].endswith("bin/dispatcher-watchdog")
        assert calls[0][1]["cwd"] == mgr._env.project_root
        assert calls[0][1]["env"]["CNB_PROJECT"] == str(mgr._env.project_root)
        assert (mgr._env.claudes_dir / "dispatcher-watchdog.pid").read_text() == "4321\n"
        assert "Dispatcher watchdog: started" in capsys.readouterr().out

    def test_start_skips_dispatcher_when_disabled(self, mgr, monkeypatch, capsys):
        monkeypatch.setenv("CNB_AUTO_DISPATCHER", "0")
        monkeypatch.setattr(
            "lib.swarm.subprocess.Popen",
            lambda *args, **kwargs: pytest.fail("dispatcher watchdog should not start"),
        )

        mgr.start(["alice"])

        assert not (mgr._env.claudes_dir / "dispatcher-watchdog.pid").exists()
        assert "Dispatcher watchdog" not in capsys.readouterr().out

    def test_initial_prompt_standby_reports_only(self, mgr):
        p = mgr.build_initial_prompt("bob", standby=True)
        assert "standby/smoke" in p
        assert "等待明确任务" in p
        assert "不要改文件" in p
        assert "不要读取 ROADMAP.md" in p
        assert "如果没有明确任务，读 ROADMAP.md 自主找活" not in p


# ---------------------------------------------------------------------------
# SwarmManager — registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_ensure_registered_creates_session_in_db(self, mgr):
        from lib.board_db import BoardDB

        mgr.ensure_registered(["newbie"])
        db = BoardDB(mgr._env.board_db)
        count = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='newbie'")
        assert count == 1

    def test_ensure_registered_creates_md_file(self, mgr):
        mgr.ensure_registered(["newbie"])
        md = mgr._env.sessions_dir / "newbie.md"
        assert md.exists()
        assert "# newbie" in md.read_text()

    def test_ensure_registered_idempotent(self, mgr):
        mgr.ensure_registered(["alice"])
        mgr.ensure_registered(["alice"])
        from lib.board_db import BoardDB

        db = BoardDB(mgr._env.board_db)
        count = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='alice'")
        assert count == 1

    def test_ensure_registered_updates_config_toml(self, mgr):
        mgr.ensure_registered(["newbie"])
        text = (mgr._env.claudes_dir / "config.toml").read_text()
        assert '"newbie"' in text

    def test_ensure_registered_skips_when_no_db(self, mgr):
        mgr._env.board_db.unlink()
        mgr.ensure_registered(["newbie"])


# ---------------------------------------------------------------------------
# SwarmManager — attendance
# ---------------------------------------------------------------------------


class TestAttendance:
    def test_clock_in_writes_log(self, mgr):
        mgr.clock_in("alice")
        log = mgr._env.attendance_log
        assert log.exists()
        assert "alice" in log.read_text()
        assert "clock-in" in log.read_text()

    def test_clock_in_records_engine(self, mgr):
        from lib.board_db import BoardDB

        mgr.cfg.agent = "codex"
        mgr.clock_in("alice")
        assert "engine=codex" in mgr._env.attendance_log.read_text()
        db = BoardDB(mgr._env)
        row = db.query_one(
            "SELECT session, engine, ended_at FROM session_runs WHERE session='alice' ORDER BY id DESC LIMIT 1"
        )
        assert row is not None
        assert row["session"] == "alice"
        assert row["engine"] == "codex"
        assert row["ended_at"] is None

    def test_clock_out_records_run_end(self, mgr):
        from lib.board_db import BoardDB

        mgr.cfg.agent = "codex"
        mgr.clock_in("alice")
        mgr.clock_out("alice")
        db = BoardDB(mgr._env)
        row = db.query_one("SELECT engine, ended_at FROM session_runs WHERE session='alice' ORDER BY id DESC LIMIT 1")
        assert row is not None
        assert row["engine"] == "codex"
        assert row["ended_at"] is not None

    def test_recorded_engine_prefers_run_history(self, mgr):
        mgr.cfg.agent = "codex"
        mgr.clock_in("alice")
        mgr.cfg.agent = "claude"
        assert mgr.recorded_engine("alice") == "codex"

    def test_recorded_engine_falls_back_to_startup_log(self, mgr):
        from lib.board_db import BoardDB

        mgr.cfg.agent = "codex"
        mgr.log_startup("alice")
        mgr.cfg.agent = "claude"
        assert mgr.recorded_engine("alice") == "codex"
        db = BoardDB(mgr._env)
        row = db.query_one("SELECT engine FROM session_runs WHERE session='alice' ORDER BY id DESC LIMIT 1")
        assert row is not None
        assert row["engine"] == "codex"

    def test_clock_out_writes_log(self, mgr):
        mgr.clock_in("alice")
        mgr.clock_out("alice")
        text = mgr._env.attendance_log.read_text()
        assert "clock-in" in text
        assert "clock-out" in text

    def test_attendance_no_records(self, mgr, capsys):
        mgr.attendance()
        assert "No attendance records" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# SwarmManager — start/stop
# ---------------------------------------------------------------------------


class TestStartStop:
    def test_save_cmd_does_not_auto_stage_or_commit(self, mgr):
        cmd = mgr._save_cmd("alice")
        assert "git add" not in cmd
        assert "git commit" not in cmd
        assert "shutdown: stopped without auto-commit" in cmd

    def test_start_dry_run(self, mgr, fake_backend, capsys):
        mgr.start([], dry_run=True)
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert len([c for c in fake_backend.calls if c[0] == "start_session"]) == 0

    def test_start_all_sessions(self, mgr, fake_backend, capsys):
        mgr.start([])
        started = [c for c in fake_backend.calls if c[0] == "start_session"]
        assert len(started) == 3

    def test_start_specific_session(self, mgr, fake_backend, capsys):
        mgr.start(["alice"])
        started = [c for c in fake_backend.calls if c[0] == "start_session"]
        assert len(started) == 1
        assert started[0][2] == "alice"

    def test_start_standby_passes_report_only_prompt(self, mgr, fake_backend, capsys):
        mgr.cfg.agent = "codex"
        mgr.start(["alice"], standby=True)
        started = [c for c in fake_backend.calls if c[0] == "start_session"]
        assert len(started) == 1
        assert "standby/smoke" in started[0][3]
        assert "不要继续" in started[0][3]
        assert "不要读取 ROADMAP.md" in started[0][3]
        out = capsys.readouterr().out
        assert "Startup: standby/smoke" in out

    def test_start_dry_run_standby_mentions_mode(self, mgr, capsys):
        mgr.start(["alice"], dry_run=True, standby=True)
        out = capsys.readouterr().out
        assert "standby/smoke" in out

    def test_start_skips_suspended(self, mgr, fake_backend, capsys):
        sf = mgr._env.suspended_file
        sf.write_text("bob\n")
        mgr.start([])
        started = [c for c in fake_backend.calls if c[0] == "start_session"]
        names = [c[2] for c in started]
        assert "bob" not in names
        assert "alice" in names

    def test_stop_with_force(self, mgr, fake_backend, capsys):
        mgr.start(["alice", "bob"])
        fake_backend.calls.clear()
        mgr.stop([], force=True)
        stopped = [c for c in fake_backend.calls if c[0] == "stop_session"]
        assert len(stopped) == 2

    def test_stop_specific_session(self, mgr, fake_backend, capsys):
        mgr.start(["alice"])
        fake_backend.calls.clear()
        mgr.stop(["alice"])
        stopped = [c for c in fake_backend.calls if c[0] == "stop_session"]
        assert len(stopped) == 1
        assert stopped[0][2] == "alice"

    def test_status_output(self, mgr, fake_backend, capsys):
        mgr.start(["alice"])
        capsys.readouterr()
        mgr.status()
        out = capsys.readouterr().out
        assert "alice" in out
        assert "running" in out
        assert "bob" in out
        assert "stopped" in out

    def test_status_uses_recorded_engine(self, mgr, fake_backend, capsys):
        mgr.cfg.agent = "codex"
        mgr.start(["alice"])
        mgr.cfg.agent = "claude"
        capsys.readouterr()
        mgr.status()
        out = capsys.readouterr().out
        assert "alice: running (fake, agent: codex)" in out


# ---------------------------------------------------------------------------
# SwarmManager — suspend/resume
# ---------------------------------------------------------------------------


class TestSuspendResume:
    def test_suspend_writes_file(self, mgr):
        mgr.suspend(["alice"])
        assert "alice" in mgr._env.suspended_file.read_text()

    def test_suspend_no_args_exits(self, mgr):
        with pytest.raises(SystemExit):
            mgr.suspend([])

    def test_resume_removes_from_file(self, mgr, fake_backend):
        mgr._env.suspended_file.write_text("alice\nbob\n")
        mgr.resume(["alice"])
        text = mgr._env.suspended_file.read_text()
        assert "alice" not in text
        assert "bob" in text

    def test_resume_no_args_exits(self, mgr):
        with pytest.raises(SystemExit):
            mgr.resume([])


# ---------------------------------------------------------------------------
# SwarmManager — role filtering
# ---------------------------------------------------------------------------


class TestRoleFiltering:
    def _write_roles(self, mgr):
        config = mgr._env.claudes_dir / "config.toml"
        config.write_text(
            'claudes_home = "/tmp"\nsessions = ["alice", "bob", "charlie"]\nprefix = "cc-test"\n\n'
            '[session.alice]\npersona = ""\nrole = "lead"\n\n'
            '[session.bob]\npersona = ""\nrole = "intern"\n\n'
            '[session.charlie]\npersona = ""\nrole = "dev"\n'
        )

    def test_get_role_no_config_section(self, mgr):
        assert mgr.get_role("alice") == "unknown"

    def test_get_role_from_config(self, mgr):
        self._write_roles(mgr)
        assert mgr.get_role("alice") == "lead"
        assert mgr.get_role("bob") == "intern"
        assert mgr.get_role("charlie") == "dev"

    def test_filter_sessions_by_role(self, mgr):
        self._write_roles(mgr)
        devs = mgr.filter_sessions(role="dev")
        assert devs == ["charlie"]

    def test_filter_sessions_exclude(self, mgr):
        self._write_roles(mgr)
        non_interns = mgr.filter_sessions(exclude="intern")
        assert "bob" not in non_interns
        assert "alice" in non_interns


# ---------------------------------------------------------------------------
# SwarmManager — help
# ---------------------------------------------------------------------------


class TestHelp:
    def test_help_output(self, mgr, capsys):
        mgr.help()
        out = capsys.readouterr().out
        assert "start" in out
        assert "stop" in out
        assert "status" in out
