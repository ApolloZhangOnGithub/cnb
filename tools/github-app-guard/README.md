# GitHub App Guard

`lib.github_app_guard` is a default-deny safety gate for public GitHub Apps.
Run it before minting an installation token or acting on a webhook.

The guard enforces:

- default-deny policy
- explicit repository names only
- no repository wildcards
- pinned `installation_id` when known
- short-lived expiry for pending, unpinned installs

Validate the current Musk policy:

```bash
python -m lib.github_app_guard validate --app cnb-workspace-musk
```

Check whether the current installed organization sandbox can act on the
management repository:

```bash
python -m lib.github_app_guard check \
  --app cnb-workspace-musk \
  --repository cnb-workspace/cnb
```

When a public App is installed into another account, update
`~/.github-apps/<app-slug>/allowlist.json` with the real `installation_id` and
remove the temporary expiry. Unknown installations must stay denied even if
GitHub allowed the user to install the public App.

To mint a token safely, use the guarded identity helper. It fetches live
installation metadata, checks the allowlist, and scopes the token to one
repository:

```bash
python -m lib.github_app_identity token \
  --app cnb-workspace-musk \
  --repository ApolloZhangOnGithub/cnb
```

If exactly one pinned allowlist rule matches the repository, `token` selects
that `installation_id` automatically. Pass `--installation-id` only while
pinning a new install.

The token is redacted by default. Use `--print-token` only inside a controlled
pipeline that immediately consumes it.

`board task done` also uses this path for auto-PR creation when a matching
local App identity exists. By convention, session `musk` maps to
`~/.github-apps/cnb-workspace-musk`; override with `CNB_GITHUB_APP_SLUG` or
`CNB_GITHUB_APP_SLUG_<SESSION>`. If no App identity is configured, auto-PR
falls back to the existing `gh` authentication.

Prefer session-specific bindings so names cannot collide:

```toml
[session.musk]
github_app_slug = "cnb-workspace-musk"
github_app_installation_id = "130997703" # optional; allowlist lookup can infer it
```

Environment overrides follow the same rule:

```bash
CNB_GITHUB_APP_SLUG_MUSK=cnb-workspace-musk
CNB_GITHUB_APP_INSTALLATION_ID_MUSK=130997703
```

`CNB_GITHUB_APP_SLUG` remains as a compatibility fallback, but it is unsafe for
multi-session projects. If two configured sessions resolve to the same App slug,
auto-PR skips the App token and falls back to the existing `gh` authentication.
