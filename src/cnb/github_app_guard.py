#!/usr/bin/env python3
"""Default-deny guard for public GitHub App installations.

This module is intentionally small and local: callers should check an
installation against an explicit allowlist before minting an installation token
or acting on a webhook.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, cast


class GitHubAppGuardError(ValueError):
    """Raised when a GitHub App guard policy is malformed."""


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str
    account: str | None
    installation_id: int | None
    repository: str
    rule_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "account": self.account,
            "installation_id": self.installation_id,
            "repository": self.repository,
            "rule_index": self.rule_index,
        }


def default_allowlist_path(app_slug: str) -> Path:
    return Path.home() / ".github-apps" / app_slug / "allowlist.json"


def default_installation_path(app_slug: str) -> Path:
    return Path.home() / ".github-apps" / app_slug / "installation.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise GitHubAppGuardError(f"file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise GitHubAppGuardError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise GitHubAppGuardError(f"expected JSON object in {path}")
    return data


def validate_policy(policy: dict[str, Any]) -> None:
    default_action = policy.get("default_action", policy.get("default", "deny"))
    if default_action != "deny":
        raise GitHubAppGuardError("allowlist must use default_action=deny")

    rules = policy.get("allowed_installations")
    if not isinstance(rules, list):
        raise GitHubAppGuardError("allowed_installations must be a list")

    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise GitHubAppGuardError(f"rule {index} must be an object")

        has_account = bool(rule.get("account"))
        has_installation_id = rule.get("installation_id") is not None
        if not has_account and not has_installation_id:
            raise GitHubAppGuardError(f"rule {index} needs account or installation_id")

        repositories = rule.get("repositories")
        if not isinstance(repositories, list) or not repositories:
            raise GitHubAppGuardError(f"rule {index} must list explicit repositories")

        for repo in repositories:
            normalized = _normalize_repo(repo)
            if "*" in normalized:
                raise GitHubAppGuardError(f"rule {index} cannot use repository wildcards")

        if not has_installation_id and not rule.get("expires_at"):
            raise GitHubAppGuardError(f"rule {index} is unpinned and must set expires_at")

        if rule.get("expires_at"):
            _parse_expires_at(str(rule["expires_at"]))


def check_installation(
    policy: dict[str, Any],
    installation: dict[str, Any],
    repository: str,
    *,
    now: datetime | None = None,
) -> GuardDecision:
    validate_policy(policy)

    repository = _normalize_repo(repository)
    account = _installation_account(installation)
    installation_id = _optional_int(installation.get("id"))
    now = now or datetime.now(UTC)

    expired_rules: list[int] = []
    for index, rule in enumerate(policy["allowed_installations"]):
        expires_at = rule.get("expires_at")
        if expires_at and _parse_expires_at(str(expires_at)) < now:
            expired_rules.append(index)
            continue

        rule_installation_id = _optional_int(rule.get("installation_id"))
        if rule_installation_id is not None and rule_installation_id != installation_id:
            continue

        rule_account = rule.get("account")
        if rule_account and _normalize_login(str(rule_account)) != _normalize_login(account):
            continue

        allowed_repos = {_normalize_repo(repo) for repo in rule["repositories"]}
        if repository not in allowed_repos:
            continue

        if rule_installation_id is None:
            reason = "allowed by unpinned account/repository rule; pin installation_id after install"
        else:
            reason = "allowed by pinned installation rule"
        return GuardDecision(True, reason, account, installation_id, repository, index)

    reason = "denied by default"
    if expired_rules:
        reason = f"denied by default; expired matching rule indexes: {expired_rules}"
    return GuardDecision(False, reason, account, installation_id, repository)


def _installation_account(installation: dict[str, Any]) -> str | None:
    account = installation.get("account")
    if isinstance(account, dict):
        login = account.get("login")
        return str(login) if login else None
    if isinstance(account, str):
        return account
    return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise GitHubAppGuardError(f"expected integer value, got {value!r}") from None


def _normalize_login(login: str | None) -> str | None:
    if login is None:
        return None
    return login.strip().lower()


def normalize_repository(repository: Any) -> str:
    repo = str(repository).strip()
    if repo.count("/") != 1:
        raise GitHubAppGuardError(f"repository must be owner/name, got {repository!r}")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise GitHubAppGuardError(f"repository must be owner/name, got {repository!r}")
    return f"{owner.lower()}/{name.lower()}"


def _normalize_repo(repository: Any) -> str:
    return normalize_repository(repository)


def _parse_expires_at(value: str) -> datetime:
    value = value.strip()
    if not value:
        raise GitHubAppGuardError("expires_at cannot be blank")
    if len(value) == 10:
        try:
            expires_date = date.fromisoformat(value)
        except ValueError as exc:
            raise GitHubAppGuardError(f"invalid expires_at date: {value}") from exc
        return datetime.combine(expires_date, time.max, tzinfo=UTC)
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise GitHubAppGuardError(f"invalid expires_at timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_allowlist(args: argparse.Namespace) -> Path:
    allowlist = getattr(args, "allowlist", None)
    if isinstance(allowlist, Path):
        return allowlist
    if args.app:
        return default_allowlist_path(args.app)
    raise GitHubAppGuardError("pass --allowlist or --app")


def _resolve_installation(args: argparse.Namespace) -> Path:
    installation = getattr(args, "installation", None)
    if isinstance(installation, Path):
        return installation
    if args.app:
        return default_installation_path(args.app)
    raise GitHubAppGuardError("pass --installation or --app")


def _cmd_validate(args: argparse.Namespace) -> int:
    policy = load_json(_resolve_allowlist(args))
    validate_policy(policy)
    print(json.dumps({"valid": True}, indent=2, sort_keys=True))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    policy = load_json(_resolve_allowlist(args))
    installation = load_json(_resolve_installation(args))
    decision = check_installation(policy, installation, args.repository)
    print(json.dumps(decision.as_dict(), indent=2, sort_keys=True))
    return 0 if decision.allowed else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guard GitHub App public installations with a default-deny allowlist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate an allowlist policy")
    validate_parser.add_argument("--app", help="GitHub App slug under ~/.github-apps")
    validate_parser.add_argument("--allowlist", type=Path, help="path to allowlist.json")
    validate_parser.set_defaults(func=_cmd_validate)

    check_parser = subparsers.add_parser("check", help="check whether an installation may act on a repository")
    check_parser.add_argument("--app", help="GitHub App slug under ~/.github-apps")
    check_parser.add_argument("--allowlist", type=Path, help="path to allowlist.json")
    check_parser.add_argument("--installation", type=Path, help="path to installation.json")
    check_parser.add_argument("--repository", required=True, help="repository full name, for example owner/repo")
    check_parser.set_defaults(func=_cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        func = cast(Callable[[argparse.Namespace], int], args.func)
        return func(args)
    except GitHubAppGuardError as exc:
        print(json.dumps({"allowed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
