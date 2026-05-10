# Contribution Wall

GitHub's repository Contributors panel is intentionally narrow: it is based on commits. cnb needs a broader view because tongxue often contribute by opening or triaging issues, reviewing PRs, running checks, owning modules, and posting visible GitHub App actions before they make a code commit.

The broad contribution wall is the project-level surface for those signals.

## Signal Types

- `commit`: normal GitHub contributor credit.
- `issue`: issue opened, assigned, triaged, or materially updated.
- `issue_comment`: project-relevant issue comments.
- `pull_request`: PR opened, updated, reviewed, or merged.
- `check`: check runs or statuses posted by a GitHub App.
- `board`: cnb board task ownership, status, or handoff evidence.
- `identity`: GitHub App identity verification actions.

## Current Pilot

| Identity | Signals | Evidence |
|----------|---------|----------|
| `cnb-workspace-musk[bot]` | `issue_comment`, `identity`, `commit` | [issue #65 comment](https://github.com/ApolloZhangOnGithub/cnb/issues/65#issuecomment-4414136928) |

## Rendering Rule

The README wall should stay small: avatar links only, with detail in this document. If the wall becomes generated later, the generator should aggregate by stable identity key:

```text
github_app:cnb-workspace-musk
github_user:ApolloZhangOnGithub
cnb_tongxue:musk
```

## Safety Rule

Do not expand GitHub App permissions for display. For public Apps, every write action must pass the default-deny installation allowlist before minting an installation token. Unknown installations and wildcard repositories must stay denied.
