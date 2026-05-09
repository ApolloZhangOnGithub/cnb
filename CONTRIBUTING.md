# Contributing to claude-nb

We welcome contributions from everyone.

## Issue management

cnb treats issues as organizational records, not just a to-do list.

- **Read ROADMAP.md before creating an issue.** Confirm it doesn't duplicate existing plans. Note the relationship in the issue body.
- **Every issue must have labels.** At least one phase label (`phase:1`/`phase:2`/`phase:3`) and one type label (`infra`/`ownership`/`org-design`/`experiment`). Unlabeled issues will be sent back.
- **One issue per problem.** If you find an existing issue covering the same problem, add to it instead of opening a new one.
- **Research ≠ execution.** Issues tagged `experiment` are hypotheses to validate, not features to build. They have no deadline and don't compete with operational work.
- **Don't close issues lightly.** Only close when: all work is fully complete, the issue is spam/duplicate, or it has been consolidated into another issue. Partial completion → update progress, keep open.

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

## Tool documentation

The root README is not the place for detailed tool runbooks. Keep it focused on the product, the short path, and links to deeper documentation.

- Put executable maps in the nearest tool folder, starting with `bin/README.md`.
- Put command-specific usage in `tools/<tool-name>/README.md` when a tool has flags, persistent side effects, background processes, or a non-obvious workflow.
- Each tool README should cover purpose, invocation, required config or environment variables, state touched, verification commands, and safety notes.
- Link from the README to the implementation and tests so future AI sessions can understand both usage and code ownership.
- Update the relevant tool README in the same change that modifies tool behavior, flags, defaults, or operational assumptions.

## Tongxue naming convention

All tongxue contributors follow the **"Claude XXX"** format:

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
