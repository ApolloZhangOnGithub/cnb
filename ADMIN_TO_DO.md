# Admin To Do

This file tracks release actions that require maintainer credentials or registry ownership.

## c-n-b npmjs Claim

The canonical npm package is now `c-n-b`, which installs the `cnb` command. Do not publish or document the unhyphenated npm package name; it belongs to an unrelated package.

Current registry state checked from this workspace:

- `npm view c-n-b version dist-tags versions` returns 404, so the first real `c-n-b` release will claim the package.
- `npm view cnb name version description` resolves to an unrelated package.

Before the next release:

1. Log in to npmjs as the maintainer account:

   ```bash
   npm login
   npm whoami
   ```

2. Configure Trusted Publishing for `c-n-b` against `ApolloZhangOnGithub/cnb` and `.github/workflows/publish-npm.yml`.
3. Run a dry-run release workflow after the rename PR merges:

   ```bash
   gh workflow run publish-npm.yml -f version=0.5.44 -f dry_run=true
   ```

4. Create the real GitHub Release only after CI and the dry run pass. The workflow should publish `c-n-b@<version>` to npmjs and mirror `@apollozhangongithub/cnb@<version>` to GitHub Packages.
5. Verify the public install path:

   ```bash
   npm view c-n-b version dist-tags engines os peerDependencies peerDependenciesMeta --json
   npm install -g c-n-b
   cnb --version
   ```

6. Move the `stable` dist-tag to the same release if the workflow cannot do it through OIDC alone.

## Site HTTPS

`http://c-n-b.space` is already served by GitHub Pages. GitHub Pages health reports the apex and `www` records as valid and served by Pages, but HTTPS enforcement is blocked until GitHub creates the certificate.

Retry after the certificate appears:

```bash
gh api --method PUT repos/ApolloZhangOnGithub/cnb/pages \
  -F https_enforced=true \
  -f cname='c-n-b.space'
```
