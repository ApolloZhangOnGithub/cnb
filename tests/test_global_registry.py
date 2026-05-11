"""Tests for lib/global_registry.py — global project registry and shared credentials.

Covers: register_project, list_projects, remove_project,
update_credential, check_credential, cleanup.
All tests use tmp_path to avoid touching the real ~/.cnb/.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.global_registry import (
    VALID_CREDENTIAL_STATUSES,
    _read_credentials,
    _read_projects,
    check_credential,
    cleanup,
    cmd_projects_scan,
    discover_projects,
    list_projects,
    register_discovered_projects,
    register_project,
    remove_project,
    update_credential,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry_file(tmp_path):
    """Return a path for projects.json inside tmp_path."""
    return tmp_path / "projects.json"


@pytest.fixture
def credentials_file(tmp_path):
    """Return a path for credentials.json inside tmp_path."""
    p = tmp_path / "shared" / "credentials.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# register_project
# ---------------------------------------------------------------------------


class TestRegisterProject:
    def test_register_new_project(self, registry_file, tmp_path):
        proj = tmp_path / "myproject"
        proj.mkdir()
        register_project(proj, "myproject", registry_path=registry_file)

        projects = list_projects(registry_path=registry_file)
        assert len(projects) == 1
        assert projects[0]["name"] == "myproject"
        assert projects[0]["path"] == str(proj.resolve())
        assert "last_active" in projects[0]

    def test_register_updates_existing(self, registry_file, tmp_path):
        proj = tmp_path / "myproject"
        proj.mkdir()
        register_project(proj, "old-name", registry_path=registry_file)
        register_project(proj, "new-name", registry_path=registry_file)

        projects = list_projects(registry_path=registry_file)
        assert len(projects) == 1
        assert projects[0]["name"] == "new-name"

    def test_register_multiple_projects(self, registry_file, tmp_path):
        for i in range(3):
            proj = tmp_path / f"proj{i}"
            proj.mkdir()
            register_project(proj, f"project-{i}", registry_path=registry_file)

        projects = list_projects(registry_path=registry_file)
        assert len(projects) == 3

    def test_register_creates_file(self, tmp_path):
        registry = tmp_path / "new_dir" / "projects.json"
        proj = tmp_path / "proj"
        proj.mkdir()
        register_project(proj, "proj", registry_path=registry)

        assert registry.exists()
        data = json.loads(registry.read_text())
        assert len(data["projects"]) == 1

    def test_ambient_registry_skips_transient_test_projects(self, tmp_path, monkeypatch):
        import lib.global_registry as registry

        cnb_home = tmp_path / ".cnb"
        monkeypatch.setattr(registry, "CNB_HOME", cnb_home)
        monkeypatch.setattr(registry, "PROJECTS_FILE", cnb_home / "projects.json")
        proj = tmp_path / "pytest-of-user" / "pytest-1" / "test_case0" / "proj"
        proj.mkdir(parents=True)

        register_project(proj, "proj")

        assert not registry.PROJECTS_FILE.exists()

        smoke = tmp_path / "cnb-codex-smoke.abc123"
        smoke.mkdir()
        register_project(smoke, "smoke")

        assert not registry.PROJECTS_FILE.exists()

    def test_last_active_is_iso_format(self, registry_file, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        register_project(proj, "proj", registry_path=registry_file)

        projects = list_projects(registry_path=registry_file)
        ts = projects[0]["last_active"]
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# list_projects
# ---------------------------------------------------------------------------


class TestListProjects:
    def test_empty_when_no_file(self, tmp_path):
        projects = list_projects(registry_path=tmp_path / "nonexistent.json")
        assert projects == []

    def test_empty_when_corrupt_json(self, tmp_path):
        f = tmp_path / "projects.json"
        f.write_text("not json{{{")
        projects = list_projects(registry_path=f)
        assert projects == []

    def test_empty_when_wrong_structure(self, tmp_path):
        f = tmp_path / "projects.json"
        f.write_text('"just a string"')
        projects = list_projects(registry_path=f)
        assert projects == []

    def test_returns_all_registered(self, registry_file, tmp_path):
        for i in range(5):
            proj = tmp_path / f"p{i}"
            proj.mkdir()
            register_project(proj, f"p{i}", registry_path=registry_file)

        assert len(list_projects(registry_path=registry_file)) == 5


# ---------------------------------------------------------------------------
# remove_project
# ---------------------------------------------------------------------------


class TestRemoveProject:
    def test_remove_existing(self, registry_file, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        register_project(proj, "proj", registry_path=registry_file)

        result = remove_project(proj, registry_path=registry_file)
        assert result is True
        assert list_projects(registry_path=registry_file) == []

    def test_remove_nonexistent(self, registry_file, tmp_path):
        result = remove_project(tmp_path / "ghost", registry_path=registry_file)
        assert result is False

    def test_remove_only_targeted(self, registry_file, tmp_path):
        p1 = tmp_path / "p1"
        p2 = tmp_path / "p2"
        p1.mkdir()
        p2.mkdir()
        register_project(p1, "p1", registry_path=registry_file)
        register_project(p2, "p2", registry_path=registry_file)

        remove_project(p1, registry_path=registry_file)
        remaining = list_projects(registry_path=registry_file)
        assert len(remaining) == 1
        assert remaining[0]["name"] == "p2"


# ---------------------------------------------------------------------------
# update_credential / check_credential
# ---------------------------------------------------------------------------


class TestCredentials:
    def test_update_and_check(self, credentials_file):
        update_credential("npm", "valid", updated_by="/my/project", credentials_path=credentials_file)

        result = check_credential("npm", credentials_path=credentials_file)
        assert result is not None
        assert result["status"] == "valid"
        assert result["updated_by"] == "/my/project"
        assert "updated" in result

    def test_check_unknown_credential(self, credentials_file):
        result = check_credential("nonexistent", credentials_path=credentials_file)
        assert result is None

    def test_update_overwrites(self, credentials_file):
        update_credential("lark", "valid", credentials_path=credentials_file)
        update_credential("lark", "expired", credentials_path=credentials_file)

        result = check_credential("lark", credentials_path=credentials_file)
        assert result is not None
        assert result["status"] == "expired"

    def test_multiple_credentials(self, credentials_file):
        update_credential("npm", "valid", credentials_path=credentials_file)
        update_credential("lark", "expired", credentials_path=credentials_file)
        update_credential("docker", "unknown", credentials_path=credentials_file)

        r = check_credential("npm", credentials_path=credentials_file)
        assert r is not None
        assert r["status"] == "valid"
        r = check_credential("lark", credentials_path=credentials_file)
        assert r is not None
        assert r["status"] == "expired"
        r = check_credential("docker", credentials_path=credentials_file)
        assert r is not None
        assert r["status"] == "unknown"

    def test_invalid_status_rejected(self, credentials_file):
        with pytest.raises(SystemExit):
            update_credential("npm", "bogus", credentials_path=credentials_file)

    def test_valid_statuses(self):
        assert "valid" in VALID_CREDENTIAL_STATUSES
        assert "expired" in VALID_CREDENTIAL_STATUSES
        assert "unknown" in VALID_CREDENTIAL_STATUSES

    def test_check_corrupt_file(self, tmp_path):
        f = tmp_path / "creds.json"
        f.write_text("{{broken")
        result = check_credential("npm", credentials_path=f)
        assert result is None

    def test_updated_by_optional(self, credentials_file):
        update_credential("npm", "valid", credentials_path=credentials_file)
        result = check_credential("npm", credentials_path=credentials_file)
        assert result is not None
        assert result["updated_by"] == ""


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_removes_stale_projects(self, registry_file, tmp_path):
        existing = tmp_path / "exists"
        existing.mkdir()
        register_project(existing, "exists", registry_path=registry_file)

        # Register a project whose path doesn't exist
        data = json.loads(registry_file.read_text())
        data["projects"].append(
            {
                "path": str(tmp_path / "gone"),
                "name": "gone",
                "last_active": "2026-01-01T00:00:00Z",
            }
        )
        registry_file.write_text(json.dumps(data))

        removed = cleanup(registry_path=registry_file)
        assert len(removed) == 1
        assert str(tmp_path / "gone") in removed[0]

        remaining = list_projects(registry_path=registry_file)
        assert len(remaining) == 1
        assert remaining[0]["name"] == "exists"

    def test_cleanup_no_stale(self, registry_file, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        register_project(proj, "proj", registry_path=registry_file)

        removed = cleanup(registry_path=registry_file)
        assert removed == []
        assert len(list_projects(registry_path=registry_file)) == 1

    def test_cleanup_empty_registry(self, tmp_path):
        removed = cleanup(registry_path=tmp_path / "empty.json")
        assert removed == []

    def test_cleanup_all_stale(self, registry_file, tmp_path):
        data = {
            "projects": [
                {"path": str(tmp_path / "gone1"), "name": "g1", "last_active": "2026-01-01T00:00:00Z"},
                {"path": str(tmp_path / "gone2"), "name": "g2", "last_active": "2026-01-01T00:00:00Z"},
            ]
        }
        registry_file.write_text(json.dumps(data))

        removed = cleanup(registry_path=registry_file)
        assert len(removed) == 2
        assert list_projects(registry_path=registry_file) == []


# ---------------------------------------------------------------------------
# discover_projects
# ---------------------------------------------------------------------------


class TestDiscoverProjects:
    def test_discovers_cnb_project_under_bounded_root(self, tmp_path):
        proj = tmp_path / "workspace" / "app"
        cnb_dir = proj / ".cnb"
        cnb_dir.mkdir(parents=True)
        (cnb_dir / "board.db").touch()
        (cnb_dir / "config.toml").write_text('prefix = "cc-test"\nsessions = ["alice"]\n')

        projects = discover_projects(roots=[tmp_path], max_depth=3)

        assert len(projects) == 1
        assert projects[0]["name"] == "app"
        assert projects[0]["path"] == str(proj.resolve())
        assert projects[0]["config_dir"] == ".cnb"
        assert projects[0]["prefix"] == "cc-test"
        assert projects[0]["configured_sessions"] == ["alice"]

    def test_discovers_legacy_claudes_project(self, tmp_path):
        proj = tmp_path / "legacy"
        legacy_dir = proj / ".claudes"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "board.db").touch()

        projects = discover_projects(roots=[tmp_path], max_depth=2)

        assert len(projects) == 1
        assert projects[0]["config_dir"] == ".claudes"

    def test_prefers_cnb_over_legacy_for_same_project(self, tmp_path):
        proj = tmp_path / "both"
        (proj / ".cnb").mkdir(parents=True)
        (proj / ".claudes").mkdir(parents=True)
        (proj / ".cnb" / "board.db").touch()
        (proj / ".claudes" / "board.db").touch()

        projects = discover_projects(roots=[tmp_path], max_depth=2)

        assert len(projects) == 1
        assert projects[0]["config_dir"] == ".cnb"

    def test_respects_max_depth(self, tmp_path):
        proj = tmp_path / "a" / "b" / "c"
        cnb_dir = proj / ".cnb"
        cnb_dir.mkdir(parents=True)
        (cnb_dir / "board.db").touch()

        assert discover_projects(roots=[tmp_path], max_depth=1) == []
        assert len(discover_projects(roots=[tmp_path], max_depth=3)) == 1

    def test_default_board_mode_ignores_marker_without_board(self, tmp_path):
        proj = tmp_path / "marker-only"
        (proj / ".cnb").mkdir(parents=True)

        assert discover_projects(roots=[tmp_path], max_depth=1) == []

    def test_marker_mode_includes_marker_without_board(self, tmp_path):
        proj = tmp_path / "marker-only"
        (proj / ".cnb").mkdir(parents=True)

        projects = discover_projects(roots=[tmp_path], max_depth=1, mode="marker")

        assert len(projects) == 1
        assert projects[0]["path"] == str(proj.resolve())
        assert projects[0]["config_dir"] == ".cnb"
        assert projects[0]["has_board"] is False
        assert projects[0]["discovery"] == "marker"
        assert projects[0]["board_db"] == ""

    def test_register_skips_marker_only_projects(self, registry_file, tmp_path):
        board_proj = tmp_path / "board"
        marker_proj = tmp_path / "marker"
        (board_proj / ".cnb").mkdir(parents=True)
        (marker_proj / ".cnb").mkdir(parents=True)
        (board_proj / ".cnb" / "board.db").touch()

        projects = discover_projects(roots=[tmp_path], max_depth=1, mode="marker")
        count = register_discovered_projects(projects, registry_path=registry_file)

        assert count == 1
        registered = list_projects(registry_path=registry_file)
        assert registered[0]["name"] == "board"
        assert registered[0]["path"] == str(board_proj.resolve())

    def test_registers_discovered_projects(self, registry_file, tmp_path):
        proj = tmp_path / "app"
        cnb_dir = proj / ".cnb"
        cnb_dir.mkdir(parents=True)
        (cnb_dir / "board.db").touch()
        projects = discover_projects(roots=[tmp_path], max_depth=1)

        count = register_discovered_projects(projects, registry_path=registry_file)

        assert count == 1
        registered = list_projects(registry_path=registry_file)
        assert registered[0]["name"] == "app"
        assert registered[0]["path"] == str(proj.resolve())


# ---------------------------------------------------------------------------
# cmd_projects_scan CLI contract
# ---------------------------------------------------------------------------


class TestCmdProjectsScan:
    def test_json_output_reports_board_project_without_registering(self, tmp_path, capsys, monkeypatch):
        import lib.global_registry as registry

        monkeypatch.setattr(registry.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no tmux/git")))
        registry_path = tmp_path / "home" / ".cnb" / "projects.json"
        monkeypatch.setattr(registry, "CNB_HOME", registry_path.parent)
        monkeypatch.setattr(registry, "PROJECTS_FILE", registry_path)
        monkeypatch.setattr(registry, "_looks_like_transient_project", lambda _path: False)

        proj = tmp_path / "workspace" / "app"
        cnb_dir = proj / ".cnb"
        cnb_dir.mkdir(parents=True)
        (cnb_dir / "board.db").touch()
        (cnb_dir / "config.toml").write_text('prefix = "cc-app"\nsessions = ["alice"]\n')

        cmd_projects_scan(["--root", str(tmp_path), "--max-depth", "3", "--json"])
        payload = json.loads(capsys.readouterr().out)

        assert [p["name"] for p in payload["projects"]] == ["app"]
        project = payload["projects"][0]
        assert project["config_dir"] == ".cnb"
        assert project["configured_sessions"] == ["alice"]
        assert project["git"]["root"] == ""
        assert not registry_path.exists()

    def test_register_in_marker_mode_skips_marker_only_projects(self, tmp_path, capsys, monkeypatch):
        import lib.global_registry as registry

        monkeypatch.setattr(registry.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no tmux/git")))
        registry_path = tmp_path / "home" / ".cnb" / "projects.json"
        monkeypatch.setattr(registry, "CNB_HOME", registry_path.parent)
        monkeypatch.setattr(registry, "PROJECTS_FILE", registry_path)
        monkeypatch.setattr(registry, "_looks_like_transient_project", lambda _path: False)

        board_proj = tmp_path / "board"
        marker_proj = tmp_path / "marker"
        (board_proj / ".cnb").mkdir(parents=True)
        (marker_proj / ".cnb").mkdir(parents=True)
        (board_proj / ".cnb" / "board.db").touch()

        cmd_projects_scan(["--root", str(tmp_path), "--max-depth", "1", "--mode", "marker", "--register"])
        out = capsys.readouterr().out

        assert "OK 已注册/更新 1 个 board-backed 项目" in out
        registered = json.loads(registry_path.read_text())["projects"]
        assert len(registered) == 1
        assert registered[0]["name"] == "board"
        assert registered[0]["path"] == str(board_proj.resolve())

    def test_no_legacy_ignores_claudes_marker(self, tmp_path, capsys, monkeypatch):
        import lib.global_registry as registry

        monkeypatch.setattr(registry.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no tmux/git")))
        legacy_proj = tmp_path / "legacy"
        legacy_dir = legacy_proj / ".claudes"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "board.db").touch()

        cmd_projects_scan(["--root", str(tmp_path), "--max-depth", "1", "--no-legacy", "--json"])
        payload = json.loads(capsys.readouterr().out)

        assert payload["projects"] == []

    def test_tmux_and_git_timeout_degrade_cleanly(self, tmp_path, capsys, monkeypatch):
        import lib.global_registry as registry

        def fake_run(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="external", timeout=3)

        monkeypatch.setattr(registry.subprocess, "run", fake_run)
        proj = tmp_path / "app"
        cnb_dir = proj / ".cnb"
        cnb_dir.mkdir(parents=True)
        (cnb_dir / "board.db").touch()

        cmd_projects_scan(["--root", str(tmp_path), "--max-depth", "1"])
        out = capsys.readouterr().out

        assert "发现 1 个 cnb 项目" in out
        assert "app" in out

    def test_bin_cnb_projects_scan_dispatches_json_contract(self, tmp_path):
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        for name in ("git", "tmux"):
            tool = fake_bin / name
            tool.write_text("#!/usr/bin/env bash\nexit 1\n")
            tool.chmod(0o755)

        root = tmp_path / "root"
        proj = root / "app"
        cnb_dir = proj / ".cnb"
        cnb_dir.mkdir(parents=True)
        (cnb_dir / "board.db").touch()
        (cnb_dir / "config.toml").write_text('prefix = "cc-app"\nsessions = ["alice"]\n')

        env = {
            **os.environ,
            "HOME": str(tmp_path / "home"),
            "VIRTUAL_ENV": str(tmp_path / "venv"),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        result = subprocess.run(
            [
                "bash",
                str(Path(__file__).parent.parent / "bin" / "cnb"),
                "projects",
                "scan",
                "--root",
                str(root),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert [project["name"] for project in payload["projects"]] == ["app"]
        assert payload["projects"][0]["configured_sessions"] == ["alice"]

    def test_bin_cnb_projects_scan_registers_board_projects_without_home_pollution(self, tmp_path):
        workspace = Path(tempfile.mkdtemp(prefix="cnb-projects-cli-"))
        try:
            fake_bin = workspace / "fake-bin"
            fake_bin.mkdir()
            for name in ("git", "tmux"):
                tool = fake_bin / name
                tool.write_text("#!/usr/bin/env bash\nexit 1\n")
                tool.chmod(0o755)

            root = workspace / "root"
            board_proj = root / "board-app"
            marker_proj = root / "marker-app"
            legacy_proj = root / "legacy-app"
            (board_proj / ".cnb").mkdir(parents=True)
            (marker_proj / ".cnb").mkdir(parents=True)
            (legacy_proj / ".claudes").mkdir(parents=True)
            (board_proj / ".cnb" / "board.db").touch()
            (legacy_proj / ".claudes" / "board.db").touch()
            (board_proj / ".cnb" / "config.toml").write_text('prefix = "cc-board"\nsessions = ["alice"]\n')

            home = tmp_path / "isolated-home"
            env = {
                **os.environ,
                "HOME": str(home),
                "VIRTUAL_ENV": str(tmp_path / "venv"),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            result = subprocess.run(
                [
                    "bash",
                    str(Path(__file__).parent.parent / "bin" / "cnb"),
                    "projects",
                    "scan",
                    "--root",
                    str(root),
                    "--max-depth",
                    "1",
                    "--mode",
                    "marker",
                    "--no-legacy",
                    "--register",
                    "--json",
                ],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            assert [project["name"] for project in payload["projects"]] == ["board-app", "marker-app"]
            marker = next(project for project in payload["projects"] if project["name"] == "marker-app")
            assert marker["has_board"] is False
            assert marker["discovery"] == "marker"

            registry_path = home / ".cnb" / "projects.json"
            registered = json.loads(registry_path.read_text())["projects"]
            assert [project["name"] for project in registered] == ["board-app"]
            assert registered[0]["path"] == str(board_proj.resolve())
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestReadHelpers:
    def test_read_projects_missing_file(self, tmp_path):
        data = _read_projects(tmp_path / "nope.json")
        assert data == {"projects": []}

    def test_read_credentials_missing_file(self, tmp_path):
        data = _read_credentials(tmp_path / "nope.json")
        assert data == {}

    def test_read_projects_invalid_structure(self, tmp_path):
        f = tmp_path / "projects.json"
        f.write_text("[1, 2, 3]")
        data = _read_projects(f)
        assert data == {"projects": []}

    def test_read_credentials_invalid_structure(self, tmp_path):
        f = tmp_path / "creds.json"
        f.write_text("[1, 2, 3]")
        data = _read_credentials(f)
        assert data == {}
