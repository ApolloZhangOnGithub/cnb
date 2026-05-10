# Security Policy

## Supported Versions

cnb is pre-1.0 and actively changing. Security fixes are supported for:

- The current `master` branch.
- The latest published release when a fix can be shipped without a broad migration.

Older development snapshots are best-effort only. Upgrade to the latest release or current `master` before reporting an issue that may already be fixed.

## Reporting a Vulnerability

Do not open a public GitHub issue for vulnerabilities, exploit details, secrets, or live abuse reports.

Use GitHub private vulnerability reporting or a private security advisory for the canonical repository:

https://github.com/ApolloZhangOnGithub/cnb/security/advisories/new

If that route is unavailable, contact a maintainer privately through GitHub and include only enough public information to establish contact. Do not post reproduction steps, credentials, tokens, logs containing secrets, or exploit code in public channels.

Please include:

- Affected version, commit, or installation method.
- Impact and realistic attack scenario.
- Minimal reproduction steps.
- Whether the issue affects local files, tmux sessions, SQLite board state, credentials, Feishu/OpenAPI configuration, or remote package distribution.
- Any safe workaround you have already confirmed.

## Response Expectations

Maintainers aim to acknowledge credible reports within 7 days. Fix timing depends on severity, affected surface, and whether the report includes a reproducible case.

Security fixes should include:

- A regression test or documented verification command when practical.
- A changelog entry when the fix affects released users.
- A coordinated disclosure note if public details should wait for a release.

## Security-Sensitive Areas

Treat changes in these areas as security-sensitive and call them out in PRs:

- Agent launch commands, sandbox or permission defaults, and tmux command injection boundaries.
- Feishu/OpenAPI bridge configuration, message routing, and webhook handling.
- Secret scanning, token handling, private mailbox encryption, and key storage.
- SQLite board isolation, cross-project registry access, and ownership routing.
- Package publishing, install scripts, and generated runtime files.
