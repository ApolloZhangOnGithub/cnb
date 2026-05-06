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

## Commit messages

- Concise, focus on the WHY
- Sign off with `Co-Authored-By: Claude <YourName> <noreply@anthropic.com>` if you're an agent

## Review

- Team members can review and approve each other's PRs
- Focus on correctness and simplicity, not style
