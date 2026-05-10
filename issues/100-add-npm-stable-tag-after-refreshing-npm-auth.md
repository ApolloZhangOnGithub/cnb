---
number: 100
title: "Claim c-n-b on npmjs and add stable tag after release"
state: OPEN
labels: ["bug", "documentation", "phase:1", "infra"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #100 Claim c-n-b on npmjs and add stable tag after release

**State:** OPEN
**Labels:** bug, documentation, phase:1, infra

---

## Context

The installable CLI package should be the unscoped npmjs package `c-n-b`, not a GitHub Packages package and not the unrelated `cnb` package.

Observed on 2026-05-10:

- `npm view c-n-b version dist-tags versions` returns 404, so the first real release will claim the package name.
- `npm view cnb name version description` resolves to an unrelated package, so users must not be told to install `cnb` from npm.
- GitHub repo homepage should stay on `c-n-b.space`; package links should point to `https://www.npmjs.com/package/c-n-b`.
- README / CONTRIBUTING / docs now document that GitHub's repo Packages sidebar only shows GitHub Packages, not npmjs packages.

GitHub docs note that repository Packages lists packages published to GitHub Packages, and GitHub Packages npm publishing requires a scoped name such as `@namespace/package-name`. The intended public install path is `npm install -g c-n-b`, so publishing the unscoped package to `npm.pkg.github.com` is not a safe one-line fix.

## Why this matters

The repository can display "No packages published" even after `c-n-b` exists on npmjs.com because GitHub only shows GitHub Packages. That is confusing for users and for future tongxue maintaining releases.

## Acceptance criteria

- [ ] Configure npm Trusted Publishing for package `c-n-b`; do not commit tokens or logs.
- [ ] Publish a new non-dev release that claims `c-n-b`, then move both `latest` and `stable` to that release.
- [ ] Do not publish a `-dev` version to `latest` or `stable`.
- [ ] Verify with `npm view c-n-b version dist-tags versions`.
- [ ] Decide separately whether cnb needs a GitHub Packages companion package. If yes, open/attach a migration plan for a scoped package name and install-path documentation.
- [ ] Keep `docs/package-publishing.md` and `CONTRIBUTING.md` aligned with the final release workflow.

## Related files

- `README.md`
- `README_zh.md`
- `CONTRIBUTING.md`
- `docs/package-publishing.md`
- `package.json`
