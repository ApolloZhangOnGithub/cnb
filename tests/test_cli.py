"""Tests for lib/cli.py — cnb entry point resolution.

Covers: entrypoint found at bin/cnb, npm fallback, PATH fallback, fatal exit.
os.execvp is mocked to prevent actually replacing the process.
"""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestCliMain:
    def test_finds_bin_cnb(self):
        """When bin/cnb exists relative to cli.py, exec bash with it."""
        with patch("os.execvp") as mock_exec:
            mock_exec.side_effect = SystemExit(0)
            from lib.cli import main

            with pytest.raises(SystemExit):
                main()
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "bash"
            assert "cnb" in args[1][1]

    def test_fatal_when_nothing_found(self, tmp_path):
        """When no entrypoint can be found, raise SystemExit(1)."""
        import lib.cli as cli_mod

        orig_file = cli_mod.__file__
        try:
            cli_mod.__file__ = str(tmp_path / "lib" / "cli.py")
            with (
                patch("shutil.which", return_value=None),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli_mod.main()
            assert exc_info.value.code == 1
        finally:
            cli_mod.__file__ = orig_file

    def test_npm_fallback(self, tmp_path):
        """When bin/cnb missing but /opt/homebrew/bin/cnb exists, use npm bin."""
        import lib.cli as cli_mod

        orig_file = cli_mod.__file__
        try:
            cli_mod.__file__ = str(tmp_path / "lib" / "cli.py")

            original_exists = Path.exists

            def fake_exists(self):
                s = str(self)
                if s == "/opt/homebrew/bin/cnb":
                    return True
                if "bin/cnb" in s:
                    return False
                return original_exists(self)

            with (
                patch.object(Path, "exists", fake_exists),
                patch("os.execvp") as mock_exec,
            ):
                mock_exec.side_effect = SystemExit(0)
                with pytest.raises(SystemExit):
                    cli_mod.main()
                mock_exec.assert_called_once()
                assert "/opt/homebrew/bin/cnb" in str(mock_exec.call_args)
        finally:
            cli_mod.__file__ = orig_file

    def test_path_fallback(self, tmp_path):
        """When bin/cnb and npm both missing, fall back to shutil.which."""
        import lib.cli as cli_mod

        orig_file = cli_mod.__file__
        try:
            cli_mod.__file__ = str(tmp_path / "lib" / "cli.py")

            original_exists = Path.exists

            def fake_exists(self):
                if "cnb" in str(self):
                    return False
                return original_exists(self)

            with (
                patch.object(Path, "exists", fake_exists),
                patch("shutil.which", return_value="/usr/local/bin/cnb"),
                patch("os.execvp") as mock_exec,
            ):
                mock_exec.side_effect = SystemExit(0)
                with pytest.raises(SystemExit):
                    cli_mod.main()
                mock_exec.assert_called_once()
                assert "cnb" in str(mock_exec.call_args)
        finally:
            cli_mod.__file__ = orig_file
