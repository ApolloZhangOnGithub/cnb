from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from lib.github_app_identity import _redact_token, build_app_jwt, resolve_repository_installation_id


def _decode_segment(segment: str) -> dict:
    padding = "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment + padding))


def test_build_app_jwt_contains_expected_header_and_claims():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    token = build_app_jwt(3660379, pem, now=1_700_000_000)

    header, payload, signature = token.split(".")
    assert signature
    assert _decode_segment(header) == {"alg": "RS256", "typ": "JWT"}
    claims = _decode_segment(payload)
    assert claims["iss"] == "3660379"
    assert claims["iat"] == 1_699_999_940
    assert claims["exp"] == 1_700_000_540


def test_redact_token_hides_raw_token_by_default():
    result = {"token": "ghs_secret", "expires_at": "2026-05-10T00:00:00Z"}

    assert _redact_token(result, print_token=False)["token"] == "<redacted>"
    assert _redact_token(result, print_token=True)["token"] == "ghs_secret"


def test_resolve_repository_installation_id_from_pinned_allowlist(tmp_path):
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "default_action": "deny",
                "allowed_installations": [
                    {
                        "account": "cnb-workspace",
                        "installation_id": 130989940,
                        "repositories": ["cnb-workspace/cnb"],
                    },
                    {
                        "account": "ApolloZhangOnGithub",
                        "installation_id": 130997703,
                        "repositories": ["ApolloZhangOnGithub/cnb"],
                    },
                ],
            }
        )
    )

    assert (
        resolve_repository_installation_id(
            "cnb-workspace-musk",
            "apollozhangongithub/cnb",
            allowlist_path=allowlist,
        )
        == 130997703
    )
