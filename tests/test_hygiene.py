"""Tests for bin/hygiene worktree classification."""

import json
import os
import subprocess
import types
from pathlib import Path

_script = Path(__file__).parent.parent / "bin" / "hygiene"
hygiene = types.ModuleType("hygiene")
hygiene.__file__ = str(_script)
exec(compile(_script.read_text(), _script, "exec"), hygiene.__dict__)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_summary_keeps_generated_state_and_untracked_work_separate(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    _write(
        tmp_path / ".gitignore",
        "\n".join(
            [
                ".venv/",
                ".build/",
                ".cnb/",
                ".claude/worktrees/",
                "*.egg-info/",
            ]
        ),
    )
    _write(tmp_path / "tracked.txt", "tracked")
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=tmp_path, check=True)
    (tmp_path / "tracked.txt").unlink()

    _write(tmp_path / ".venv/bin/python", "python")
    _write(tmp_path / ".build/debug/module.o", "object")
    _write(tmp_path / "pkg.egg-info/PKG-INFO", "metadata")
    _write(tmp_path / ".cnb/board.db", "db")
    _write(tmp_path / ".claude/worktrees/agent/bin/board", "board")
    _write(tmp_path / "tools/old.shit/file.txt", "backup")
    _write(tmp_path / "docs/new.md", "real work")

    monkeypatch.chdir(tmp_path)
    summary = hygiene._summary(tmp_path)

    assert summary["generated"]["count"] == 3
    assert summary["local_state"]["count"] == 2
    assert summary["marked_backups"]["sample"] == ["tools/old.shit/file.txt"]
    assert summary["untracked_other"]["sample"] == ["docs/new.md"]
    assert summary["tracked_changes"]["deleted"] == 1
    assert summary["tracked_changes"]["deleted_sample"] == ["tracked.txt"]


def test_cnb_hygiene_subcommand_outputs_json(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    script = Path(__file__).parent.parent / "bin" / "cnb"

    result = subprocess.run(
        ["bash", str(script), "hygiene", "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "VIRTUAL_ENV": str(tmp_path / "venv")},
        timeout=30,
    )

    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert "generated" in parsed
    assert "local_state" in parsed
