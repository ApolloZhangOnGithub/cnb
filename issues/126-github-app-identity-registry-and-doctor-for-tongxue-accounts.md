---
number: 126
title: "GitHub App identity registry and doctor for tongxue accounts"
state: OPEN
labels: ["phase:2", "ownership", "infra", "org-design"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #126 GitHub App identity registry and doctor for tongxue accounts

**State:** OPEN
**Labels:** phase:2, ownership, infra, org-design

---

## Context check

- [x] Checked related work: #65 is the original GitHub App/avatar identity proposal.
- [x] Searched existing issues for `GitHub App identity doctor app slug tongxue identity` and `同学 身份 GitHub App 头像`; no duplicate found.
- [x] This is routed to ownership/infra/org-design because it affects durable tongxue identity, App token use, and auto-PR attribution.

## Problem and goal

GitHub App identities let each tongxue act with a visible independent avatar/account, but the current local setup can still drift if identity binding is only inferred from a short session name such as `musk -> cnb-workspace-musk`.

The immediate guard path should remain default-deny, but the long-term product needs an explicit identity registry and a doctor command so operators can see which tongxue identities are configured, installed, allowed for the current repository, and safe to use.

## Current mitigation

A short-term fail-closed mitigation is being added locally:

- prefer session-specific bindings such as `[session.musk].github_app_slug` or `CNB_GITHUB_APP_SLUG_MUSK`;
- keep the name convention only as a compatibility fallback;
- skip App-token injection when multiple configured sessions resolve to the same App slug;
- continue to require allowlist + repository + installation checks before minting a token.

That mitigation reduces immediate misattribution risk, but it does not replace a durable registry and audit surface.

## Proposed work

Add a first-class GitHub App identity management surface:

1. Add a `cnb github-app doctor` command, or equivalent module command, that lists every configured session and reports:
   - configured `github_app_slug` source: config, session env, global env, or name convention;
   - local credential presence under `~/.github-apps/<slug>/` without printing secrets;
   - allowlist validity;
   - resolved installation id for the current repository;
   - duplicate App slug conflicts across sessions;
   - whether auto-PR may safely use the App token.
2. Support explicit per-session config as the preferred durable binding:
   - `[session.<name>] github_app_slug = "..."`
   - optional `[session.<name>] github_app_installation_id = "..."`
3. Decide whether global `CNB_GITHUB_APP_SLUG` should stay compatibility-only, warn, or be removed.
4. Document an operator workflow for adding a new tongxue identity from GitHub App creation through allowlist pinning and doctor verification.
5. Keep all outputs secret-safe: no private key paths beyond the slug directory, no raw token, no webhook secret, no installation token.

## Acceptance criteria

- `cnb github-app doctor` or the chosen command prints a clear table for all sessions in the current project.
- A project with two sessions resolving to the same App slug reports a blocking conflict.
- A session with a valid slug, private key, allowlist, and repository installation reports usable status.
- A missing private key, missing allowlist, unpinned ambiguous allowlist entry, or repository mismatch reports a non-usable status with a concrete next step.
- Auto-PR behavior and doctor behavior share the same binding-resolution logic.
- Tests cover config binding, session env binding, global env compatibility, name convention fallback, duplicate slug conflict, and missing credential cases.
- Tool README or docs explain the identity lifecycle and safe verification commands.

