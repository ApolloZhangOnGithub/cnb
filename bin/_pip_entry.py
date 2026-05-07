#!/usr/bin/env python3
"""pip/uv entry point for claudes-code — standalone, zero-dependency.

This script is installed as a console_script entry point and resolves
the real bin/claudes-code bash script relative to itself.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    claudes_home = Path(__file__).resolve().parent.parent
    bash_script = claudes_home / "bin" / "claudes-code"

    if bash_script.exists():
        os.execvp("bash", ["bash", str(bash_script), *sys.argv[1:]])

    print(f"FATAL: {bash_script} not found", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
