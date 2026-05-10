# Package Publishing

cnb has two different package surfaces:

- The installable CLI package is `claude-nb` on npmjs.com.
- GitHub's repository Packages sidebar shows GitHub Packages only.

These are not the same registry. Seeing "No packages published" in the GitHub sidebar does not mean the npmjs package is missing.

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

Do not route the existing `claude-nb` package to GitHub Packages by adding `publishConfig.registry=https://npm.pkg.github.com`.

GitHub Packages npm publishing requires a scoped package name such as `@namespace/package-name`. The current public CLI name is intentionally unscoped so users can install it with:

```bash
npm install -g claude-nb
```

If the project later needs a GitHub Packages entry for repository visibility or GitHub App workflows, handle it as a separate migration:

- Choose the namespace, likely a lowercase user or organization scope.
- Decide whether it is a companion package or a breaking rename.
- Publish it to GitHub Packages and connect it to this repository.
- Document the install path separately from the npmjs package.

