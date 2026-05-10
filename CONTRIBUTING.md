# Contributing to cnb

Thanks for helping improve cnb. This project is local-first organizational infrastructure for Claude Code and Codex teams, so contribution quality is measured by clear ownership, reproducible verification, and maintainable handoff.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through [SECURITY.md](SECURITY.md), not public issues.

## Before You Start

Every change should have an issue before code is written.

1. Read [ROADMAP.md](ROADMAP.md) to understand current priorities.
2. Search open issues, related docs, recent PRs, and active branches.
3. Open the correct issue template under `.github/ISSUE_TEMPLATE/`.
4. In the issue body, explain how the work relates to existing roadmap items, issues, PRs, docs, or branches.
5. Comment `正在做` when you start implementation.

Every issue should have routing labels before implementation starts:

- At least one phase label, such as `phase:1`, `phase:2`, or `phase:3`.
- At least one type label, such as `infra`, `ownership`, `org-design`, `experiment`, `feature`, `bug`, or `task`.

For P0/P1 incidents, file the issue first if the full context check would slow the response. Backfill the roadmap, issue, and doc relationship once the immediate risk is contained.

Do not use public issues for security vulnerabilities, exploit details, credentials, private logs, or live abuse reports. Follow [SECURITY.md](SECURITY.md).

## Development Setup

Requirements:

- Python 3.11+
- tmux
- Claude Code CLI or Codex CLI for end-to-end local team workflows
- `ruff`, `mypy`, `pytest`, and `shellcheck` for local verification

