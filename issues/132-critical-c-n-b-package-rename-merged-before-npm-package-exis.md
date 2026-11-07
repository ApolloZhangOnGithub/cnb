---
number: 132
title: "Critical: c-n-b package rename merged before npm package exists"
state: CLOSED
labels: ["bug", "documentation", "phase:1", "infra", "priority:p0"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #132 Critical: c-n-b package rename merged before npm package exists

**State:** CLOSED
**Labels:** bug, documentation, phase:1, infra, priority:p0

---

## Problem

PR #130 changed the public package surface from `claude-nb` to `c-n-b` on `master`, including package metadata, release workflows, docs, site copy, and GitHub Release titles.

That is not aligned with the live registry state.

## Current evidence

As of 2026-05-10 11:30 CST:

```bash
npm view claude-nb name version dist-tags --json
```

returns:

```json
{
  "name": "claude-nb",
  "version": "0.5.44",
  "dist-tags": {
    "latest": "0.5.44"
  }
}
```

But:

```bash
npm view c-n-b name version dist-tags --json
```

returns npm `E404 Not Found`.

Current `origin/master` after #130 has:

```json
{
  "name": "c-n-b",
  "version": "0.5.45-dev",
  "bin": {"cnb": "bin/cnb.js"}
}
```

## Why this is severe

- README/site/docs can now tell users to install `c-n-b`, but `npm install -g c-n-b` cannot work yet.
- Release workflows now target `PACKAGE_NAME: c-n-b`; the next release would depend on npm Trusted Publishing being configured for a package that currently does not exist.
- GitHub Release titles were renamed to `c-n-b 0.5.44`, `c-n-b 0.5.43`, and `c-n-b 0.5.31`, even though those releases were actually published to npmjs as `claude-nb`.
- `ADMIN_TO_DO.md` was rewritten around the future `c-n-b` claim and lost the just-verified `claude-nb@0.5.44` release state / `stable` dist-tag blocker context.

## Recommended immediate fix

Do not proceed as if `c-n-b` is already the canonical package.

Restore current public install and release surfaces to the verified package name `claude-nb` until a controlled migration is completed:

- `package.json` / `pyproject.toml` package name should remain `claude-nb` for now.
- `publish-npm.yml` and `publish-github-package.yml` should publish/mirror from `claude-nb` for now.
- README/site/docs should not tell users to install `c-n-b` until npmjs has that package and a release has been verified.
- GitHub Release titles for existing tags should reflect the actual published npm package, or at least avoid implying those tags were published as `c-n-b`.
- Keep a separate migration issue/checklist for claiming `c-n-b`, configuring Trusted Publishing, dry-running, publishing, and then switching docs.

## Related

- PR #130: https://github.com/ApolloZhangOnGithub/cnb/pull/130
- Verified release workflow for `claude-nb@0.5.44`: https://github.com/ApolloZhangOnGithub/cnb/actions/runs/25618433161
- npm stable tag follow-up: #100
