---
number: 99
title: "Adopt Markrun as cnb documentation source of truth"
state: OPEN
labels: ["documentation", "phase:2", "infra", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #99 Adopt Markrun as cnb documentation source of truth

**State:** OPEN
**Labels:** documentation, phase:2, infra, priority:p2

---

## Summary

Track the cnb-side adoption of Markrun as the single source of truth for cnb documentation.

The cross-project proposal lives in Breadboard: https://github.com/ApolloZhangOnGithub/Breadboard/issues/11

This issue exists in the cnb repository because the actual content migration, review, CI policy, and generated-file rules belong to cnb.

## Owner split

- **Markrun language/tooling owner:** `ritchie` owns compatibility work on the Markrun side, per Breadboard #11.
  - cnb doc shape support: feature flags, bilingual rendering, template composition.
  - `_markrun.yml` and `fragments.mr` template library support.
  - path resolution edge cases.
  - strict/safe mode behavior so broken generated output is not committed.
- **cnb content owner:** TBD. This should be assigned before implementation starts.
  - Recommended owner profile: docs/code-health owner or project lead delegate.
  - Responsible for deciding canonical wording, bilingual parity, generated-file policy, and CI acceptance.

## Proposed migration target

Use Markrun sources for the cnb documentation suite:

```text
_markrun.yml
fragments.mr
README.mr        -> README.md
README_zh.mr     -> README_zh.md
CONTRIBUTING.mr  -> .github/CONTRIBUTING.md
CLAUDE.mr        -> CLAUDE.md
CHANGELOG.mr     -> CHANGELOG.md
SECURITY.mr      -> SECURITY.md
```

Shared data should include at minimum:

- package/project version
- install and activation commands
- team/role terminology
- board command references
- safety and high-risk-action rules
- feature flags for optional systems such as encrypted mailbox, Feishu bridge, GitHub App integration, and terminal supervisor features

## Migration strategy

Do not big-bang all docs in one PR.

1. **Decision pass**
   - Decide whether generated `.md` files remain tracked. Recommendation: keep generated `.md` tracked for GitHub/npm readability, but add a generated header and CI drift check.
   - Decide where Markrun lives in cnb: vendored script, submodule path, npm package, or dev-only checkout. Avoid making normal cnb users install extra tooling just to read docs.
   - Decide cnb-side content owner.
2. **Minimal pilot**
   - Convert only `README.md` and `README_zh.md` first.
   - Keep current rendered output semantically identical except for an explicit generated header if adopted.
   - Add a local check command that rebuilds and fails on drift.
3. **Core docs migration**
   - Add `.github/CONTRIBUTING.md` and `CLAUDE.md` once README parity is stable.
   - Extract shared fragments only when there is real duplication.
4. **Extended docs**
   - Consider `CHANGELOG.md` and `SECURITY.md` last. These may need stricter human review and may not fully benefit from templating.

## Markrun-side dependencies to check before implementation

Breadboard Markrun issues that affect safe adoption:

- https://github.com/ApolloZhangOnGithub/Breadboard/issues/7 - broken imports should not write corrupted output.
- https://github.com/ApolloZhangOnGithub/Breadboard/issues/16 - fenced examples must remain inert.
- https://github.com/ApolloZhangOnGithub/Breadboard/issues/17 - quoted version-like strings must stay strings.
- https://github.com/ApolloZhangOnGithub/Breadboard/issues/18 - CLI version should not be hard-coded stale value.
- https://github.com/ApolloZhangOnGithub/Breadboard/issues/8 and #9 are useful for larger doc trees, but should not block the minimal pilot unless the pilot needs path aliases/link rewriting.

## Acceptance criteria

- cnb has a Markrun source for at least README + README_zh, with generated Markdown matching current content semantics.
- CI or a documented local check fails if generated Markdown is stale.
- Broken imports or missing templates do not overwrite valid generated Markdown.
- Version-like values such as `"0.10"` remain strings.
- Markrun examples inside docs can be shown without being evaluated accidentally.
- The cnb-side owner is recorded before expanding beyond the README pilot.
- Breadboard #11 is updated with the cnb-side tracking link.

## Non-goals

- Rewriting cnb runtime code in Markrun.
- Converting all docs in one PR.
- Making generated docs unreadable on GitHub.
- Blocking urgent cnb fixes on a documentation-language migration.
