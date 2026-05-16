---
number: 100
title: "Add npm stable tag after refreshing npm auth"
state: OPEN
labels: ["bug", "documentation", "phase:1", "infra", "priority:p0"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #100 Add npm stable tag after refreshing npm auth

**State:** OPEN
**Labels:** bug, documentation, phase:1, infra, priority:p0

---

## Context

The installable CLI package is the unscoped npmjs package `claude-nb`, not a GitHub Packages package.

Observed on 2026-05-10:

- `npm view claude-nb version dist-tags versions` reports published versions `0.3.0`, `0.4.0`, and `0.5.1`.
- npmjs dist-tags currently show only `latest: 0.5.1`; there is no `stable` tag yet.
- Attempting `npm dist-tag add claude-nb@0.5.1 stable` from the local machine failed with `E401` because the npm token in `~/.npmrc` is invalid.
- GitHub repo homepage has been set to https://www.npmjs.com/package/claude-nb so the real package is visible from the repository sidebar.
- README / CONTRIBUTING / docs now document that GitHub's repo Packages sidebar only shows GitHub Packages, not npmjs packages.

GitHub docs note that repository Packages lists packages published to GitHub Packages, and GitHub Packages npm publishing requires a scoped name such as `@namespace/package-name`. The current public install path is intentionally `npm install -g claude-nb`, so publishing the existing unscoped package to `npm.pkg.github.com` is not a safe one-line fix.

## Why this matters

The repository can display "No packages published" even though `claude-nb` exists on npmjs.com. That is confusing for users and for future tongxue maintaining releases.

## Acceptance criteria

- [ ] Refresh npm publisher authentication safely; do not commit tokens or logs.
- [ ] Add `stable` to the current supported npmjs release, or publish a new release first and then move both `latest` and `stable` to that release.
- [ ] Do not publish a `-dev` version to `latest` or `stable`.
- [ ] Verify with `npm view claude-nb version dist-tags versions`.
- [ ] Decide separately whether cnb needs a GitHub Packages companion package. If yes, open/attach a migration plan for a scoped package name and install-path documentation.
- [ ] Keep `docs/package-publishing.md` and `CONTRIBUTING.md` aligned with the final release workflow.

## Related files

- `README.md`
- `README_zh.md`
- `CONTRIBUTING.md`
- `docs/package-publishing.md`
- `package.json`

