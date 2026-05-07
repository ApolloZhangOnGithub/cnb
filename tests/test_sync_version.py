"""Tests for bin/sync-version — version/license consistency checker."""

import importlib.util
import json
import types
from pathlib import Path

import pytest

_script = Path(__file__).parent.parent / "bin" / "sync-version"
_spec = importlib.util.spec_from_loader("sync_version", loader=None, origin=str(_script))
sync_mod = types.ModuleType("sync_version")
sync_mod.__file__ = str(_script)
exec(compile(_script.read_text(), _script, "exec"), sync_mod.__dict__)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Create minimal VERSION, package.json, pyproject.toml in tmp_path."""
    (tmp_path / "VERSION").write_text("1.2.3-dev\n")
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "test", "version": "1.2.3-dev", "license": "OpenAll-1.0"}, indent=2) + "\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\nversion = "1.2.3.dev0"\nlicense = {text = "OpenAll-1.0"}\n'
    )
    monkeypatch.setattr(sync_mod, "ROOT", tmp_path)
    return tmp_path


class TestConversions:
    def test_canonical_to_pep440_dev(self):
        assert sync_mod.canonical_to_pep440("1.2.3-dev") == "1.2.3.dev0"

    def test_canonical_to_pep440_release(self):
        assert sync_mod.canonical_to_pep440("1.2.3") == "1.2.3"

    def test_pep440_to_npm_dev(self):
        assert sync_mod.pep440_to_npm("1.2.3.dev0") == "1.2.3-dev"

    def test_pep440_to_npm_release(self):
        assert sync_mod.pep440_to_npm("1.2.3") == "1.2.3"


class TestCheck:
    def test_all_consistent(self, project):
        assert sync_mod.check() == []

    def test_detects_npm_version_drift(self, project):
        pkg = json.loads((project / "package.json").read_text())
        pkg["version"] = "0.0.1"
        (project / "package.json").write_text(json.dumps(pkg))
        errors = sync_mod.check()
        assert len(errors) >= 1
        assert any("package.json version" in e for e in errors)

    def test_detects_pyproject_version_drift(self, project):
        text = (project / "pyproject.toml").read_text()
        text = text.replace("1.2.3.dev0", "0.0.1")
        (project / "pyproject.toml").write_text(text)
        errors = sync_mod.check()
        assert len(errors) >= 1
        assert any("pyproject.toml version" in e for e in errors)

    def test_detects_license_drift(self, project):
        pkg = json.loads((project / "package.json").read_text())
        pkg["license"] = "MIT"
        (project / "package.json").write_text(json.dumps(pkg))
        errors = sync_mod.check()
        assert len(errors) >= 1
        assert any("license" in e for e in errors)


class TestSync:
    def test_fixes_npm_version(self, project):
        pkg = json.loads((project / "package.json").read_text())
        pkg["version"] = "0.0.1"
        (project / "package.json").write_text(json.dumps(pkg))

        sync_mod.sync()
        pkg_after = json.loads((project / "package.json").read_text())
        assert pkg_after["version"] == "1.2.3-dev"

    def test_fixes_npm_license(self, project):
        pkg = json.loads((project / "package.json").read_text())
        pkg["license"] = "MIT"
        (project / "package.json").write_text(json.dumps(pkg))

        sync_mod.sync()
        pkg_after = json.loads((project / "package.json").read_text())
        assert pkg_after["license"] == "OpenAll-1.0"

    def test_fixes_pyproject_version(self, project):
        text = (project / "pyproject.toml").read_text()
        text = text.replace("1.2.3.dev0", "0.0.1")
        (project / "pyproject.toml").write_text(text)

        sync_mod.sync()
        text_after = (project / "pyproject.toml").read_text()
        assert "1.2.3.dev0" in text_after

    def test_noop_when_consistent(self, project, capsys):
        sync_mod.sync()
        out = capsys.readouterr().out
        assert "already in sync" in out


class TestMainCheckMode:
    def test_exits_1_when_drift(self, project):
        pkg = json.loads((project / "package.json").read_text())
        pkg["version"] = "0.0.1"
        (project / "package.json").write_text(json.dumps(pkg))

        import sys

        old_argv = sys.argv
        sys.argv = ["sync-version", "--check"]
        try:
            with pytest.raises(SystemExit) as exc_info:
                sync_mod.main()
            assert exc_info.value.code == 1
        finally:
            sys.argv = old_argv
