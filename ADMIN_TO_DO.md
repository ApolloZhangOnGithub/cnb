# Admin To Do

This file tracks release actions that require maintainer credentials or registry ownership.

## npmjs Release

The repository is ready to publish `claude-nb@0.5.31`, but npmjs publishing requires an authenticated npm maintainer session.

1. Log in to npmjs:

   ```bash
   npm login
   npm whoami
   ```

2. From a clean checkout of the `v0.5.31` tag, publish the package:

   ```bash
   npm publish
   npm dist-tag add claude-nb@0.5.31 stable
   ```

3. Verify the public package metadata:

   ```bash
   npm view claude-nb version dist-tags engines os peerDependencies peerDependenciesMeta --json
   ```

4. Check the public npm page:

   ```text
   https://www.npmjs.com/package/claude-nb?activeTab=dependencies
   ```

   npm's Dependencies tab only reports JavaScript package dependencies. Runtime requirements such as Python, tmux, git, and Python packages are documented in the README and `pyproject.toml`.

## GitHub Packages Mirror

After `claude-nb@0.5.31` is visible on npmjs, mirror it to GitHub Packages:

```bash
gh workflow run publish-github-package.yml -f version=0.5.31
```

Verify the workflow publishes `@apollozhangongithub/cnb@0.5.31`.

## Recommended Follow-Up

- Configure npm trusted publishing or an npm automation token so future release packages can be published by GitHub Actions instead of a local maintainer shell.
- Keep npmjs `claude-nb` as the canonical user install path.
- Keep GitHub Packages as a scoped mirror only, unless a future migration issue changes that policy.
