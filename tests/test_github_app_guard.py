from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lib.github_app_guard import (
    GitHubAppGuardError,
    GuardDecision,
    check_installation,
    default_allowlist_path,
    default_installation_path,
    load_json,
    main,
    normalize_repository,
    validate_policy,
)


def _policy() -> dict:
    return {
        "schema_version": 1,
        "app_slug": "cnb-workspace-musk",
        "default_action": "deny",
        "allowed_installations": [
            {
                "account": "cnb-workspace",
                "installation_id": 130989940,
                "repositories": ["cnb-workspace/cnb"],
                "purpose": "management sandbox",
            },
            {
                "account": "ApolloZhangOnGithub",
                "installation_id": None,
                "repositories": ["ApolloZhangOnGithub/cnb"],
                "expires_at": "2026-05-17",
                "purpose": "pending canonical cnb install",
            },
        ],
    }


def test_accepts_pinned_installation_for_exact_repository():
    decision = check_installation(
        _policy(),
        {"id": 130989940, "account": "cnb-workspace"},
        "cnb-workspace/cnb",
        now=datetime(2026, 5, 10, tzinfo=UTC),
    )

    assert decision.allowed is True
    assert decision.rule_index == 0


def test_rejects_unlisted_repository_for_same_installation():
    decision = check_installation(
        _policy(),
        {"id": 130989940, "account": "cnb-workspace"},
        "cnb-workspace/other",
        now=datetime(2026, 5, 10, tzinfo=UTC),
    )

    assert decision.allowed is False
    assert decision.reason == "denied by default"


def test_accepts_pending_install_for_exact_account_and_repository_before_expiry():
    decision = check_installation(
        _policy(),
        {"id": 999, "account": {"login": "ApolloZhangOnGithub"}},
        "ApolloZhangOnGithub/cnb",
        now=datetime(2026, 5, 10, tzinfo=UTC),
    )

    assert decision.allowed is True
    assert "pin installation_id" in decision.reason


def test_rejects_pending_install_after_expiry():
    decision = check_installation(
        _policy(),
        {"id": 999, "account": {"login": "ApolloZhangOnGithub"}},
        "ApolloZhangOnGithub/cnb",
        now=datetime(2026, 5, 18, tzinfo=UTC),
    )

    assert decision.allowed is False
    assert "expired matching rule" in decision.reason


def test_rejects_unknown_account_even_if_repository_name_matches():
    decision = check_installation(
        _policy(),
        {"id": 999, "account": {"login": "attacker"}},
        "ApolloZhangOnGithub/cnb",
        now=datetime(2026, 5, 10, tzinfo=UTC),
    )

    assert decision.allowed is False


def test_policy_requires_default_deny():
    policy = _policy()
    policy["default_action"] = "allow"

    with pytest.raises(GitHubAppGuardError, match="default_action=deny"):
        validate_policy(policy)


def test_policy_rejects_repository_wildcards():
    policy = _policy()
    policy["allowed_installations"][0]["repositories"] = ["cnb-workspace/*"]

    with pytest.raises(GitHubAppGuardError, match="wildcards"):
        validate_policy(policy)


def test_policy_requires_expiry_for_unpinned_installation():
    policy = _policy()
    del policy["allowed_installations"][1]["expires_at"]

    with pytest.raises(GitHubAppGuardError, match="unpinned"):
        validate_policy(policy)


# ---------------------------------------------------------------------------
# Extended coverage: paths, json loading, validators, CLI dispatch
# ---------------------------------------------------------------------------


class TestGuardDecisionDict:
    def test_as_dict_returns_all_fields(self):
        decision = GuardDecision(True, "ok", "acme", 42, "acme/repo", rule_index=1)
        payload = decision.as_dict()
        assert payload == {
            "allowed": True,
            "reason": "ok",
            "account": "acme",
            "installation_id": 42,
            "repository": "acme/repo",
            "rule_index": 1,
        }


