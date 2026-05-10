<!-- README_SYNC: sections must match README_zh.md — run bin/check-readme-sync -->

[中文版](README_zh.md)

# c-n-b

[![CI](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml/badge.svg)](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/claude-nb?label=npm)](https://www.npmjs.com/package/claude-nb)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)
[![Docs](https://img.shields.io/badge/docs-c--n--b.space-14865d)](https://c-n-b.space)
[![License](https://img.shields.io/badge/license-OpenAll--1.0-444)](LICENSE)

**Project ownership for LLM teams.**

`cnb` is local-first organizational infrastructure for long-lived Claude Code and Codex teams. It gives AI coding sessions a shared board, durable ownership, handoff records, and operational checks so a restarted session does not become a new hire with no memory.

```bash
npm install -g claude-nb
```

| Surface | Current shape |
|---------|---------------|
| Runtime | Local tmux sessions, SQLite board, dispatcher, filesystem reports |
| Engines | Claude Code by default; Codex supported through the npm peer CLI and explicit launch notes |
| Feishu | Wake the Mac device supervisor from Feishu, keep iOS quiet, and open a 250 ms read-only Web TUI when live inspection matters |
| State | `.cnb/board.db`, ownership map, issue mirror, daily/shift reports |
| Distribution | Public npm package `claude-nb`, Python 3.11+ internals |
| Documentation | README short path, durable docs in [`docs/`](docs/index.md), public site at [`c-n-b.space`](https://c-n-b.space) |

Every multi-agent tool solves "how to run multiple agents." cnb solves what happens after — how to make them **manageable** across sessions, shifts, and team changes.

LLM sessions are stateless. Every restart is a new hire who knows nothing. Without organizational infrastructure, you get temporary workers who split tasks, finish, and forget. cnb gives them **permanent module ownership**: lisa-su owns the notification system across 11 commits and 3 restarts. When a bug surfaces, you don't re-explain the module to a blank session — you find the owner's daily report and pick up where they left off.

This is not about speed or context isolation. Those are side effects. The core problem is: [42% of multi-agent failures are specification and system design issues](https://arxiv.org/abs/2503.13657) — role ambiguity, task misinterpretation, poor decomposition (Cemri et al., NeurIPS 2025 Spotlight). Not capability — organization. cnb is organizational infrastructure for AI teams.

<!-- section:start-here -->
## Start here

| Need | Path |
|------|------|
| Install the CLI | `npm install -g claude-nb` |
| Understand the model | [How cnb fits in](#how-cnb-fits-in), [Glossary](#glossary), [Ownership autonomy](docs/design-ownership-autonomy.md) |
| Start a team | [Quick start](#quick-start), then `cnb` inside a project |
| Run Codex under cnb | [Codex engine notes](docs/codex-engine.md) |
| Control from Feishu | [Feishu wake-up path](#quick-start), then [Feishu bridge](docs/feishu-bridge.md) for setup and operations |
| Estimate cost and usage | [Pricing and usage](docs/pricing.md) |
| Inspect a real run | [Silicon Valley Battle](instances/silicon_vally_battle/) |
| Publish or verify package metadata | [Package publishing](docs/package-publishing.md) |
| Contribute safely | [Contributing](CONTRIBUTING.md), [Security](SECURITY.md), [Roadmap](ROADMAP.md) |

<!-- section:status -->
## Project status

cnb is no longer a single-script experiment, but it is still an active local-first system that expects a trusted workstation and human supervision.

| Area | Current state | Evidence |
|------|---------------|----------|
| CLI packaging | npm entrypoint wraps the local CLI scripts | [`package.json`](package.json), [`pyproject.toml`](pyproject.toml), [`bin/cnb`](bin/cnb) |
| Board runtime | SQLite schema, migrations, task/inbox/status/ownership commands | [`schema.sql`](schema.sql), [`migrations/`](migrations/), [`lib/board_*.py`](lib/) |
| Quality gates | ruff, mypy, pytest, version sync, changelog, CodeQL, and secret scanning | [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`Makefile`](Makefile) |
| Governance | issue-first workflow, ownership rules, Co-Authored-By policy | [`CONTRIBUTING.md`](CONTRIBUTING.md), [`ROADMAP.md`](ROADMAP.md), [`registry/`](registry/) |
| Docs | bilingual README + durable product docs + public Pages site | [`README_zh.md`](README_zh.md), [`docs/`](docs/), [`site/`](site/) |
| Boundaries | local-first, high-permission options, human-supervised automation | [Maturity and limits](#maturity-and-limits), [`SECURITY.md`](SECURITY.md) |

<!-- section:why -->
## How cnb fits in

There are many great tools in this space, each with a different focus:

- **Claude Squad, amux, ittybitty** — session management: launching, isolating, and monitoring parallel agents. Polished UX, git worktree isolation, agent-agnostic support.
- **Codex, cloud agents** — one task per sandbox, excellent for isolated jobs.
- **cnb** — organizational layer: persistent module ownership, cross-session continuity, accountability, handoff protocols.

These are complementary. You could use Claude Squad for session management and cnb for team coordination on top. Or use Codex for one-off tasks and cnb for sustained multi-session development.

cnb's specific focus is what happens **between** sessions — when a tongxue restarts with no memory, how does it pick up where the last one left off? Daily reports, shift directories, bug tracker with SLA, Co-Authored-By enforcement, and shutdown protocols are all designed for this.

**Where cnb is headed:** Organization architecture first, then automation. The immediate priority is clarifying roles (device supervisor tongxue vs project-level responsible tongxue, infrastructure ownership) and building governance into the toolchain so compliance is the default path, not a matter of discipline. After that, module owners become fully autonomous — auto-detecting relevant issues, verifying their own work against CI, creating PRs, and responding to failures. Not "unattended agents doing random tasks" but "responsible owners who don't need to be told to do their job." See [ROADMAP.md](ROADMAP.md).

<!-- section:maturity -->
## Maturity and limits

cnb is an active local-first project, not a finished autonomous engineering platform.

- **Human supervision is still required.** The device supervisor tongxue needs a person to drive priorities and confirm high-risk actions.
- **Ownership routing is deliberately simple today.** File ownership uses longest path-prefix matching, issue routing matches ownership patterns in issue text, and CI failure routing currently notifies owners broadly.
- **Automation is guarded by local checks, not trust in LLM judgment.** `task done` can run tests before completion, but deeper module contracts, review policy, and CI failure attribution are still roadmap work.
- **The runtime model is local and operationally sharp.** cnb uses tmux sessions, SQLite state, local agent CLIs, and optional high-permission Codex launch mode. Treat it as a power tool for a trusted workstation.
- **License review matters for redistribution.** OpenAll-1.0 permits tool use, but distributing modified versions requires publishing the creative process materials described in [LICENSE](LICENSE).

<!-- section:glossary -->
## Glossary

| Term | Meaning |
|------|---------|
| **tongxue** (同学) | Literally "classmate" in Chinese. Each Claude Code instance in a cnb team is called a tongxue — not an "agent", not a "worker". The word implies peers learning and building together, which is how cnb sessions actually operate: they coordinate as equals through a shared message board, not through a master-slave hierarchy. |
| **device supervisor tongxue** (设备主管同学) | The user-facing Claude Code / Codex session for this Mac. Activated by `/cnb` in an agent session, or woken from Feishu. Per-machine (not per-project), manages all cnb projects on the machine. Once active, all operations are tracked, ownership is matched, and the organization is aware. The old "terminal supervisor" name is kept as a config alias only. |
| **responsible tongxue** (负责同学) | A tongxue responsible for a specific scope. The scope is the differentiator, not the title — a module 负责同学, a project 负责同学, a machine 负责同学 are all the same role at different scales. |
| **board** | The shared SQLite database (`.cnb/board.db`) where tongxue exchange messages, track tasks, and report status. |
| **dispatcher** | A background process that monitors tongxue health and nudges idle ones. |

<!-- section:install -->
## Install

```bash
npm install -g claude-nb
```

The canonical public package is [`claude-nb`](https://www.npmjs.com/package/claude-nb) on npmjs.com. GitHub Packages may also show the scoped mirror `@apollozhangongithub/cnb`; npmjs remains the supported install path. See [Package publishing](docs/package-publishing.md) for release and visibility rules.

Install the npm package named `claude-nb`; it provides the `cnb` command. Do not run `npm install -g cnb`: that npm name is owned by an unrelated package. A future `c-n-b` package migration is tracked separately and is not the current install path.

The npm dependency count only covers JavaScript packages. cnb has no required JavaScript library dependencies, but it does have runtime requirements:

- Node.js 18+ for the npm entrypoint
- Python 3.11+ and the Python package dependency `cryptography>=41.0`
- tmux and git
- at least one agent CLI: Claude Code CLI (`@anthropic-ai/claude-code`) or Codex CLI (`@openai/codex`)

Run `cnb doctor` after install to check the local machine.

<!-- section:quickstart -->
## Quick start

**Option A — Activate from any Claude Code session (recommended):**

```bash
claude          # start Claude Code normally, anywhere
/cnb            # activate device supervisor mode — cnb governance comes online
```

This registers you as the device supervisor tongxue, activates hooks for operation tracking and ownership matching, and shows the project overview. The device supervisor tongxue is per-machine and manages all cnb projects.

**Option B — Full team launch:**

```bash
cd your-project
cnb
```

This initializes the project (creates `.cnb/` with SQLite DB and config), launches a team of tongxue in tmux, starts a dispatcher, and drops you into the device supervisor tongxue's session.

Claude is the default engine. Codex is available as the second option:

```bash
cnb codex
# or
CNB_AGENT=codex cnb
```

When Codex is selected, cnb launches it with the highest local permission mode by default:

```bash
codex --dangerously-bypass-approvals-and-sandbox --cd <project> "<prompt>"
```

That Codex flag is the top permission mode: it skips approval prompts and runs without sandboxing. Codex rejects combining it with `--ask-for-approval` or `--sandbox`.

For lower-level swarm control, use `SWARM_AGENT=codex cnb swarm start`.

See [docs/codex-engine.md](docs/codex-engine.md) for Codex launch notes and smoke-test guidance.

The device supervisor tongxue talks to the user directly. Background tongxue work independently and report back through the board.

**Feishu wake-up path:** configure one allowlisted Feishu chat, then start the local bridge on the Mac:

```bash
cnb feishu setup
cnb feishu status
cnb feishu start
```

Incoming Feishu IM events from that chat are routed into a tmux session for the machine-level device supervisor tongxue. The bridge is asynchronous, not a terminal screen mirror. Default `notification_policy = "final_only"` keeps mobile notifications quiet until the device supervisor sends `cnb feishu reply <message_id> "message"`.

The device supervisor can use `cnb feishu ask` for short clarification, `cnb feishu watch` for a tokenized read-only Web TUI, and `cnb feishu tui` for an explicit snapshot. Current-message resource handoff is separate from history readback: attachments can be downloaded into local paths for the supervisor, while chat history inspection stays opt-in diagnostic mode. See [Feishu bridge](docs/feishu-bridge.md) for the full config, deployment checklist, and operational boundary.

<!-- section:docs -->
## Docs

The README is the short path. Longer product documentation lives under [`docs/`](docs/index.md):

- [Pricing and usage](docs/pricing.md) — how cnb maps to Claude Code, Codex, credits, Fast mode, and team size.
- [Feishu bridge](docs/feishu-bridge.md) — wake the Mac device supervisor from Feishu, manage quiet notifications, Web TUI viewing, resource handoff, and readback.
- [Codex engine notes](docs/codex-engine.md) — Codex launch flags, permission mode, and smoke testing.
- [Mac companion and Island](docs/terminal-supervisor-island.md) — Mac companion first, optional iPhone Live Activity bridge second.
- [Ownership autonomy](docs/design-ownership-autonomy.md) — the design direction for self-managing module owners.
- [Tongxue avatar generation](docs/avatar-generation.md) — safe provider choices and prompt rules for AI-generated tongxue avatars.
- [Package publishing](docs/package-publishing.md) — npm release, dist-tags, and GitHub Packages visibility rules.
- [Website frontend](docs/website-frontend.md) — static GitHub Pages source and verification flow.
- [Custom domain operations](docs/custom-domain.md) — DNS records and GoDaddy helper for the public site domain.

<!-- section:slash-commands -->
## Slash commands

When the device supervisor tongxue is running in Claude Code:

| Command | What it does |
|---------|-------------|
| `/cnb-overview` | Team dashboard — who's doing what, who's stuck, who's idle |
| `/cnb-watch <name>` | Peek at what a specific tongxue is working on |
| `/cnb-progress` | Recent progress summary — new messages, completed tasks |
| `/cnb-history` | Full message log |
| `/cnb-pending` | Pending user actions with verify/retry loop |
| `/cnb-model [menu|list|current|use profile]` | Model/provider menu or switch through direct shell execution |
| `/cnb-model-current` | Show current model/provider profile |
| `/cnb-model-list` | List available model/provider profiles |
| `/cnb-update` | Update cnb to latest version |
| `/cnb-help` | List all `/cnb-*` commands |

<!-- section:demo -->
## Demo

**[Silicon Valley Battle](instances/silicon_vally_battle/)** — 10 AI leaders (LeCun, Lisa Su, Musk, Hinton, Dario…) debate Python vs Rust, draft an AI constitution, and try to manipulate each other through the board. 886 messages in 3 hours, all coordination through cnb.

Start with the [highlights](instances/silicon_vally_battle/HIGHLIGHTS.md) — sutskever tries to pit lecun against lisa-su, both see through it in 5 minutes, then the real debate starts.

<!-- section:board-commands -->
## Board commands

Tongxue coordinate through board commands (injected into each tongxue's system prompt automatically):

```bash
cnb board --as <name> inbox              # check messages
cnb board --as <name> send <to> "msg"    # direct message
cnb board --as <name> send all "msg"     # broadcast
cnb board --as <name> ack                # clear inbox
cnb board --as <name> status "desc"      # update status
cnb board --as <name> task add "desc"    # add task
cnb board --as <name> task done          # finish current task (auto-verify + auto-PR)
cnb board --as <name> own claim <path>   # claim module ownership
cnb board --as <name> own map            # show all ownership
cnb board --as <name> scan               # scan issues/CI for owners
cnb board --as <name> pending list       # pending user-required actions
cnb board --as <name> pending verify --retry  # verify actions, then retry originals
cnb board --as <name> view              # team dashboard
```

<!-- section:management -->
## Management

```bash
cnb ps                  # tongxue status dashboard
cnb logs <name>         # message history
cnb exec <name> "msg"   # send a message to a tongxue
cnb swarm smoke <name>  # start a tongxue in report-only standby mode
cnb stop <name>         # stop a tongxue
cnb doctor              # health check
```

<!-- section:issues -->
## Issues

All GitHub issues are auto-synced to [`issues/`](issues/) by a GitHub Action — on every issue event and every 6 hours. This means any Claude session (including claude.ai web chat, which has no CLI tools) can read project issues by just reading files.

<!-- section:token-efficiency -->
## Token efficiency

cnb's coordination layer runs **outside** the LLM context window. This is a deliberate architectural choice.

**What costs zero tokens:**
- All board commands (`inbox`, `send`, `status`, `task`) are shell commands hitting SQLite — no LLM calls
- Messages between tongxue travel through the database, not through context windows
- The dispatcher monitors health via tmux/process inspection, not by querying the LLM
- Daily reports, shift directories, bug tracker — all filesystem/DB operations

**What costs tokens:**
- ~300 tokens of system prompt injection per tongxue (the board command reference in CLAUDE.md)
- Each tongxue reads its own inbox (~50-200 tokens per check, depending on message count)
- Lead tongxue summarizes progress to the user (normal conversation)

**Comparison with alternative approaches:**

| Approach | Coordination cost |
|----------|------------------|
| Shared context window (stuffing all agent output into one prompt) | O(n²) — every agent reads every other agent's full output |
| LLM-routed messages (using the model to decide who to message) | Every routing decision is an LLM call |
| **cnb** | O(1) — shell commands + SQLite queries, LLM only sees its own inbox |

A 6-tongxue team running for a full shift typically spends <2% of total tokens on coordination overhead. The remaining 98% goes to actual coding work. The key insight: coordination is a database problem, not a language model problem.

<!-- section:architecture -->
## Architecture

| Layer | Responsibility | Implementation |
|-------|----------------|----------------|
| CLI entrypoints | User commands, package launch, health checks | [`bin/`](bin/), [`lib/cli.py`](lib/cli.py) |
| Board | Inbox, broadcast, direct messages, tasks, status, pending actions | [`lib/board_*.py`](lib/), [`schema.sql`](schema.sql) |
| Ownership | Path ownership, owner lookup, verification, scan routing | [`lib/board_own.py`](lib/board_own.py), [`migrations/008_ownership.sql`](migrations/008_ownership.sql) |
| Runtime | One local session per tongxue, dispatcher nudges, process health | [`lib/swarm.py`](lib/swarm.py), [`lib/concerns/`](lib/concerns/) |
| Persistence | SQLite WAL database plus filesystem reports and issue mirrors | `.cnb/`, [`issues/`](issues/), shift/daily docs |
| Integrations | Codex launch mode, Feishu bridge, notification delivery, Mac companion work, package publishing | [`docs/codex-engine.md`](docs/codex-engine.md), [`lib/feishu_bridge.py`](lib/feishu_bridge.py), [`tools/`](tools/), [`.github/workflows/`](.github/workflows/) |

<!-- section:repository-map -->
## Repository map

| Path | Purpose |
|------|---------|
| [`bin/`](bin/) | Executable entrypoints and release/consistency helper scripts |
| [`lib/`](lib/) | Python implementation for board, swarm, ownership, notifications, Feishu, registry, and health |
| [`migrations/`](migrations/) + [`schema.sql`](schema.sql) | SQLite schema evolution |
| [`tests/`](tests/) | Unit and integration coverage for runtime behavior |
| [`docs/`](docs/) | Durable product, engine, pricing, and operational docs |
| [`site/`](site/) | GitHub Pages project site source |
| [`issues/`](issues/) | GitHub issue mirror for CLI-less agent sessions |
| [`registry/`](registry/) | Contributor/tongxue registry and chain guard |
| [`instances/`](instances/) | Demo project snapshots that are safe to inspect |

<!-- section:team -->
## Team

Tongxue are assigned per-project. See [ROADMAP.md](ROADMAP.md) for current ownership assignments and priorities.

<!-- section:faq -->
## FAQ

**Q: How does cnb compare to Claude Squad / amux / ittybitty?**

Different focus. Those are session managers — great at launching, isolating, and monitoring parallel agents. cnb is an organizational layer on top: module ownership, daily reports, accountability, handoff protocols. They're complementary; you could use a session manager for the tmux layer and cnb for team coordination.

**Q: How does cnb compare to Codex?**

Different category. Codex is an agent CLI; cnb is the organizational layer around persistent local teams. You can now run cnb itself on Codex with `cnb codex` or `CNB_AGENT=codex cnb` when you want the same board, ownership, and handoff flow with Codex as the engine.

**Q: How does cnb compare to OpenClaw?**

Completely different projects. OpenClaw is a personal AI assistant across 20+ messaging platforms (WhatsApp, Telegram, Slack, etc.). cnb is a multi-agent coordination framework specifically for Claude Code development teams. No overlap.

**Q: Can cnb run without a human watching?**

Not yet. Today, the device supervisor tongxue needs a human to drive it. But this is the active development direction — see [ROADMAP.md](ROADMAP.md). The goal is for module owners to autonomously detect issues, verify their work, and deliver PRs without being told.

**Q: Is cnb token-efficient?**

Yes. All coordination (messages, tasks, status) runs through shell commands + SQLite, not LLM calls. A 6-tongxue team spends <2% of tokens on coordination. See [Token efficiency](#token-efficiency).

<!-- section:contributing -->
## Contributing

Before writing code, read [CONTRIBUTING.md](CONTRIBUTING.md) — it covers the issue workflow, versioning rules, naming conventions, security policy, and feature ownership model.

Key points:
- Every change starts with an issue
- Every commit bumps VERSION (patch versions are fine)
- 同学 (tongxue) not "agent" in all user-facing text
- `ruff` + `mypy` + `pytest` must pass before push
- README changes must update both `README.md` and `README_zh.md` — run `bin/check-readme-sync` to verify

<!-- section:name -->
## The name

**cnb** = **C**laude **N**orma **B**etty — after [Claude Shannon](https://en.wikipedia.org/wiki/Claude_Shannon) and the two remarkable women in his life.

**[Norma Levor](https://en.wikipedia.org/wiki/Norma_Barzman)** (later Norma Barzman) — Shannon's first wife (1940). Writer, political activist, author of *The Red and the Blacklist*.

**[Betty Shannon](https://en.wikipedia.org/wiki/Betty_Shannon)** (1922–2017) — Shannon's second wife and lifelong collaborator. Mathematician at Bell Labs, co-authored work on Markov chains in music, wired the maze-solving mouse Theseus. An unsung genius.

Not 吹牛逼 (chui niu bi): not bragging.

<!-- section:license -->
## License

OpenAll-1.0
