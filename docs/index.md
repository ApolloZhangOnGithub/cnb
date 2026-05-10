# cnb Docs

cnb documentation should work like product documentation, not like a pile of notes. Keep the README short, then move durable operating details into docs pages with stable links.

## Start Here

| Page | Purpose |
|------|---------|
| [Website](https://c-n-b.space/) | Public GitHub Pages entry for first-time visitors. |
| [README](../README.md) | Product overview, install, quick start, and the shortest command reference. |
| [Roadmap](../ROADMAP.md) | Product direction and active development themes. |
| [Contributing](../CONTRIBUTING.md) | Contributor workflow, style, and review expectations. |
| [Package publishing](package-publishing.md) | npm release, dist-tags, and GitHub Packages visibility rules. |
| [Custom domain operations](custom-domain.md) | DNS records and GoDaddy helper for the public site domain. |
| [Tongxue avatar generation](avatar-generation.md) | Safe provider choices and prompt rules for AI-generated tongxue avatars. |

## Concepts

| Page | Purpose |
|------|---------|
| [Ownership autonomy](design-ownership-autonomy.md) | Why cnb treats long-lived module ownership as the core unit of work. |
| [Contribution wall](contribution-wall.md) | Broad contribution signals beyond GitHub's commit-only Contributors panel. |

## Documentation System

Use this information architecture as the docs grow:

| Section | What belongs here |
|---------|-------------------|
| Getting Started | Installation, quick start, first team, first task. |
| Using cnb | Board commands, slash commands, swarm control, shutdown flow. |
| Concepts | Tongxue model, ownership, task lifecycle, inbox, dispatcher, security model. |
| Configuration | `.claudes/config.toml`, engines, roles, permissions, registries, hooks. |
| Operations | Health checks, usage/cost control, recovery, migrations, upgrades. |
| Reference | CLI command reference, schema, environment variables, file layout. |
| Development | Roadmap, architecture notes, contributing, release process. |