class TestDefaultPaths:
    def test_default_allowlist_path_under_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert default_allowlist_path("cnb") == tmp_path / ".github-apps" / "cnb" / "allowlist.json"

    def test_default_installation_path_under_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert default_installation_path("cnb") == tmp_path / ".github-apps" / "cnb" / "installation.json"


class TestLoadJson:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(GitHubAppGuardError, match="file not found"):
            load_json(tmp_path / "missing.json")

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        with pytest.raises(GitHubAppGuardError, match="invalid JSON"):
            load_json(p)

    def test_non_object_json_raises(self, tmp_path):
        p = tmp_path / "list.json"
        p.write_text("[1, 2]")
        with pytest.raises(GitHubAppGuardError, match="expected JSON object"):
            load_json(p)

    def test_object_loads(self, tmp_path):
        p = tmp_path / "ok.json"
        p.write_text(json.dumps({"a": 1}))
        assert load_json(p) == {"a": 1}


class TestValidatePolicyErrors:
    def test_rules_not_a_list(self):
        with pytest.raises(GitHubAppGuardError, match="must be a list"):
            validate_policy({"default_action": "deny", "allowed_installations": "nope"})

    def test_rule_not_an_object(self):
        with pytest.raises(GitHubAppGuardError, match="rule 0 must be an object"):
            validate_policy({"default_action": "deny", "allowed_installations": ["bad"]})

    def test_rule_missing_account_and_id(self):
        with pytest.raises(GitHubAppGuardError, match="needs account or installation_id"):
            validate_policy(
                {
                    "default_action": "deny",
                    "allowed_installations": [{"repositories": ["a/b"]}],
                }
            )

    def test_rule_missing_repositories(self):
        with pytest.raises(GitHubAppGuardError, match="explicit repositories"):
            validate_policy(
                {
                    "default_action": "deny",
                    "allowed_installations": [{"account": "a", "installation_id": 1}],
                }
            )


class TestNormalizeRepository:
    def test_lowercases_owner_and_name(self):
        assert normalize_repository("Acme/Repo") == "acme/repo"

    def test_rejects_missing_slash(self):
        with pytest.raises(GitHubAppGuardError, match="owner/name"):
            normalize_repository("acmerepo")

    def test_rejects_empty_segment(self):
        with pytest.raises(GitHubAppGuardError, match="owner/name"):
            normalize_repository("/repo")


class TestInstallationAccount:
    """_installation_account is indirectly tested via check_installation."""

    def test_string_account_form_is_accepted(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [{"account": "Acme", "installation_id": 7, "repositories": ["acme/repo"]}],
        }
        decision = check_installation(policy, {"id": 7, "account": "Acme"}, "acme/repo")
        assert decision.allowed is True
        assert decision.account == "Acme"


class TestOptionalIntCoercion:
    """check_installation forwards installation id through _optional_int."""

    def test_string_id_rejected_as_invalid(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [{"account": "a", "installation_id": 1, "repositories": ["a/b"]}],
        }
        with pytest.raises(GitHubAppGuardError, match="expected integer"):
            check_installation(policy, {"id": "not-an-int", "account": "a"}, "a/b")


class TestParseExpiresAt:
    def test_blank_expiry_rejected(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [{"account": "a", "repositories": ["a/b"], "expires_at": "  "}],
        }
        with pytest.raises(GitHubAppGuardError, match="expires_at cannot be blank"):
            validate_policy(policy)

    def test_invalid_date_rejected(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [{"account": "a", "repositories": ["a/b"], "expires_at": "2026-13-40"}],
        }
        with pytest.raises(GitHubAppGuardError, match="invalid expires_at"):
            validate_policy(policy)

    def test_iso_timestamp_with_z_accepted(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [
                {
                    "account": "a",
                    "repositories": ["a/b"],
                    "expires_at": "2026-12-31T23:59:59Z",
                }
            ],
        }
        # Should not raise — the Z form is parsed via the +00:00 swap branch.
        validate_policy(policy)

    def test_iso_timestamp_naive_treated_as_utc(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [
                {
                    "account": "a",
                    "repositories": ["a/b"],
                    "expires_at": "2026-12-31T23:59:59",
                }
            ],
        }
        validate_policy(policy)

    def test_iso_timestamp_invalid_rejected(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [
                {
                    "account": "a",
                    "repositories": ["a/b"],
                    "expires_at": "not-a-timestamp-at-all",
                }
            ],
        }
        with pytest.raises(GitHubAppGuardError, match="invalid expires_at timestamp"):
            validate_policy(policy)


