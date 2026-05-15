"""Shared secret-scanning helpers for local commit/checkpoint guards."""

from __future__ import annotations

import re
from pathlib import Path

SENSITIVE_FILENAMES = re.compile(
    r"(?i)"
    r"("
    r"\.pem$|\.key$|\.p12$|\.pfx$|\.jks$"
    r"|id_rsa|id_ed25519|id_ecdsa"
    r"|\.env$|\.env\.|\.secret"
    r"|credentials|recovery_code|recovery_key"
    r"|npm_recovery|npmrc$"
    r"|\.htpasswd|shadow$|passwd$"
    r"|token\.json|service.account\.json"
    r"|keystore|truststore"
    r")"
)

SENSITIVE_CONTENT = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-z0-9]{20,}"), "API key"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "OpenAI API key"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GitHub personal access token"),
    (re.compile(r"npm_[a-zA-Z0-9]{36}"), "npm token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"xox[bpors]-[a-zA-Z0-9-]{10,}"), "Slack token"),
]
GENERIC_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:secret|password|passwd|token)\s*[:=]\s*"
    r"(?P<quote>['\"])(?P<value>[A-Za-z0-9_./+=:@-]{12,})(?P=quote)(?=$|[\s,}\]#])"
)

SKIP_EXTENSIONS = frozenset(
    {
        ".pyc",
        ".whl",
        ".gz",
        ".tar",
        ".zip",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".db",
        ".db-shm",
        ".db-wal",
        ".sqlite",
    }
)

SKIP_PATHS = frozenset(
    {
        "registry/pubkeys.json",
        "tests/",
        "lib/crypto.py",
    }
)


def should_skip(filepath: str) -> bool:
    ext = Path(filepath).suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return True
    return any(filepath.startswith(skip) for skip in SKIP_PATHS)


def scan_filename(filepath: str) -> str | None:
    if SENSITIVE_FILENAMES.search(filepath):
        return "sensitive filename pattern"
    return None


def scan_text(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern, label in SENSITIVE_CONTENT:
            if pattern.search(line):
                findings.append((lineno, label))
                break
        else:
            match = GENERIC_SECRET_ASSIGNMENT.search(line)
            if match and looks_like_secret_literal(match.group("value")):
                findings.append((lineno, "secret/password"))
    return findings


def scan_content(filepath: str | Path) -> list[tuple[int, str]]:
    try:
        content = Path(filepath).read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_text(content)


def looks_like_secret_literal(value: str) -> bool:
    """Return True for likely literal secrets, not code identifiers or calls."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return False
    has_alpha = any(ch.isalpha() for ch in value)
    has_digit = any(ch.isdigit() for ch in value)
    has_symbol = any(not ch.isalnum() and ch != "_" for ch in value)
    return len(value) >= 16 and has_alpha and (has_digit or has_symbol)
