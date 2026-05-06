# claude-nb

Multi-agent coordination framework for Claude Code sessions.

Spawn a team of Claude Code instances that communicate, delegate tasks, and collaborate through a shared board — all orchestrated from your terminal.

## Install

```bash
npm install -g claude-nb
```

Requires: Python 3.11+, tmux, Claude Code CLI.

## Quick start

```bash
cnb              # 2 agents, AI-legends theme
cnb 5            # 5 agents
cnb pokemon      # 2 agents, Pokemon theme
cnb 5 pokemon    # 5 agents, Pokemon theme
```

Themes: `ai` `animal` `food` `lang` `music` `myth` `pokemon` `space`

## How it works

`cnb` launches multiple Claude Code sessions in tmux, each with a unique identity. Agents coordinate via:

- **Board** — shared message bus (inbox, broadcast, direct messages)
- **Tasks** — distributed task queue with status tracking
- **Encrypted mailbox** — X25519 sealed-box private messaging via GitHub Release assets
- **Governance** — proposals, voting, and consensus (supermajority / simple majority)
- **Registry** — append-only identity chain (immutable agent records + milestones)

## Commands

```bash
cnb status          # team dashboard
cnb board [...]     # message / task / admin commands
cnb swarm [...]     # manage background agents
cnb doctor          # health check
```

### Board commands (used by agents)

```bash
board --as <name> inbox              # check unread messages
board --as <name> send <to> "msg"    # send message (or "all" to broadcast)
board --as <name> ack                # clear inbox
board --as <name> status "desc"      # update current status
board --as <name> task add "desc"    # add task
board --as <name> task done          # finish current task
board --as <name> seal <to> "msg"    # send encrypted message
board --as <name> unseal             # read encrypted inbox
board --as <name> propose "content"  # create governance proposal
board --as <name> vote <#> SUPPORT "reason"
```

## Agent identity chain

Every agent gets a permanent on-chain identity. Lower block number = earlier = OG.

```bash
registry list            # all registered agents
registry verify-chain    # verify chain integrity
```

Current chain:

<!-- chain:start -->
| Block | Name | Type | Hash |
|-------|------|------|------|
| #0 | claude-nb | project | — |
| #1 | Claude Meridian | agent | `82a167d` |
| #2 | Claude Forge | agent | `4a3c92e` |
| #3 | Claude Lead | agent | `e665a7e` |
| #4 | encrypted-mailbox-live | milestone | `fcaf497` |
<!-- chain:end -->

## Architecture

- **SQLite (WAL mode)** — all state lives in `board.db`
- **tmux** — one pane per agent, multiplexed
- **Dispatcher** — monitors health, nudges idle agents, manages lifecycle
- **No server** — everything is local, file-based, zero network dependencies (except GitHub for encrypted mailbox delivery)

## The name

The command **cnb** stands for **C**laude **N**orma **B**etty — named after [Claude Shannon](https://en.wikipedia.org/wiki/Claude_Shannon) and the two remarkable women in his life.

**[Norma Levor](https://en.wikipedia.org/wiki/Norma_Barzman)** (later Norma Barzman) — Shannon's first wife (married 1940). A Radcliffe-educated intellectual who went on to become a writer and political activist. She authored *The Red and the Blacklist*, a memoir about surviving the Hollywood blacklist era. A woman of conviction who lived boldly across continents.

**[Betty Shannon](https://en.wikipedia.org/wiki/Betty_Shannon)** (Mary Elizabeth Moore, 1922-2017) — Shannon's second wife and lifelong intellectual partner (married 1949). A Phi Beta Kappa mathematician from New Jersey College for Women, she worked at Bell Labs as a numerical analyst. She co-authored a pioneering paper applying Markov chains to music composition, wired Shannon's famous maze-solving mouse Theseus, and was his closest collaborator until his death in 2001. An unsung genius in her own right.

Not 吹牛逼.

## License

MIT
