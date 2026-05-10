---
number: 94
title: "Decision: keep Apollo repo canonical; use cnb-workspace/cnb as GitHub App test repo"
state: OPEN
labels: ["documentation", "phase:3", "infra", "org-design", "decision", "migration"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #94 Decision: keep Apollo repo canonical; use cnb-workspace/cnb as GitHub App test repo

**State:** OPEN
**Labels:** documentation, phase:3, infra, org-design, decision, migration

---

## Decision

For now, `ApolloZhangOnGithub/cnb` remains the canonical repository. Do not migrate the project to `cnb-workspace/cnb` yet.

`cnb-workspace/cnb` exists as a test repository for organization-owned GitHub App work, especially app identity/avatar experiments for tongxue. Treat it as a sandbox, not as the source of truth.

## Why

We want organization-owned GitHub Apps so tongxue can eventually act with organization app identities and avatars. The `cnb-workspace` organization is the right long-term home for that, but repository transfer has real coordination risk: issues, PRs, wiki, app installations, remotes, branch state, npm metadata, and contributor workflows all need a deliberate migration window.

The current owner is not fully comfortable with the migration mechanics yet, so we should avoid introducing migration risk while active feature work is ongoing.

## Current operating rules

- Canonical code, issues, PRs, and wiki stay under `ApolloZhangOnGithub/cnb`.
- Use `cnb-workspace/cnb` only for GitHub App / organization permission / avatar experiments.
- Do not open canonical feature PRs against `cnb-workspace/cnb` unless a later migration decision explicitly changes this.
- Do not split issue tracking or wiki updates across both repositories.
- If a local checkout has both remotes, prefer `origin = https://github.com/ApolloZhangOnGithub/cnb.git` for canonical development.

## Future migration checklist

When we are ready to migrate:

1. Rename the current `cnb-workspace/cnb` sandbox to something like `cnb-bootstrap` or `cnb-app-sandbox` so the destination name is free.
2. Transfer `ApolloZhangOnGithub/cnb` to `cnb-workspace/cnb` using GitHub repository transfer, preserving issues, PRs, wiki, stars, releases, settings, and redirects.
3. Update local remotes to the new canonical URL.
4. Update `package.json` repository/bugs metadata and any docs that mention the old canonical repo.
5. Transfer GitHub App registrations separately if they were created under a personal account. Repository transfer does not automatically transfer App ownership.
6. Re-check GitHub App installation access after repo transfer, especially selected-repository installs.
7. Rotate App private keys and deployment secrets after ownership changes.
8. Verify wiki clone, issue links, PR links, Actions, npm publish workflow, and branch protections.

## References

- GitHub repository transfers move issues, PRs, wiki, stars, releases/settings, and keep redirects, but the target account cannot already have a repo with the same name.
- GitHub App registrations can be transferred separately to a user or organization by the App owner/App manager.

## Done condition

This issue can close only after either:

- the repository is intentionally transferred to `cnb-workspace/cnb` and the checklist above is completed, or
- we decide permanently that `ApolloZhangOnGithub/cnb` remains canonical and the workspace repo remains only an app sandbox.
