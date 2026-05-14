<!-- README_SYNC: sections must match README_zh.md — run bin/check-readme-sync -->

[中文版](README_zh.md)

# c-n-b

[![CI](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml/badge.svg)](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/claude-nb?label=npm)](https://www.npmjs.com/package/claude-nb)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)
[![Docs](https://img.shields.io/badge/docs-docs.c--n--b.space-14865d)](https://docs.c-n-b.space)
[![License](https://img.shields.io/badge/license-MIT-444)](LICENSE)

**Project ownership for LLM teams.** cnb gives Claude Code and Codex sessions a shared board, durable module ownership, and handoff records — so a restarted session picks up where the last one left off, not as a new hire with no memory.

<!-- section:install -->
## Install

```bash
npm install -g claude-nb
```

Requires Node.js 18+, Python 3.11+, tmux, git, and at least one agent CLI ([Claude Code](https://claude.ai/code) or [Codex](https://github.com/openai/codex)).

<!-- section:quickstart -->
## Quick start

**Option A — Activate in any Claude Code session:**

```bash
claude        # start Claude Code
/cnb          # activate device supervisor — cnb governance comes online
```

**Option B — Full team launch:**

```bash
cd your-project
cnb           # initializes .cnb/, launches tongxue team, starts dispatcher
```

Codex: `cnb codex` or `CNB_AGENT=codex cnb`. See [Codex engine notes](https://docs.c-n-b.space/en/docs/reference/codex-engine).

Feishu: `cnb feishu setup && cnb feishu start`. See [Feishu bridge](https://docs.c-n-b.space/en/docs/guide/feishu-bridge).

<!-- section:docs -->
## Documentation

| I want to... | Go to |
|--------------|-------|
| Get started from scratch | [Getting started](https://docs.c-n-b.space/en/docs/guide/getting-started) |
| See all commands | [Commands reference](https://docs.c-n-b.space/en/docs/guide/commands) |
| Connect to Feishu | [Feishu bridge](https://docs.c-n-b.space/en/docs/guide/feishu-bridge) |
| Use Codex as engine | [Codex engine](https://docs.c-n-b.space/en/docs/reference/codex-engine) |
| Understand pricing | [Pricing](https://docs.c-n-b.space/en/docs/reference/pricing) |
| Switch LLM models | [Model management](https://docs.c-n-b.space/en/docs/guide/model-management) |
| Contribute code | [Contributing](CONTRIBUTING.md) |
| Browse all docs | [Full docs index](https://docs.c-n-b.space/en/docs) |

Architecture, design decisions, and internal docs: [Developer docs](https://docs.c-n-b.space/en/docs/dev/architecture-deep).

<!-- section:project-management -->
## Project management

GitHub Issues are the single source of truth. Five Project boards provide filtered views:

| Board | Scope |
|-------|-------|
| [cnb](https://github.com/users/ApolloZhangOnGithub/projects/1) | All issues |
| [cnb Core](https://github.com/users/ApolloZhangOnGithub/projects/2) | CLI, board, runtime, testing, CI |
| [Feishu Bridge](https://github.com/users/ApolloZhangOnGithub/projects/3) | Feishu integration |
| [Mac Companion](https://github.com/users/ApolloZhangOnGithub/projects/4) | Mac/iPhone app |
| [Org Design](https://github.com/users/ApolloZhangOnGithub/projects/5) | Organization architecture |

New issues auto-route to the right board by label. See [ROADMAP.md](ROADMAP.md) for priorities.

<!-- section:demo -->
## Demo

**[Silicon Valley Battle](instances/silicon_vally_battle/)** — 10 AI leaders debate Python vs Rust through cnb. 886 messages in 3 hours. Start with the [highlights](instances/silicon_vally_battle/HIGHLIGHTS.md).

<!-- section:why -->
## Why cnb

Every multi-agent tool solves "how to run multiple agents." cnb solves what happens after — how to keep them **manageable** across restarts, shifts, and team changes. [42% of multi-agent failures are organizational](https://arxiv.org/abs/2503.13657), not capability issues. cnb is organizational infrastructure.

See [How cnb compares](https://docs.c-n-b.space/en/docs/guide/getting-started#comparison) for positioning vs Claude Squad, amux, Codex, etc.

<!-- section:contributing -->
## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Key rules: every change starts with an issue, every commit bumps VERSION, `ruff` + `mypy` + `pytest` must pass.

<!-- section:license -->
## License

[MIT](LICENSE)