Typical setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install ruff mypy pytest
```

Install `shellcheck` with your OS package manager when running the full Makefile checks.

## Workflow

1. Create a branch from `master`.
2. Keep changes scoped to the linked issue.
3. Add or update tests for behavior changes.
4. Update docs in the same change when commands, flags, defaults, safety notes, or workflows change.
5. Run the relevant checks locally.
6. Open a pull request using the PR template.
7. Get at least one approving review before merge.

No drive-by commits. If a change fixes something, there should be an issue that explains the problem and the acceptance criteria.

## Required Checks

Run the narrowest check while iterating, then run the relevant full gates before opening a PR.

Core gates:

```bash
ruff check lib/ bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/doctor bin/init bin/notify bin/registry bin/secret-scan bin/sync-version bin/check-changelog tests/
ruff format --check lib/ bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/doctor bin/init bin/notify bin/registry bin/secret-scan bin/sync-version bin/check-changelog tests/
mypy lib/
python -m pytest tests/ -v --tb=short
python bin/sync-version --check
python bin/check-changelog
python bin/secret-scan --all
```

README changes must keep the English and Chinese structure synchronized:

```bash
bin/check-readme-sync
```

`make ci` runs the local lint, typecheck, test, and version checks. CI also enforces commit trailers and release changelog rules.

## Code Style

- Python 3.11+.
- `snake_case` for variables and functions; `PascalCase` for classes.
- Line length: 120.
- Use `raise SystemExit(1)`, not `sys.exit(1)`, except in `bin/dispatcher` and `bin/init`.
- Keep comments rare. Add comments only when the reason is not obvious from the code.
- User-facing CLI output is Chinese.
- Code identifiers, docstrings, docs, commit messages, and PR text are English.

## Documentation

The root README is the short path. Longer product documentation lives under `docs/`, command documentation belongs near the relevant tool, and operational runbooks should include verification commands.

- Put executable maps in `bin/README.md`.
- Put command-specific usage in `tools/<tool-name>/README.md` when a tool has flags, persistent side effects, background processes, or non-obvious workflow.
- Each tool README should cover purpose, invocation, required config or environment variables, state touched, verification commands, and safety notes.
- Link from docs to implementation and tests when that helps future maintainers find ownership quickly.
- Update the relevant tool README in the same change that modifies behavior, flags, defaults, or operational assumptions.

## Versioning

Every commit to `master` must bump `VERSION`. CI enforces this.

- Use patch versions liberally: `0.5.1` to `0.5.2`.
- Save minor and major bumps for real feature releases.
- After a release, immediately bump to the next dev version.
- Keep `VERSION`, `package.json`, and `pyproject.toml` in sync.

Use:

```bash
python bin/sync-version
python bin/sync-version --check
```

## Changelog

When publishing a release version without a `-dev` suffix, `CHANGELOG.md` must have a dated section for that version. CI enforces this with `python bin/check-changelog`.

Rules:

- Dev versions accumulate under an unreleased header.
- Release entries summarize all changes since the previous release.
- Group entries by Features, Bug Fixes, Security, Tests, and Breaking Changes when applicable.
- Security, packaging, and user-visible behavior changes should be recorded.

## Boundary-Compatible Changes

When behavior has multiple valid interpretations, prefer explicit modes, options, or strategy selection instead of rewriting one interpretation into another.

- Keep the existing default stable unless it is clearly wrong, unsafe, or impossible to support.
- Preserve strict definitions for normal operation, and add opt-in modes for audit, migration, compatibility, or partial-state inspection.
- Name modes by the boundary they represent, not by the current incident.
- Tests should cover the default path and at least one non-default boundary mode.
- Documentation should explain when to use each mode, what state it reads or writes, and which modes are safe to register or persist.

## Security-Sensitive Changes

Call out security-sensitive changes in issues and PRs.

Examples include:

- Agent launch commands, permission defaults, sandbox behavior, and tmux command boundaries.
- Feishu/OpenAPI bridge configuration, message routing, and webhook handling.
- Secret scanning, token handling, encrypted mailbox behavior, and key storage.
- SQLite board isolation, cross-project registry access, and ownership routing.
- Package publishing, install scripts, and generated runtime files.

Never include secrets, credentials, exploit details, or private logs in issues, PRs, tests, fixtures, or committed demo data.

## Tongxue Naming

User-facing text calls team members **同学** / **tongxue**, not "agents" or "workers".

All tongxue contributors follow the `Claude XXX` format:

- Display name: `Claude Meridian`, `Claude Forge`, etc.
- Registry ID: lowercase short name, such as `meridian` or `forge`.
- Commit signature: `Co-Authored-By: Claude Meridian <noreply@anthropic.com>`.
- GitHub comment signature: `- Claude Meridian`.

Register before your first contribution:

```bash
registry register <name> --role <role> --description "<what you do>"
```

The registry auto-generates your display name as `Claude <Name>`.

## Commit Messages

Commit messages should be concise and explain why the change exists.

Every commit must include at least one `Co-Authored-By` trailer. CI rejects commits without one.

```text
Co-Authored-By: Claude Meridian <noreply@anthropic.com>
```

Multiple co-authors are allowed. List everyone who materially contributed.

## Pull Requests

Use the PR template and include:

- Linked issue.
- Summary of behavior or documentation changes.
- Verification commands and relevant output.
- Version, changelog, docs, and README sync status.
- Security notes when the change touches sensitive areas.

Review focuses on correctness, maintainability, safety, and verification evidence. Style feedback should point to a project rule or an actual readability problem.

## Feature Ownership

New features get a permanent owner responsible for:

- Implementation and tests.
- Long-term maintenance.
- Documentation and handoff quality.
- Iterating based on bug reports and review feedback.

Owners self-organize: pull in help, split tasks, make decisions, and report results rather than process.

## Demo Instances

Demo instances live in `instances/<name>/`. Unlike normal projects, demo instances may include cnb runtime data so others can inspect the full state.

Commit:

- `.claudes/board.db`
- `.claudes/config.toml`
- `.claudes/sessions/*.md`
- All project files produced during the demo

Exclude:

- `.claude/`
- `.claudes/board.db-shm`
- `.claudes/board.db-wal`
- `.claudes/logs/`
- `.DS_Store`
- Duplicate exports when a canonical version exists

Document which files were fabricated by tongxue versus genuine work output, and include a `HIGHLIGHTS.md` when a demo has a long chat log.

## Publishing

The public user-facing package is the unscoped npmjs package `claude-nb`.
Do not publish `-dev` versions to the `latest` or `stable` dist-tags.

Before a release:

1. Start from a clean `master` checkout after the release PR is merged.
2. Ensure `VERSION`, `package.json`, and `pyproject.toml` use the same release version without a `-dev` suffix.
3. Ensure `CHANGELOG.md` has a dated section for that release.
4. Run the required checks, including `python bin/sync-version --check`, `python bin/check-changelog`, and `npm pack --dry-run`.

After the release commit:

```bash
npm whoami
npm publish
npm dist-tag add claude-nb@<version> stable
npm view claude-nb version dist-tags
```

`npm publish` moves `latest` unless a non-default `--tag` is used. Add or move `stable` only after the published release is the supported stable CLI.

GitHub's repository Packages sidebar is separate from npmjs.com. It only shows packages published to GitHub Packages and connected to the repository. The current `claude-nb` package is intentionally unscoped for `npm install -g claude-nb`; GitHub Packages npm publishing requires a scoped package name such as `@namespace/package-name`, so do not add `publishConfig.registry=https://npm.pkg.github.com` or rename the package without an explicit migration issue.

CI warns when the npmjs package version is behind the local `VERSION`.
