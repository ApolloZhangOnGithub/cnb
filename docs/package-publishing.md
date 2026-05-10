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

## Release Flow

Publish only from a clean `master` checkout after the release PR is merged.

1. Set a release version without a `-dev` suffix in `VERSION`.
2. Run `python bin/sync-version` to update `package.json` and `pyproject.toml`.
3. Add a dated `CHANGELOG.md` section for the release.
4. Run:

```bash
python bin/sync-version --check
python bin/check-changelog
npm pack --dry-run
npm whoami
```

5. Publish and verify:

```bash
npm publish
npm dist-tag add claude-nb@<version> stable
npm view claude-nb version dist-tags
```

`npm publish` updates `latest` by default unless a non-default `--tag` is used. Keep `latest` and `stable` on release versions only; use another tag such as `next` for prerelease builds.

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

The workflow downloads `claude-nb@<version>` from npmjs, rewrites only package metadata for GitHub Packages, and publishes `@apollozhangongithub/cnb@<version>` with the repository `GITHUB_TOKEN`.

Rules:

- Mirror release versions only, never `-dev` versions.
- Keep npmjs `claude-nb` as the canonical install path.
- Keep the GitHub Packages package scoped and clearly tied to this repository.
- If the mirror package ever becomes a real supported install path, open a migration issue first.
