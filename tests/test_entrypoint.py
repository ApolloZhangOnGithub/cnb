"""Tests for bin/cnb entrypoint.

Covers: worker count clamping, theme selection, banner, system prompt,
slash command generation, and board message validation.

Strategy: run the actual bash script with a stubbed `claude` binary,
and run board commands against real SQLite for validation tests.
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

CLAUDES_HOME = Path(__file__).resolve().parent.parent
ENTRYPOINT = CLAUDES_HOME / "bin" / "cnb"
BOARD = CLAUDES_HOME / "bin" / "board"


@pytest.fixture
def fake_project(tmp_path):
    """A temp dir with fake agent binaries that dump their args."""
    fake_claude = tmp_path / "claude"
    fake_claude.write_text(
        "#!/usr/bin/env bash\n"
        "while [[ $# -gt 0 ]]; do\n"
        '  case "$1" in\n'
        '    --append-system-prompt) echo "SYSPROMPT<<EOF"; echo "$2"; echo "EOF"; shift 2 ;;\n'
        '    --name) echo "NAME=$2"; shift 2 ;;\n'
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
    )
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IEXEC)

    fake_codex = tmp_path / "codex"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        'echo CODEX_ARGS="$*"\n'
        "while [[ $# -gt 0 ]]; do\n"
        '  case "$1" in\n'
        '    --cd) echo "CD=$2"; shift 2 ;;\n'
        '    --sandbox) echo "SANDBOX=$2"; shift 2 ;;\n'
        '    --ask-for-approval) echo "APPROVAL=$2"; shift 2 ;;\n'
        '    --dangerously-bypass-approvals-and-sandbox) echo "BYPASS=1"; shift ;;\n'
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
    )
    fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IEXEC)

    stub_swarm = tmp_path / "swarm-stub"
    stub_swarm.write_text("#!/usr/bin/env bash\nexit 0\n")
    stub_swarm.chmod(stub_swarm.stat().st_mode | stat.S_IEXEC)

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project_dir, check=True)

    return project_dir, fake_claude, fake_codex, stub_swarm


def _run(fake_project, args=None, env=None):
    project_dir, fake_claude, fake_codex, stub_swarm = fake_project
    home_dir = project_dir / "home"
    home_dir.mkdir(exist_ok=True)

    script = ENTRYPOINT.read_text()
    script = script.replace(
        'CLAUDES_HOME="$(cd "$(dirname "$0")/.." && pwd)"',
        f'CLAUDES_HOME="{CLAUDES_HOME}"',
    )
    script = script.replace("exec claude", str(fake_claude))
    script = script.replace("exec codex", str(fake_codex))
    script = script.replace('"$CLAUDES_HOME/bin/swarm"', str(stub_swarm))
    script = script.replace("_start_dispatcher\n", "# _start_dispatcher (stubbed)\n")
    script = script.replace("clear\n", "")
    script = script.replace("if [ ! -t 0 ] || [ ! -t 1 ]; then", "if false; then")

    tmp_script = project_dir / "_test.sh"
    tmp_script.write_text(script)
    tmp_script.chmod(tmp_script.stat().st_mode | stat.S_IEXEC)

    cmd = ["bash", str(tmp_script)]
    if args:
        cmd.extend(args)

    run_env = {**os.environ, "TERM": "dumb", "HOME": str(home_dir)}
    run_env.pop("CNB_AGENT", None)
    run_env.pop("SWARM_AGENT", None)
    if env:
        run_env.update(env)

    return subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=30,
        env=run_env,
    )


class TestWorkerClamping:
    def test_zero_clamped_to_one(self, fake_project):
        r = _run(fake_project, ["0"])
        assert r.returncode == 0
        assert "1 位同学" in r.stdout

    def test_overflow_clamped_to_max(self, fake_project):
        r = _run(fake_project, ["99"])
        assert r.returncode == 0
        count = int(re.search(r"(\d+) 位同学", r.stdout).group(1))
        assert count <= 20

    def test_default_is_two(self, fake_project):
        r = _run(fake_project)
        assert r.returncode == 0
        assert "2 位同学" in r.stdout


class TestThemeSelection:
    def test_positional_theme(self, fake_project):
        r = _run(fake_project, ["food"])
        assert r.returncode == 0
        assert "美食" in r.stdout

    def test_number_and_theme(self, fake_project):
        r = _run(fake_project, ["3", "threebody"])
        assert r.returncode == 0
        assert "三体" in r.stdout
        assert "3 位同学" in r.stdout

    def test_theme_before_number(self, fake_project):
        r = _run(fake_project, ["space", "4"])
        assert r.returncode == 0
        assert "太空" in r.stdout
        assert "4 位同学" in r.stdout

    def test_invalid_theme_errors(self, fake_project):
        r = _run(fake_project, ["nonsense"])
        assert r.returncode != 0

    def test_default_theme_is_ai(self, fake_project):
        r = _run(fake_project)
        assert r.returncode == 0
        assert "AI 大佬" in r.stdout


class TestBanner:
    def test_has_product_name(self, fake_project):
        r = _run(fake_project)
        assert "cnb" in r.stdout

    def test_has_theme_in_brackets(self, fake_project):
        r = _run(fake_project)
        assert re.search(r"「.+」", r.stdout)

    def test_has_worker_names(self, fake_project):
        r = _run(fake_project, ["1"])
        match = re.search(r"同学[：:]\s*(\S+)", r.stdout)
        assert match


class TestSystemPrompt:
    def test_has_lead_role(self, fake_project):
        r = _run(fake_project)
        assert "负责和用户沟通" in r.stdout

    def test_lead_name_passed(self, fake_project):
        r = _run(fake_project)
        assert re.search(r"NAME=\S+", r.stdout)

    def test_has_board_commands(self, fake_project):
        r = _run(fake_project)
        assert "send" in r.stdout
        assert "inbox" in r.stdout

    def test_codex_agent_uses_highest_permissions(self, fake_project):
        r = _run(fake_project, ["codex"])
        assert r.returncode == 0
        assert "engine: codex" in r.stdout
        assert "BYPASS=1" in r.stdout
        assert "APPROVAL=" not in r.stdout
        assert "SANDBOX=" not in r.stdout
        assert "CD=" in r.stdout

    def test_codex_agent_from_env(self, fake_project):
        r = _run(fake_project, env={"CNB_AGENT": "codex"})
        assert r.returncode == 0
        assert "engine: codex" in r.stdout
        assert "BYPASS=1" in r.stdout


class TestSlashCommands:
    def test_slash_commands_created(self, fake_project):
        r = _run(fake_project)
        assert r.returncode == 0
        project_dir = fake_project[0]
        cmd_dir = project_dir / ".claude" / "commands"
        assert cmd_dir.is_dir()
        expected = [
            "cnb-watch.md",
            "cnb-overview.md",
            "cnb-progress.md",
            "cnb-history.md",
            "cnb-pending.md",
            "cnb-update.md",
            "cnb-help.md",
        ]
        for f in expected:
            assert (cmd_dir / f).exists(), f"Missing: {f}"

        pending_content = (cmd_dir / "cnb-pending.md").read_text()
        assert "pending list" in pending_content
        assert "pending verify --retry" in pending_content


class TestSubcommands:
    def test_version(self, fake_project):
        project_dir = fake_project[0]
        r = subprocess.run(
            ["bash", str(ENTRYPOINT), "version"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "cnb v" in r.stdout

    def test_unknown_command_errors(self, fake_project):
        project_dir = fake_project[0]
        r = subprocess.run(
            ["bash", str(ENTRYPOINT), "nonsense"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0

    def test_help_shows_themes(self, fake_project):
        project_dir = fake_project[0]
        r = subprocess.run(
            ["bash", str(ENTRYPOINT), "help"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "threebody" in r.stdout

    def test_version_subcommand_notifies_lead_when_outdated(self, board_project, tmp_path):
        home = tmp_path / "home"
        cnb_home = home / ".cnb"
        cnb_home.mkdir(parents=True)
        (cnb_home / "latest-version").write_text("9.9.9\n")

        env = {**os.environ, "CNB_PROJECT": str(board_project), "HOME": str(home)}
        r = subprocess.run(
            ["bash", str(ENTRYPOINT), "version"],
            cwd=board_project,
            capture_output=True,
            text=True,
            env=env,
        )

        assert r.returncode == 0
        assert "cnb v" in r.stdout
        inbox = _board(board_project, "--as", "lead", "inbox")
        assert "cnb v9.9.9 已发布" in inbox.stdout

    def test_version_subcommand_does_not_notify_for_older_latest(self, board_project, tmp_path):
        home = tmp_path / "home"
        cnb_home = home / ".cnb"
        cnb_home.mkdir(parents=True)
        (cnb_home / "latest-version").write_text("0.5.1\n")

        env = {**os.environ, "CNB_PROJECT": str(board_project), "HOME": str(home)}
        r = subprocess.run(
            ["bash", str(ENTRYPOINT), "version"],
            cwd=board_project,
            capture_output=True,
            text=True,
            env=env,
        )

        assert r.returncode == 0
        inbox = _board(board_project, "--as", "lead", "inbox")
        assert "cnb update" not in inbox.stdout
        assert not (cnb_home / "update-notified").exists()

    def test_version_subcommand_skips_update_check_in_virtualenv(self, board_project, tmp_path):
        home = tmp_path / "home"
        cnb_home = home / ".cnb"
        cnb_home.mkdir(parents=True)
        (cnb_home / "latest-version").write_text("9.9.9\n")

        env = {
            **os.environ,
            "CNB_PROJECT": str(board_project),
            "HOME": str(home),
            "VIRTUAL_ENV": str(tmp_path / "venv"),
        }
        r = subprocess.run(
            ["bash", str(ENTRYPOINT), "version"],
            cwd=board_project,
            capture_output=True,
            text=True,
            env=env,
        )

        assert r.returncode == 0
        inbox = _board(board_project, "--as", "lead", "inbox")
        assert "cnb v9.9.9 已发布" not in inbox.stdout
        assert not (cnb_home / "update-notified").exists()


# ── Board message validation (found by AI self-play) ──


@pytest.fixture
def board_project(tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project_dir, check=True)
    subprocess.run(
        [str(CLAUDES_HOME / "bin" / "init"), "lead", "alpha", "bravo"],
        cwd=project_dir,
        capture_output=True,
    )
    return project_dir


def _board(project_dir, *args):
    env = {**os.environ, "CNB_PROJECT": str(project_dir)}
    return subprocess.run(
        [str(BOARD), *args],
        cwd=project_dir,
        capture_output=True,
        text=True,
        env=env,
    )


class TestSendValidation:
    def test_send_to_unknown_recipient_rejected(self, board_project):
        r = _board(board_project, "--as", "lead", "send", "nobody", "hello")
        assert r.returncode == 1
        assert "not a registered session" in r.stdout

    def test_send_empty_message(self, board_project):
        r = _board(board_project, "--as", "lead", "send", "alpha", "")
        assert r.returncode != 0
        assert "不能为空" in r.stdout

    def test_send_valid_message(self, board_project):
        r = _board(board_project, "--as", "lead", "send", "alpha", "hello")
        assert r.returncode == 0
        assert "OK" in r.stdout

    def test_broadcast_works(self, board_project):
        r = _board(board_project, "--as", "lead", "send", "all", "大家好")
        assert r.returncode == 0


class TestInboxValidation:
    def test_unknown_session_rejected(self, board_project):
        r = _board(board_project, "--as", "ghost", "inbox")
        assert r.returncode == 1
        assert "not a registered session" in r.stdout

    def test_registered_session(self, board_project):
        r = _board(board_project, "--as", "alpha", "inbox")
        assert r.returncode == 0

    def test_inbox_shows_messages(self, board_project):
        _board(board_project, "--as", "lead", "send", "alpha", "测试消息")
        r = _board(board_project, "--as", "alpha", "inbox")
        assert "测试消息" in r.stdout
