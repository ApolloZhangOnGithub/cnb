# cnb Docs

cnb documentation should work like product documentation, not like a pile of notes. Keep the README short, then move durable operating details into docs pages with stable links.

## Start Here

| Page | Purpose |
|------|---------|
| [Website](https://c-n-b.space) | Public GitHub Pages entry for first-time visitors. |
| [README](../README.md) | Product overview, install, quick start, and the shortest command reference. |
| [Pricing and usage](pricing.md) | How cnb usage maps to Claude Code, Codex, credits, Fast mode, and team size. |
| [Feishu bridge](feishu-bridge.md) | Wake the Mac device supervisor from Feishu, quiet notifications, Web TUI viewing, resource handoff, and readback boundaries. |
| [Mac companion and Island](terminal-supervisor-island.md) | Mac companion first, optional iPhone Live Activity bridge second. |
| [Roadmap](../ROADMAP.md) | Product direction and active development themes. |
| [Contributing](../CONTRIBUTING.md) | Contributor workflow, style, and review expectations. |
| [Package publishing](package-publishing.md) | npm release, dist-tags, and GitHub Packages visibility rules. |
| [Website frontend](website-frontend.md) | Static GitHub Pages source, local preview, and layout verification. |
| [Custom domain operations](custom-domain.md) | DNS records and GoDaddy helper for the public site domain. |
| [Tongxue avatar generation](avatar-generation.md) | Safe provider choices and prompt rules for AI-generated tongxue avatars. |

## Concepts

| Page | Purpose |
|------|---------|
| [Ownership autonomy](design-ownership-autonomy.md) | Why cnb treats long-lived module ownership as the core unit of work. |
| [Codex engine notes](codex-engine.md) | How cnb launches Codex, including permission mode and smoke testing. |
| [CNB sync gateway](cnb-sync-gateway.md) | Small event-log gateway for companion clients and future sync/relay paths. |
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

This mirrors the useful shape of OpenAI and Anthropic docs: a short overview, task-oriented guides, conceptual pages, configuration reference, operational guidance, and explicit pricing/usage notes.
