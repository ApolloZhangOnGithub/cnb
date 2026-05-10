# Admin To Do

This file tracks maintainer-only actions that need registry, repository, or organization credentials.

## Current Release State

`v0.5.44` is the current verified release.

- GitHub Release: https://github.com/ApolloZhangOnGithub/cnb/releases/tag/v0.5.44
- npmjs package: `claude-nb@0.5.44`
- npmjs `latest`: `0.5.44`
- GitHub Packages mirror: `@apollozhangongithub/cnb@0.5.44`
- Release workflow: https://github.com/ApolloZhangOnGithub/cnb/actions/runs/25618433161
- End-to-end publish flow passed: npmjs Trusted Publishing, npmjs readback retry, fresh install smoke, GitHub Packages mirror publish, and GitHub Packages mirror verification.

## npm `stable` Dist-Tag

Remaining blocker: `stable` is not set yet.

Observed state:

```bash
npm view claude-nb dist-tags --json
```

Current result:

```json
{
  "latest": "0.5.44"
}
```

Local evidence:

- `~/.npmrc` contains an npmjs auth token line.
- `NPM_TOKEN` is not present in the shell environment.
- `npm whoami --registry=https://registry.npmjs.org/` returns `E401`.
- `npm dist-tag add claude-nb@0.5.44 stable` returns `E401`.

Next maintainer action:

```bash
npm login --registry=https://registry.npmjs.org/
npm whoami --registry=https://registry.npmjs.org/
npm dist-tag add claude-nb@0.5.44 stable --registry=https://registry.npmjs.org/
npm view claude-nb dist-tags --json
```

Expected final dist-tags:

```json
{
  "latest": "0.5.44",
  "stable": "0.5.44"
}
```

Tracking issue: https://github.com/ApolloZhangOnGithub/cnb/issues/100

## Optional GitHub Actions Secret

Trusted Publishing now handles `npm publish` without a local maintainer shell. It does not currently move `stable` because no usable `NPM_TOKEN` secret is available to the workflow.

If maintainers want `stable` to move automatically during release:

1. Create a valid npm token that can mutate dist-tags for `claude-nb`.
2. Add it to the GitHub repository as `NPM_TOKEN`.
3. Publish the next release normally and confirm the `Try to move stable dist-tag` step no longer reports an auth notice.

Do not store npm tokens in the repository.

## Future `c-n-b` Package Migration

`c-n-b.space` can stay as the website domain, but `c-n-b` is not a published npm package yet. Do not make it the documented install path until the migration is complete.

Before changing the canonical npm package name:

1. Confirm `npm view c-n-b` returns 404 or shows this project.
2. Configure npm Trusted Publishing for package `c-n-b` against `ApolloZhangOnGithub/cnb` and `.github/workflows/publish-npm.yml`.
3. Change package metadata, release workflows, docs, and site copy in one PR.
4. Publish a real non-dev release that claims `c-n-b`.
5. Verify the new npm package installs the `cnb` command from a clean temporary prefix.
6. Move `latest` and `stable` only after the new package is verified.

Tracking issue: https://github.com/ApolloZhangOnGithub/cnb/issues/132

## Prepare Release PR Creation

The `Prepare Release` workflow can push release branches. Repository settings currently block GitHub Actions from creating pull requests, so the workflow degrades gracefully and writes a manual compare link to the step summary.

Optional maintainer action:

- Enable GitHub Actions PR creation in repository settings if fully automatic release PR creation is desired.

Leaving this disabled is acceptable because the release branch and validation still complete; only the PR click is manual.

## GitHub Packages Sidebar

No action needed for the current release.

The repository Packages sidebar should remain populated by the scoped mirror `@apollozhangongithub/cnb`. Keep npmjs `claude-nb` as the canonical user install path until a verified package migration changes that policy.
