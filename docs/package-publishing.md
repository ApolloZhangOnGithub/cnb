# Package Publishing

cnb has two different package surfaces:

- The canonical installable CLI package is `claude-nb` on npmjs.com.
- The GitHub Packages sidebar is populated by the scoped mirror package `@apollozhangongithub/cnb`.

These are not the same registry. Do not change the npmjs package name just to satisfy the GitHub sidebar.

## Current Package

Use npmjs for user installs:

```bash
npm install -g claude-nb
```

Check the public package state:

```bash
npm view claude-nb version dist-tags versions
npm dist-tag ls claude-nb
```

The GitHub Packages mirror exists for repository visibility and GitHub-native package metadata. It is not the primary user install path.

The npm Dependencies tab only reports JavaScript packages listed in `dependencies`. cnb is an npm-distributed Bash/Python CLI, so a low npm dependency count does not mean it has no runtime requirements.

Keep the runtime contract visible in three places:

- `package.json` `engines` and optional `peerDependencies` for supported agent CLIs.
- `README.md` / `README_zh.md` install section for system and Python requirements.
- `pyproject.toml` for Python package dependencies such as `cryptography`.

Do not add unused npm packages just to make the dependency count nonzero. If a dependency is not required by `bin/cnb.js` or another JavaScript entrypoint, it does not belong in `dependencies`.

## Release Flow

Publish only after the release PR is merged to `master`.

1. Set a release version without a `-dev` suffix in `VERSION`.
2. Run `python bin/sync-version` to update `package.json` and `pyproject.toml`.
3. Add a dated `CHANGELOG.md` section for the release.
4. Run:

```bash
python bin/sync-version --check
python bin/check-changelog
npm pack --dry-run
```

5. Create a GitHub Release for the matching tag, for example `v0.5.39`.

The `Publish npm Release` workflow then publishes `claude-nb` to npmjs and mirrors the same release to GitHub Packages. It can also be run manually in dry-run mode:

```bash
gh workflow run publish-npm.yml -f version=<version> -f dry_run=true
```

`npm publish` updates `latest` by default unless a non-default `--tag` is used. The workflow also tries to move the `stable` dist-tag to the same version. If npm accepts OIDC only for the publish operation in the current registry behavior, add a granular `NPM_TOKEN` repository secret for dist-tag mutation or move `stable` manually after verifying the release.

## One-time npm Trusted Publishing setup

The npmjs publish step uses Trusted Publishing through GitHub Actions OIDC. This avoids a long-lived npm publish token in GitHub secrets.

Configure the package once from an npm account that owns `claude-nb`:

```bash
npm install -g npm@^11.10.0
npm login
npm trust github claude-nb --repo ApolloZhangOnGithub/cnb --file publish-npm.yml
npm trust list claude-nb
```

Equivalent npmjs.com UI settings:

- package: `claude-nb`
- trusted publisher: GitHub Actions
- organization/user: `ApolloZhangOnGithub`
- repository: `cnb`
- workflow filename: `publish-npm.yml`
- environment: leave blank unless the workflow is later moved behind a protected GitHub Environment

After this setup, creating a GitHub Release is enough to publish the package. If the package owner later enables "disallow tokens", Trusted Publishing continues to work while old token-based publish paths stop working.

## GitHub Packages

Do not route the existing `claude-nb` package to GitHub Packages by adding `publishConfig.registry=https://npm.pkg.github.com` to the root package. That would make normal maintainers much more likely to publish the canonical npmjs package to the wrong registry.

GitHub Packages npm publishing requires a scoped package name such as `@namespace/package-name`. The current public CLI name is intentionally unscoped so users can install it with:

```bash
npm install -g claude-nb
```

To keep GitHub Packages populated without changing the user-facing npmjs package, mirror a published npmjs release into the scoped package:

```bash
gh workflow run publish-github-package.yml -f version=0.5.1
```

The release workflow now does this automatically after a successful npmjs release. The manual `publish-github-package.yml` workflow remains as a repair path for old releases or failed mirror runs. It downloads `claude-nb@<version>` from npmjs, rewrites only package metadata for GitHub Packages, and publishes `@apollozhangongithub/cnb@<version>` with the repository `GITHUB_TOKEN`.

Rules:

- Mirror release versions only, never `-dev` versions.
- Keep npmjs `claude-nb` as the canonical install path.
- Keep the GitHub Packages package scoped and clearly tied to this repository.
- If the mirror package ever becomes a real supported install path, open a migration issue first.
