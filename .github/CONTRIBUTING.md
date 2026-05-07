# Contributing to cnb

## Issue workflow

Every change — feature, bug fix, refactor — follows this flow:

1. **Check ROADMAP first** — read `ROADMAP.md`, confirm the issue doesn't duplicate or conflict with existing plans. Note the relationship in the issue body
2. **Create issue** — describe what and why before writing code. Use the issue template (includes mandatory ROADMAP checklist)
3. **Comment "正在做"** — when you start working on it
4. **Implement + test** — code, tests, ruff, mypy all pass
5. **Verify** — confirm the feature works end-to-end
6. **Close issue** — only after verification passes

No drive-by commits. If you're fixing something, there should be an issue for it.

## Versioning

- **Every commit to master must bump VERSION** — CI enforces this
- Use **patch versions** liberally: `0.5.1 → 0.5.2 → 0.5.3`
- Save minor/major bumps for real feature releases
- After a release (`0.5.1`), immediately bump to next dev (`0.5.2-dev`)
- VERSION, package.json, and pyproject.toml must stay in sync (`bin/sync-version --check`)

## Release changelog

When publishing a release version (no `-dev` suffix), CHANGELOG.md **must** have a `## {version}` section that consolidates all changes since the previous release. This is enforced by CI (`bin/check-changelog`).

Rules:
- **Dev versions** (`0.5.14-dev`) accumulate freely under an `(unreleased)` header — no enforcement
- **Release versions** (`0.6.0`) must have a dated, non-unreleased entry with real content (≥3 lines)
- The release entry must **summarize all dev versions** since the last release — don't just copy the latest dev section
- Group by Features / Bug Fixes / Security / Tests / Breaking Changes as applicable
- If you're cutting a release and CHANGELOG.md doesn't have the entry, CI will block the merge

Workflow:
1. During dev: keep the `## X.Y.Z-dev (unreleased)` section updated as you go
2. At release time: rename the header to `## X.Y.Z (YYYY-MM-DD)`, consolidate all accumulated dev entries, trim noise
3. After release: add a new `## X.Y.(Z+1)-dev (unreleased)` section at the top

## Tone

- **Be humble.** This project exists because of Claude Code and Anthropic. Without them, cnb is nothing. Never position cnb as superior to or replacing Claude Code — cnb is an add-on that builds on top of their work.
- **Respect other projects.** When mentioning Claude Squad, amux, Codex, ittybitty, or any other tool: use "different focus", "complementary", "each has strengths" — never disparage. Acknowledge what they do better.
- Comparison tables list objective capability differences only, no subjective judgments. No "Yes/No" columns that implicitly trash the other side.
- State what cnb does, not what others don't.

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

## Bug tracker and accountability

Use the board's built-in bug tracker for incidents, regressions, and security issues:

```bash
board --as <name> bug report <P1|P2> "description"  # report (P0 = immediate, P1 = 4h, P2 = 24h)
board --as <name> bug assign <BUG-NNN> <session>     # assign
board --as <name> bug fix <BUG-NNN> "evidence"        # close with evidence
board --as <name> bug list                             # open bugs
board --as <name> bug overdue                          # SLA violations
```

Also available: `kudos` for recognition and `kudos-list` for the leaderboard.

```bash
board --as <name> kudos <target> "reason"    # give recognition
board --as lead kudos-list                   # kudos leaderboard
```

Security incidents must be reported as bugs, broadcast to all, and logged in the relevant GitHub issue.

## Shutdown checklist

Every session must complete before clocking off:

1. `git add` + `git commit` + **`git push`** — all code must be on remote
2. `board --as <name> status "progress summary"` — write what you did and where to continue
3. Write daily report to `.claudes/dailies/{shift}/{name}.md`
4. `board --as <name> ack` — confirm shutdown
5. Reply ack to lead's shutdown broadcast

**No unpushed commits.** If it's not on remote, it doesn't exist.

## Demo instances

Demo instances live in `instances/<name>/`. Unlike normal projects, demo instances **must** include cnb runtime data so others can inspect the full state:

**Must commit:**
- `.claudes/board.db` — the SQLite database (message history, tasks, all state)
- `.claudes/config.toml` — team configuration
- `.claudes/sessions/*.md` — session persona files
- All project files produced during the demo

**Must exclude:**
- `.claude/` — Claude Code runtime config (not cnb data)
- `.claudes/board.db-shm`, `.claudes/board.db-wal` — SQLite temp files
- `.claudes/logs/` — dispatcher logs (noisy, not useful for demos)
- `.DS_Store`
- Duplicate exports (e.g. if both `.md` and `.txt` versions exist, keep only `.md`)

**Must document:**
- Which files were fabricated by tongxue (e.g. social engineering attempts) vs genuine work output
- A `HIGHLIGHTS.md` with curated excerpts and commentary — most people won't read a 20k-line chat log

The `.claudes/.gitignore` auto-generated by cnb excludes `board.db` by default. Use `git add -f` to override for demo instances.

## npm publishing

After a release commit:
```bash
npm login        # if token expired
npm publish      # requires OTP or recovery code
```

CI warns when npm package version is behind local VERSION.
