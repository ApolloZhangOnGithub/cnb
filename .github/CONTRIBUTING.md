# Contributing to cnb

## Issue workflow

Every change — feature, bug fix, refactor — follows this flow:

1. **Create issue first** — describe what and why before writing code
2. **Comment "正在做"** — when you start working on it
3. **Implement + test** — code, tests, ruff, mypy all pass
4. **Verify** — confirm the feature works end-to-end
5. **Close issue** — only after verification passes

No drive-by commits. If you're fixing something, there should be an issue for it.

## Versioning

- **Every commit to master must bump VERSION** — CI enforces this
- Use **patch versions** liberally: `0.5.1 → 0.5.2 → 0.5.3`
- Save minor/major bumps for real feature releases
- After a release (`0.5.1`), immediately bump to next dev (`0.5.2-dev`)
- VERSION, package.json, and pyproject.toml must stay in sync (`bin/sync-version --check`)

## Naming

- Team members are called **同学** (classmates), not "agents", in all user-facing text
- Code identifiers, docstrings, commit messages: English
- User-facing output (CLI messages, errors): Chinese
- README / docs: English

## Code style

- `ruff check --fix && ruff format` before every commit
- `mypy lib/` must pass with zero errors (CI enforces as hard gate)
- `raise SystemExit(1)`, never `sys.exit(1)` (except `bin/dispatcher` and `bin/init`)
- No comments unless the WHY is non-obvious
- Line length: 120

## Testing

- Tests use `tmp_path` for isolated DB/filesystem
- Mock tmux/subprocess, never the database — tests hit real SQLite
- Run `pytest` before pushing

## Feature ownership

New features get a **permanent owner** who is responsible for:
- Implementation and testing
- Long-term maintenance
- Iterating based on feedback

Owner self-organizes: pulls in help, splits tasks, makes decisions. Reports results, not process.

## Contributor attribution

Every commit must include a `Co-Authored-By` trailer identifying who wrote it:

```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
Co-Authored-By: musk
```

Multiple co-authors are fine — list everyone who contributed. CI rejects commits without at least one `Co-Authored-By` line.

View the contributor leaderboard:
```bash
cnb leaderboard
```

## npm publishing

After a release commit:
```bash
npm login        # if token expired
npm publish      # requires OTP or recovery code
```

CI warns when npm package version is behind local VERSION.
