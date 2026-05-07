# claude-nb

Multi-agent coordination framework for Claude Code sessions.

Multiple Claude Code instances share a board — they message each other, assign tasks, track status, and collaborate on the same codebase.

## Install

```bash
npm install -g claude-nb
```

Requires: Python 3.11+, tmux, Claude Code CLI.

## Quick start

```bash
cd your-project
cnb
```

This initializes the project (creates `.claudes/` with SQLite DB and config), launches a team of tongxue in tmux, starts a dispatcher, and drops you into the lead tongxue's Claude Code session.

The lead tongxue talks to the user directly. Background tongxue work independently and report back through the board.

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

## Management

```bash
cnb ps                  # tongxue status dashboard
cnb logs <name>         # message history
cnb exec <name> "msg"   # send a message to a tongxue
cnb stop <name>         # stop a tongxue
cnb doctor              # health check
```

## Architecture

- **SQLite (WAL mode)** — all state in `.claudes/board.db`, one DB per project
- **Board** — message bus (inbox, broadcast, direct), task queue, status tracking
- **Dispatcher** — background process that monitors health, nudges idle tongxue
- **Encrypted mailbox** — X25519 sealed-box private messaging between tongxue
- **tmux** — one session per tongxue, all local

## Contributing

Before writing code, read [CONTRIBUTING.md](.github/CONTRIBUTING.md) — it covers the issue workflow, versioning rules, naming conventions, and feature ownership model.

Key points:
- Every change starts with an issue
- Every commit bumps VERSION (patch versions are fine)
- 同学 not "agent" in all user-facing text
- `ruff` + `mypy` + `pytest` must pass before push

## The name

**cnb** = **C**laude **N**orma **B**etty — after [Claude Shannon](https://en.wikipedia.org/wiki/Claude_Shannon) and the two remarkable women in his life.

**[Norma Levor](https://en.wikipedia.org/wiki/Norma_Barzman)** (later Norma Barzman) — Shannon's first wife (1940). Writer, political activist, author of *The Red and the Blacklist*.

**[Betty Shannon](https://en.wikipedia.org/wiki/Betty_Shannon)** (1922–2017) — Shannon's second wife and lifelong collaborator. Mathematician at Bell Labs, co-authored work on Markov chains in music, wired the maze-solving mouse Theseus. An unsung genius.

Not 吹牛逼.

## License

OpenAll-1.0
