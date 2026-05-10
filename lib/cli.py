"""Entry point for `cnb` when installed via pip/uv.

Resolves the bash entry script relative to this file, so it works from
any working directory after a normal source checkout or package install.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _candidate_entrypoints() -> list[Path]:
    claudes_home = Path(__file__).resolve().parent.parent
    return [
        claudes_home / "bin" / "cnb",
        Path("/opt/homebrew/bin/cnb"),
    ]


def main() -> None:
    for entrypoint in _candidate_entrypoints():
        if entrypoint.exists():
            if (
                entrypoint.name == "cnb"
                and entrypoint.parent.name == "bin"
                and entrypoint.parent.parent != Path("/opt/homebrew")
            ):
                os.execvp("bash", ["bash", str(entrypoint), *sys.argv[1:]])
            os.execvp(str(entrypoint), [str(entrypoint), *sys.argv[1:]])

    found = shutil.which("cnb")
    if found and Path(found).resolve() != Path(__file__).resolve():
        os.execvp(found, [found, *sys.argv[1:]])

    searched = ", ".join(str(path) for path in _candidate_entrypoints()) + ", PATH:cnb"
    print(f"FATAL: cnb entrypoint not found. Searched: {searched}", file=sys.stderr)
    raise SystemExit(1)
