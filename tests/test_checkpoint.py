"""Tests for checkpoint dirty-worktree guard."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from lib.checkpoint import build_checkpoint, checkpoint_to_json, shutdown_warning_lines

ROOT = Path(__file__).parent.parent


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _write(repo / ".gitignore", "\n".join([".cnb/", ".pytest_cache/", ".venv/"]) + "\n")
    _write(repo / "tracked.py", "print('ok')\n")
    _git(repo, "add", ".gitignore", "tracked.py")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init")


def test_checkpoint_buckets_code_generated_local_and_secret_work(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path / "tracked.py", "print('changed')\n")
    _write(tmp_path / "docs" / "plan.md", "ship it\n")
    _write(tmp_path / ".cnb" / "board.db", "runtime")
    _write(tmp_path / ".pytest_cache" / "node", "cache")
    _write(tmp_path / ".env", "TOKEN=prod-token-123456789\n")

    report = build_checkpoint(tmp_path)

    assert {item.path for item in report.code_changes} == {"tracked.py", "docs/plan.md"}
    assert report.local_state == [".cnb/board.db"]
    assert report.generated_artifacts == [".pytest_cache/node"]
    assert [risk.path for risk in report.secret_risks] == [".env"]
    assert report.has_important_work is True
    assert "GitHub-only planning" in report.recommendations[-1]


def test_checkpoint_staged_mode_fails_for_staged_secret(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path / ".env.production", "TOKEN=prod-token-123456789\n")
    _git(tmp_path, "add", ".env.production")

    result = subprocess.run(
        [str(ROOT / "bin" / "checkpoint"), "--staged"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=30,
    )

    assert result.returncode == 1
    assert "secret risks: 1" in result.stdout
    assert ".env.production" in result.stdout


def test_checkpoint_json_reports_machine_readable_buckets(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path / "docs" / "plan.md", "ship it\n")

    report = build_checkpoint(tmp_path)
    parsed = json.loads(checkpoint_to_json(report))

    assert parsed["git_available"] is True
    assert parsed["code_changes"][0]["path"] == "docs/plan.md"
    assert "recommendations" in parsed


def test_checkpoint_strict_fails_for_important_work(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path / "tracked.py", "print('changed')\n")

    result = subprocess.run(
        [str(ROOT / "bin" / "checkpoint"), "--strict"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=30,
    )

    assert result.returncode == 1
    assert "code/doc changes: 1" in result.stdout


def test_shutdown_warning_mentions_checkpoint_for_important_changes(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path / "tracked.py", "print('changed')\n")

    lines = shutdown_warning_lines(build_checkpoint(tmp_path))

    assert any("uncommitted important work" in line for line in lines)
    assert lines[-1] == "  Run: cnb checkpoint"
