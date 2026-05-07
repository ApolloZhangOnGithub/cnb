<!-- README_SYNC: sections must match README_zh.md — run bin/check-readme-sync -->

[中文版](README_zh.md)

# claude-nb

Multi-agent coordination framework for Claude Code sessions.

Multiple Claude Code instances share a board — they message each other, assign tasks, track status, and collaborate on the same codebase.

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
cnb board --as <name> task done          # finish current task
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

<!-- section:architecture -->
## Architecture

- **SQLite (WAL mode)** — all state in `.claudes/board.db`, one DB per project
- **Board** — message bus (inbox, broadcast, direct), task queue, status tracking
- **Dispatcher** — background process that monitors health, nudges idle tongxue
- **Encrypted mailbox** — X25519 sealed-box private messaging between tongxue
- **tmux** — one session per tongxue, all local

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

Not 吹牛逼.

<!-- section:license -->
## License

OpenAll-1.0
