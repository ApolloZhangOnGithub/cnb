<!-- README_SYNC: sections must match README_zh.md — run bin/check-readme-sync -->

[中文版](README_zh.md)

# claude-nb

**Project ownership for LLM teams.**

Every multi-agent tool solves "how to run multiple agents." cnb solves what happens after — how to make them **manageable** across sessions, shifts, and team changes.

LLM sessions are stateless. Every restart is a new hire who knows nothing. Without organizational infrastructure, you get temporary workers who split tasks, finish, and forget. cnb gives them **permanent module ownership**: lisa-su owns the notification system across 11 commits and 3 restarts. When a bug surfaces, you don't re-explain the module to a blank session — you find the owner's daily report and pick up where they left off.

This is not about speed or context isolation. Those are side effects. The core problem is: [42% of multi-agent failures are specification and system design issues](https://arxiv.org/abs/2503.13657) — role ambiguity, task misinterpretation, poor decomposition (Cemri et al., NeurIPS 2025 Spotlight). Not capability — organization. cnb is organizational infrastructure for AI teams.

<!-- section:why -->
## How cnb fits in

There are many great tools in this space, each with a different focus:

- **Claude Squad, amux, ittybitty** — session management: launching, isolating, and monitoring parallel agents. Polished UX, git worktree isolation, agent-agnostic support.
- **Codex, cloud agents** — one task per sandbox, excellent for isolated jobs.
- **cnb** — organizational layer: persistent module ownership, cross-session continuity, accountability, handoff protocols.

These are complementary. You could use Claude Squad for session management and cnb for team coordination on top. Or use Codex for one-off tasks and cnb for sustained multi-session development.

cnb's specific focus is what happens **between** sessions — when a tongxue restarts with no memory, how does it pick up where the last one left off? Daily reports, shift directories, bug tracker with SLA, Co-Authored-By enforcement, and shutdown protocols are all designed for this.

**Where cnb is headed:** Today, a module owner still needs a human to say "go check your issues" or "push your code." The goal is for owners to be fully autonomous within their domain — auto-detecting relevant issues, verifying their own work against CI, creating PRs, and responding to failures. Not "unattended agents doing random tasks" but "responsible owners who don't need to be told to do their job." See [ROADMAP.md](ROADMAP.md).

<!-- section:glossary -->
## Glossary

| Term | Meaning |
|------|---------|
| **tongxue** (同学) | Literally "classmate" in Chinese. Each Claude Code instance in a cnb team is called a tongxue — not an "agent", not a "worker". The word implies peers learning and building together, which is how cnb sessions actually operate: they coordinate as equals through a shared message board, not through a master-slave hierarchy. |
| **lead tongxue** | The tongxue whose terminal faces the user. It delegates work and relays results, but has no special privileges on the board. |
| **board** | The shared SQLite database (`.claudes/board.db`) where tongxue exchange messages, track tasks, and report status. |
| **dispatcher** | A background process that monitors tongxue health and nudges idle ones. |

<!-- section:install -->
## Install

```bash
npm install -g claude-nb
```

Requires: Python 3.11+, tmux, Claude Code CLI.

<!-- section:quickstart -->
## Quick start

```bash
cd your-project
cnb
```

This initializes the project (creates `.claudes/` with SQLite DB and config), launches a team of tongxue in tmux, starts a dispatcher, and drops you into the lead tongxue's Claude Code session.

The lead tongxue talks to the user directly. Background tongxue work independently and report back through the board.

<!-- section:slash-commands -->
## Slash commands

Inside the lead tongxue's Claude Code session:

| Command | What it does |
|---------|-------------|
| `/cnb-overview` | Team dashboard — who's doing what, who's stuck, who's idle |
| `/cnb-watch <name>` | Peek at what a specific tongxue is working on |
| `/cnb-progress` | Recent progress summary — new messages, completed tasks |
| `/cnb-history` | Full message log |
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
cnb board --as <name> view              # team dashboard
```

<!-- section:management -->
## Management

```bash
cnb ps                  # tongxue status dashboard
cnb logs <name>         # message history
cnb exec <name> "msg"   # send a message to a tongxue
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

- **SQLite (WAL mode)** — all state in `.claudes/board.db`, one DB per project
- **Board** — message bus (inbox, broadcast, direct), task queue, status tracking
- **Dispatcher** — background process that monitors health, nudges idle tongxue
- **Encrypted mailbox** — X25519 sealed-box private messaging between tongxue
- **tmux** — one session per tongxue, all local

<!-- section:team -->
## Team

| 同学 | 负责 |
|------|------|
| lead | 项目负责人、团队协调 |
| musk | 安全隔离 (#31) |
| lisa-su | 通知推送 (#33) |
| forge | 待办队列 (#34)、邮件系统 (#32)、全局管理 (#42) |
| tester | 测试加固、质量保障 |
| sutskever | 架构重构 (#26) |

<!-- section:faq -->
## FAQ

**Q: How does cnb compare to Claude Squad / amux / ittybitty?**

Different focus. Those are session managers — great at launching, isolating, and monitoring parallel agents. cnb is an organizational layer on top: module ownership, daily reports, accountability, handoff protocols. They're complementary; you could use a session manager for the tmux layer and cnb for team coordination.

**Q: How does cnb compare to Codex?**

Different category. Codex runs isolated tasks in cloud sandboxes. cnb coordinates persistent local teams across sessions. Use Codex for one-off jobs, cnb when you need continuity and ownership across restarts.

**Q: How does cnb compare to OpenClaw?**

Completely different projects. OpenClaw is a personal AI assistant across 20+ messaging platforms (WhatsApp, Telegram, Slack, etc.). cnb is a multi-agent coordination framework specifically for Claude Code development teams.

**Q: Can cnb run without a human watching?**

Not yet. Today, the lead tongxue needs a human to drive it. But this is the active development direction — see [ROADMAP.md](ROADMAP.md) Phase 2. The goal is for module owners to autonomously detect issues, verify their work, and deliver PRs without being told.

**Q: Is cnb token-efficient?**

Yes. All coordination (messages, tasks, status) runs through shell commands + SQLite, not LLM calls. A 6-tongxue team spends <2% of tokens on coordination. See [Token efficiency](#token-efficiency).

<!-- section:contributing -->
## Contributing

Before writing code, read [CONTRIBUTING.md](.github/CONTRIBUTING.md) — it covers the issue workflow, versioning rules, naming conventions, and feature ownership model.

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

Not Chui Niu Bi(吹牛逼, Bragging in Chinese).

<!-- section:license -->
## License

OpenAll-1.0
