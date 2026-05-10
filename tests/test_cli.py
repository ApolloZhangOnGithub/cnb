"""Tests for lib.cli entrypoint resolution."""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestCliMain:
    def test_finds_checkout_bin_cnb(self):
        with patch("os.execvp") as mock_exec:
            mock_exec.side_effect = SystemExit(0)
            from lib.cli import main

            with pytest.raises(SystemExit):
                main()

            args = mock_exec.call_args[0]
            assert args[0] == "bash"
            assert args[1][0] == "bash"
            assert args[1][1].endswith("bin/cnb")

    def test_fatal_when_nothing_found(self, tmp_path):
        import lib.cli as cli_mod

        orig_file = cli_mod.__file__
        try:
            cli_mod.__file__ = str(tmp_path / "lib" / "cli.py")
            with (
                patch.object(Path, "exists", return_value=False),
                patch("shutil.which", return_value=None),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli_mod.main()
            assert exc_info.value.code == 1
        finally:
            cli_mod.__file__ = orig_file

    def test_path_fallback(self, tmp_path):
        import lib.cli as cli_mod

        orig_file = cli_mod.__file__
        try:
            cli_mod.__file__ = str(tmp_path / "lib" / "cli.py")
            with (
                patch.object(Path, "exists", return_value=False),
                patch("shutil.which", return_value="/usr/local/bin/cnb"),
                patch("os.execvp") as mock_exec,
            ):
                mock_exec.side_effect = SystemExit(0)
                with pytest.raises(SystemExit):
                    cli_mod.main()
                assert mock_exec.call_args[0][0] == "/usr/local/bin/cnb"
        finally:
            cli_mod.__file__ = orig_file
