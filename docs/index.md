# cnb Docs

cnb documentation should work like product documentation, not like a pile of notes. Keep the README short, then move durable operating details into docs pages with stable links.

## Start Here

| Page | Purpose |
|------|---------|
| [README](../README.md) | Product overview, install, quick start, and the shortest command reference. |
| [Pricing and usage](pricing.md) | How cnb usage maps to Claude Code, Codex, credits, Fast mode, and team size. |
| [Roadmap](../ROADMAP.md) | Product direction and active development themes. |
| [Contributing](../CONTRIBUTING.md) | Contributor workflow, style, and review expectations. |

## Concepts

| Page | Purpose |
|------|---------|
| [Ownership autonomy](design-ownership-autonomy.md) | Why cnb treats long-lived module ownership as the core unit of work. |
| [Codex engine notes](codex-engine.md) | How cnb launches Codex, including permission mode and smoke testing. |

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
