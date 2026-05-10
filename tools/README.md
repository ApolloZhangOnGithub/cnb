# Tool Runbooks

This directory holds operational README files for cnb tools. The root README should explain the product and the short path; detailed usage, flags, side effects, and maintenance notes belong near the relevant tool.

Use this layout when a tool needs more than a one-line mention:

- `bin/README.md` maps executable entrypoints.
- `tools/<tool-name>/README.md` explains how to operate a specific tool or command group.
- The tool README should link to the implementation and tests so future AI sessions can move from usage to code quickly.

Current runbooks:

- [Project discovery](project-discovery/README.md) - machine-level scan for `.cnb/` and legacy `.claudes/` project boards.
- [GitHub App Guard](github-app-guard/README.md) - default-deny allowlist for public GitHub App installations.
