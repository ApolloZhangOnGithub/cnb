# Contributing to claudes-code

We welcome contributions from everyone.

## Workflow

1. Fork the repo (or create a branch if you have write access)
2. Make your changes
3. Run `ruff check --fix && ruff format` and `pytest`
4. Open a PR against `master`
5. Get one approving review, then merge

## Code style

- Python 3.11+, `snake_case` variables, `PascalCase` classes
- Line length: 120
- No comments unless the WHY is non-obvious
- User-facing output in Chinese, code/docs in English

## Agent naming convention

All agent contributors follow the **"Claude XXX"** format:

- Display name: `Claude Meridian`, `Claude Forge`, etc.
- Registry ID: lowercase short name (`meridian`, `forge`)
- Commit signature: `Co-Authored-By: Claude Meridian <noreply@anthropic.com>`
- GitHub comment signature: `— Claude Meridian`

Register before your first contribution:

```bash
registry register <name> --role <role> --description "<what you do>"
```

The registry auto-generates your display name as `Claude <Name>`.

## Commit messages

- Concise, focus on the WHY
- Sign off with `Co-Authored-By: Claude <YourName> <noreply@anthropic.com>`

## Review

- Team members can review and approve each other's PRs
- Focus on correctness and simplicity, not style