class TestNormalizeLoginNone:
    """_normalize_login is exercised when installation.account is missing/None."""

    def test_account_none_does_not_match_rule(self):
        policy = {
            "default_action": "deny",
            "allowed_installations": [{"account": "a", "installation_id": 1, "repositories": ["a/b"]}],
        }
        # installation without an account field at all
        decision = check_installation(policy, {"id": 1}, "a/b")
        assert decision.allowed is False


def _write_policy(tmp_path: Path) -> Path:
    p = tmp_path / "allowlist.json"
    p.write_text(
        json.dumps(
            {
                "default_action": "deny",
                "allowed_installations": [{"account": "acme", "installation_id": 1, "repositories": ["acme/repo"]}],
            }
        )
    )
    return p


def _write_installation(tmp_path: Path, *, account: str = "acme", inst_id: int = 1) -> Path:
    p = tmp_path / "installation.json"
    p.write_text(json.dumps({"id": inst_id, "account": account}))
    return p


class TestCliValidate:
    def test_validate_explicit_allowlist(self, tmp_path, capsys):
        p = _write_policy(tmp_path)
        rc = main(["validate", "--allowlist", str(p)])
        assert rc == 0
        assert json.loads(capsys.readouterr().out) == {"valid": True}

    def test_validate_requires_app_or_allowlist(self, capsys):
        rc = main(["validate"])
        assert rc == 1
        body = json.loads(capsys.readouterr().out)
        assert body["allowed"] is False
        assert "--allowlist" in body["error"]

    def test_validate_resolves_app_to_default_path(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        target = default_allowlist_path("demo")
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "default_action": "deny",
                    "allowed_installations": [{"account": "a", "installation_id": 1, "repositories": ["a/b"]}],
                }
            )
        )
        rc = main(["validate", "--app", "demo"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out) == {"valid": True}


class TestCliCheck:
    def test_check_allowed_returns_zero(self, tmp_path, capsys):
        p = _write_policy(tmp_path)
        i = _write_installation(tmp_path)
        rc = main(["check", "--allowlist", str(p), "--installation", str(i), "--repository", "acme/repo"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["allowed"] is True

    def test_check_denied_returns_two(self, tmp_path, capsys):
        p = _write_policy(tmp_path)
        i = _write_installation(tmp_path, account="other", inst_id=2)
        rc = main(["check", "--allowlist", str(p), "--installation", str(i), "--repository", "acme/repo"])
        assert rc == 2
        assert json.loads(capsys.readouterr().out)["allowed"] is False

    def test_check_requires_installation_path(self, tmp_path, capsys):
        p = _write_policy(tmp_path)
        rc = main(["check", "--allowlist", str(p), "--repository", "acme/repo"])
        assert rc == 1
        body = json.loads(capsys.readouterr().out)
        assert "--installation" in body["error"]

    def test_check_resolves_app_to_default_installation_path(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        allow = default_allowlist_path("demo")
        inst = default_installation_path("demo")
        allow.parent.mkdir(parents=True)
        allow.write_text(
            json.dumps(
                {
                    "default_action": "deny",
                    "allowed_installations": [{"account": "acme", "installation_id": 9, "repositories": ["acme/repo"]}],
                }
            )
        )
        inst.write_text(json.dumps({"id": 9, "account": "acme"}))
        rc = main(["check", "--app", "demo", "--repository", "acme/repo"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["allowed"] is True
