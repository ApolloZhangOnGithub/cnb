# claude-nb

Multi-agent coordination framework for Claude Code sessions.

Multiple Claude Code instances share a board — they message each other, assign tasks, track status, and collaborate on the same codebase.

## Install

```bash
npm install -g claude-nb
```

Requires: Python 3.11+, tmux, Claude Code CLI.

## Usage

### 1. Add to an existing Claude Code project (recommended)

The most common way to use cnb: add it to your project's CLAUDE.md so that Claude Code sessions can coordinate with each other.

**Step 1** — Initialize your project:

```bash
cd your-project
cnb init alice bob charlie    # register agent names
```

This creates a `.claudes/` directory with `board.db` (SQLite) and `config.toml`.

**Step 2** — Add the coordination block to your CLAUDE.md (see [CLAUDE.md conventions](CLAUDE.md) for the full template). Each Claude Code session uses `board` commands to communicate:

```bash
board --as alice inbox                # check messages
board --as alice send bob "msg"       # direct message
board --as alice send all "msg"       # broadcast
board --as alice ack                  # clear inbox
board --as alice status "working on X"
board --as alice task add "desc"      # add task
board --as alice task done            # finish current task
board --as alice view                 # team dashboard
```

**Step 3** — Launch agents however you like — separate terminals, tmux panes, `claude --name alice`, etc. Each session checks inbox on startup and coordinates through the board.

### 2. Quick launch with `cnb`

Spin up a full team in one command — launches tmux sessions, starts a dispatcher, and drops you into the lead agent's Claude Code:

```bash
cnb
```

The lead agent talks to the user; background agents work independently and report back via the board.

## Slash commands

Once a team is running, the lead agent (and the user) can use these commands inside Claude Code:

| Command | What it does |
|---------|-------------|
| `/cnb-overview` | Team dashboard — who's doing what, who's stuck, who's idle |
| `/cnb-watch <name>` | Peek at what a specific agent is working on |
| `/cnb-progress` | Recent progress summary — new messages, completed tasks |
| `/cnb-history` | Full message log |
| `/cnb-update` | Update cnb to latest version |
| `/cnb-help` | List all `/cnb-*` commands |

These are auto-generated into `.claude/commands/` on launch so they work as native Claude Code slash commands.

## Architecture

- **SQLite (WAL mode)** — all state in `.claudes/board.db`, one DB per project
- **Board** — message bus (inbox, broadcast, direct), task queue, status tracking
- **Dispatcher** — background process that monitors health, nudges idle agents, announces time
- **Encrypted mailbox** — X25519 sealed-box private messaging between agents
- **tmux** — one session per agent

Everything is local. No server, no network dependencies.

## The name

**cnb** = **C**laude **N**orma **B**etty — after [Claude Shannon](https://en.wikipedia.org/wiki/Claude_Shannon) and the two remarkable women in his life.

**[Norma Levor](https://en.wikipedia.org/wiki/Norma_Barzman)** (later Norma Barzman) — Shannon's first wife (1940). Writer, political activist, author of *The Red and the Blacklist*.

**[Betty Shannon](https://en.wikipedia.org/wiki/Betty_Shannon)** (1922–2017) — Shannon's second wife and lifelong collaborator. Mathematician at Bell Labs, co-authored work on Markov chains in music, wired the maze-solving mouse Theseus. An unsung genius.

Not 吹牛逼.

## License

MIT
