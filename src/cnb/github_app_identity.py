#!/usr/bin/env python3
"""GitHub App identity helpers guarded by an installation allowlist."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from lib.github_app_guard import (
    GitHubAppGuardError,
    check_installation,
    default_allowlist_path,
    default_installation_path,
    load_json,
    normalize_repository,
)

DEFAULT_API_URL = "https://api.github.com"


class GitHubAppIdentityError(RuntimeError):
    """Raised when GitHub App identity setup or API access fails."""


def app_dir(app_slug: str) -> Path:
    return Path.home() / ".github-apps" / app_slug


def build_app_jwt(app_id: int, private_key_pem: bytes, *, now: int | None = None) -> str:
    now = now or int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iat": now - 60,
        "exp": now + 9 * 60,
        "iss": str(app_id),
    }
    signing_input = b".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode()),
            _b64url(json.dumps(payload, separators=(",", ":")).encode()),
        ]
    )
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise GitHubAppIdentityError("GitHub App private key must be an RSA private key")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return b".".join([signing_input, _b64url(signature)]).decode()


def load_app_jwt(app_slug: str) -> str:
    directory = app_dir(app_slug)
    app = load_json(directory / "app.json")
    app_id = app.get("id")
    if app_id is None:
        raise GitHubAppIdentityError(f"missing app id in {directory / 'app.json'}")
    private_key_path = directory / "private-key.pem"
    try:
        private_key = private_key_path.read_bytes()
    except FileNotFoundError:
        raise GitHubAppIdentityError(f"missing private key: {private_key_path}") from None
    return build_app_jwt(int(app_id), private_key)


def fetch_installation(app_slug: str, installation_id: int) -> dict[str, Any]:
    jwt = load_app_jwt(app_slug)
    return _github_json("GET", f"/app/installations/{installation_id}", jwt)


def list_installations(app_slug: str) -> list[dict[str, Any]]:
    jwt = load_app_jwt(app_slug)
    result = _github_request_json("GET", "/app/installations?per_page=100", jwt)
    if not isinstance(result, list):
        raise GitHubAppIdentityError("GitHub API GET /app/installations returned non-list JSON")
    return [item for item in result if isinstance(item, dict)]


def create_repo_scoped_token(
    app_slug: str,
    installation_id: int,
    repository: str,
    *,
    allowlist_path: Path | None = None,
) -> dict[str, Any]:
    repository = _normalize_repo(repository)
    allowlist_path = allowlist_path or default_allowlist_path(app_slug)
    policy = load_json(allowlist_path)
    installation = fetch_installation(app_slug, installation_id)

    decision = check_installation(policy, installation, repository)
    if not decision.allowed:
        raise GitHubAppGuardError(decision.reason)

    jwt = load_app_jwt(app_slug)
    repo_name = repository.split("/", 1)[1]
    token = _github_json(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        jwt,
        body={"repositories": [repo_name]},
    )
    return {
        "installation_id": installation_id,
        "repository": repository,
        "expires_at": token.get("expires_at"),
        "permissions": token.get("permissions", {}),
        "token": token.get("token"),
    }


def resolve_repository_installation_id(
    app_slug: str,
    repository: str,
    *,
    allowlist_path: Path | None = None,
) -> int | None:
    """Return the pinned allowlist installation for a repository, if unique."""
    policy = load_json(allowlist_path or default_allowlist_path(app_slug))
    repository_key = normalize_repository(repository)
    matches: set[int] = set()
    unpinned = False

    for rule in policy.get("allowed_installations", []):
        if not isinstance(rule, dict):
            continue
        repositories = rule.get("repositories", [])
        if repository_key not in {normalize_repository(repo) for repo in repositories}:
            continue
        value = rule.get("installation_id")
        if value is None or value == "":
            unpinned = True
            continue
        matches.add(int(value))

    if len(matches) == 1:
        return next(iter(matches))
    if len(matches) > 1:
        ids = ", ".join(str(item) for item in sorted(matches))
        raise GitHubAppIdentityError(f"multiple pinned installations for {repository}: {ids}")
    if unpinned:
        raise GitHubAppIdentityError(f"allowlist rule for {repository} is unpinned; pass --installation-id")
    return None


def _github_json(method: str, path: str, bearer_token: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = _github_request_json(method, path, bearer_token, body=body)
    if not isinstance(parsed, dict):
        raise GitHubAppIdentityError(f"GitHub API {method} {path} returned non-object JSON")
    return parsed


def _github_request_json(
    method: str,
    path: str,
    bearer_token: str,
    *,
    body: dict[str, Any] | None = None,
) -> Any:
    api_url = os.environ.get("GITHUB_API_URL", DEFAULT_API_URL).rstrip("/")
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {bearer_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cnb-github-app-identity",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{api_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        raise GitHubAppIdentityError(f"GitHub API {method} {path} failed: {exc.code} {error_body}") from exc
    except urllib.error.URLError as exc:
        raise GitHubAppIdentityError(f"GitHub API {method} {path} failed: {exc}") from exc
    if not payload:
        return {}
    return json.loads(payload)


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _normalize_repo(repository: str) -> str:
    repo = repository.strip()
    if repo.count("/") != 1:
        raise GitHubAppIdentityError(f"repository must be owner/name, got {repository!r}")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise GitHubAppIdentityError(f"repository must be owner/name, got {repository!r}")
    return f"{owner}/{name}"


def _resolve_installation_id(
    app_slug: str,
    installation_id: int | None,
    *,
    repository: str | None = None,
    allowlist_path: Path | None = None,
) -> int:
    if installation_id is not None:
        return installation_id
    if repository:
        resolved = resolve_repository_installation_id(app_slug, repository, allowlist_path=allowlist_path)
        if resolved is not None:
            return resolved
    installation = load_json(default_installation_path(app_slug))
    value = installation.get("id")
    if value is None:
        raise GitHubAppIdentityError(f"missing installation id in {default_installation_path(app_slug)}")
    return int(value)


def _redact_token(result: dict[str, Any], *, print_token: bool) -> dict[str, Any]:
    if print_token:
        return result
    redacted = dict(result)
    if redacted.get("token"):
        redacted["token"] = "<redacted>"
    return redacted


def _cmd_token(args: argparse.Namespace) -> int:
    installation_id = _resolve_installation_id(
        args.app,
        args.installation_id,
        repository=args.repository,
        allowlist_path=args.allowlist,
    )
    result = create_repo_scoped_token(
        args.app,
        installation_id,
        args.repository,
        allowlist_path=args.allowlist,
    )
    print(json.dumps(_redact_token(result, print_token=args.print_token), indent=2, sort_keys=True))
    return 0


def _cmd_installation(args: argparse.Namespace) -> int:
    installation_id = _resolve_installation_id(args.app, args.installation_id)
    installation = fetch_installation(args.app, installation_id)
    summary = {
        "account": installation.get("account", {}).get("login")
        if isinstance(installation.get("account"), dict)
        else installation.get("account"),
        "id": installation.get("id"),
        "repository_selection": installation.get("repository_selection"),
        "target_type": installation.get("target_type"),
        "updated_at": installation.get("updated_at"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _cmd_installations(args: argparse.Namespace) -> int:
    installations = list_installations(args.app)
    summaries = []
    for installation in installations:
        account = installation.get("account")
        summaries.append(
            {
                "account": account.get("login") if isinstance(account, dict) else account,
                "id": installation.get("id"),
                "repository_selection": installation.get("repository_selection"),
                "target_type": installation.get("target_type"),
                "updated_at": installation.get("updated_at"),
            }
        )
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use a GitHub App only after allowlist checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    installation_parser = subparsers.add_parser("installation", help="fetch installation metadata")
    installation_parser.add_argument("--app", required=True, help="GitHub App slug under ~/.github-apps")
    installation_parser.add_argument("--installation-id", type=int, help="GitHub App installation id")
    installation_parser.set_defaults(func=_cmd_installation)

    installations_parser = subparsers.add_parser("installations", help="list installations for this GitHub App")
    installations_parser.add_argument("--app", required=True, help="GitHub App slug under ~/.github-apps")
    installations_parser.set_defaults(func=_cmd_installations)

    token_parser = subparsers.add_parser("token", help="mint a repo-scoped installation token after guard checks")
    token_parser.add_argument("--app", required=True, help="GitHub App slug under ~/.github-apps")
    token_parser.add_argument("--installation-id", type=int, help="GitHub App installation id")
    token_parser.add_argument("--repository", required=True, help="repository full name, for example owner/repo")
    token_parser.add_argument("--allowlist", type=Path, help="path to allowlist.json")
    token_parser.add_argument("--print-token", action="store_true", help="print the raw installation token")
    token_parser.set_defaults(func=_cmd_token)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        func = cast(Callable[[argparse.Namespace], int], args.func)
        return func(args)
    except (GitHubAppGuardError, GitHubAppIdentityError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "time": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
