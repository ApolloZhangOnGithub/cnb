"""Tests for bin/secret-scan — pre-commit hook to block sensitive files."""

import importlib.util
import types
from pathlib import Path
from unittest.mock import patch

import pytest

_script = Path(__file__).parent.parent / "bin" / "secret-scan"
_spec = importlib.util.spec_from_loader("secret_scan", loader=None, origin=str(_script))
secret_scan = types.ModuleType("secret_scan")
secret_scan.__file__ = str(_script)
exec(compile(_script.read_text(), _script, "exec"), secret_scan.__dict__)


class TestSensitiveFilenames:
    @pytest.mark.parametrize(
        "filename",
        [
            "server.pem",
            "id_rsa",
            "id_ed25519",
            ".env",
            ".env.production",
            "credentials.json",
            "npm_recovery_codes.txt",
            ".npmrc",
            "token.json",
            "my.secret",
            "app.key",
            "keystore.p12",
        ],
    )
    def test_detects_sensitive_filenames(self, filename):
        assert secret_scan._scan_filename(filename) is not None

    @pytest.mark.parametrize(
        "filename",
        [
            "main.py",
            "lib/board_db.py",
            "README.md",
            "pyproject.toml",
            "schema.sql",
            "tests/test_board.py",
        ],
    )
    def test_allows_safe_filenames(self, filename):
        assert secret_scan._scan_filename(filename) is None


class TestSensitiveContent:
    def test_detects_private_key(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----\n")
        findings = secret_scan._scan_content(str(f))
        assert len(findings) >= 1
        assert findings[0][1] == "private key"

    def test_detects_api_key(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('api_key = "sk-abc123def456ghi789jkl012mno345pqr"\n')
        findings = secret_scan._scan_content(str(f))
        assert any("API key" in label or "secret" in label for _, label in findings)

    def test_detects_aws_key(self, tmp_path):
        f = tmp_path / "aws.txt"
        f.write_text("aws_access_key_id = AKIAIOSFODNN7EXAMPLE\n")
        findings = secret_scan._scan_content(str(f))
        assert any("AWS" in label for _, label in findings)

    def test_detects_github_token(self, tmp_path):
        f = tmp_path / "gh.txt"
        f.write_text("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij\n")
        findings = secret_scan._scan_content(str(f))
        assert any("GitHub" in label for _, label in findings)

    def test_detects_slack_token(self, tmp_path):
        f = tmp_path / "slack.txt"
        f.write_text("xoxb-123456789-abcdefghij\n")
        findings = secret_scan._scan_content(str(f))
        assert any("Slack" in label for _, label in findings)

    def test_clean_file_no_findings(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("def hello():\n    print('hello world')\n")
        findings = secret_scan._scan_content(str(f))
        assert len(findings) == 0


class TestSkipLogic:
    def test_skips_binary_extensions(self):
        assert secret_scan._should_skip("image.png") is True
        assert secret_scan._should_skip("data.db") is True
        assert secret_scan._should_skip("archive.zip") is True

    def test_skips_test_files(self):
        assert secret_scan._should_skip("tests/test_crypto.py") is True

    def test_skips_pubkeys(self):
        assert secret_scan._should_skip("registry/pubkeys.json") is True

    def test_does_not_skip_normal_files(self):
        assert secret_scan._should_skip("lib/board_db.py") is False
        assert secret_scan._should_skip("bin/board") is False


class TestMain:
    @patch.object(secret_scan, "_get_staged_files", return_value=[])
    def test_no_files_returns_zero(self, _mock):
        assert secret_scan.main() == 0

    @patch.object(secret_scan, "_get_staged_files", return_value=["clean.py"])
    @patch.object(secret_scan, "_scan_filename", return_value=None)
    @patch.object(secret_scan, "_scan_content", return_value=[])
    def test_clean_files_returns_zero(self, _c, _f, _s):
        assert secret_scan.main() == 0

    @patch.object(secret_scan, "_get_staged_files", return_value=["server.pem"])
    def test_sensitive_filename_returns_one(self, _mock, capsys):
        result = secret_scan.main()
        assert result == 1
        out = capsys.readouterr().out
        assert "BLOCKED" in out
        assert "server.pem" in out
