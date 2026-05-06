"""Entry point for `claudes-code` when installed via pip/uv.

Resolves the bash entry script relative to this file, so it works from
any working directory after a normal (non-editable) pip install.  For
editable installs that ship only the lib/ directory, fall back to
running the bash script through the npm-linked Node.js wrapper.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    claudes_home = Path(__file__).resolve().parent.parent
    entrypoint = claudes_home / "bin" / "claudes-code"

    if entrypoint.exists():
        os.execvp("bash", ["bash", str(entrypoint)] + sys.argv[1:])

    # Fallback for editable installs: try the npm global bin wrapper
    npm_bin = Path("/opt/homebrew/bin/claudes-code")
    if npm_bin.exists():
        os.execvp(str(npm_bin), [str(npm_bin)] + sys.argv[1:])

    # Last resort: search PATH
    import shutil

    found = shutil.which("claudes-code")
    if found and Path(found).resolve() != Path(__file__).resolve():
        os.execvp(found, [found] + sys.argv[1:])

    print(f"FATAL: entrypoint not found at {entrypoint}", file=sys.stderr)
    raise SystemExit(1)
