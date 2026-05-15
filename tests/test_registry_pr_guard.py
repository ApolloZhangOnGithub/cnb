import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_guard_module():
    path = Path(__file__).parent.parent / "bin" / "check-registry-pr-guard"
    loader = SourceFileLoader("check_registry_pr_guard", str(path))
    spec = importlib.util.spec_from_loader("check_registry_pr_guard", loader)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_base_ref_uses_master_when_github_base_ref_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    assert _load_guard_module().default_base_ref() == "origin/master"


def test_default_base_ref_uses_master_when_github_base_ref_empty(monkeypatch):
    monkeypatch.setenv("GITHUB_BASE_REF", "")

    assert _load_guard_module().default_base_ref() == "origin/master"


def test_default_base_ref_uses_pull_request_base(monkeypatch):
    monkeypatch.setenv("GITHUB_BASE_REF", "release/v1")

    assert _load_guard_module().default_base_ref() == "origin/release/v1"
