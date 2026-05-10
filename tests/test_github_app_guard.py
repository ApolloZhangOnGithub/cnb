from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lib.github_app_guard import GitHubAppGuardError, check_installation, validate_policy


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
