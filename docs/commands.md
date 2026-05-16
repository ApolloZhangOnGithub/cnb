# Commands reference

cnb has two command surfaces: terminal CLI commands and Claude Code slash commands.

## Terminal CLI

### Project lifecycle

```bash
cnb                     # initialize project + launch team + start dispatcher watchdog
cnb codex               # same, with Codex as the agent engine
cnb doctor              # health check: verify dependencies and config
cnb ps                  # tongxue status dashboard
cnb stop <name>         # stop a tongxue
cnb logs <name>         # message history for a tongxue
cnb exec <name> "msg"   # send a message to a tongxue
```

### Swarm control

```bash
cnb swarm start         # launch the full team + ensure dispatcher watchdog is running
cnb swarm smoke <name>  # start a tongxue in report-only standby
```

### Board commands

Tongxue coordinate through the board. These commands are injected into each tongxue's system prompt automatically.

#### Messaging

```bash
cnb board --as <name> inbox                    # check unread messages
cnb board --as <name> send <to> "msg"          # direct message
cnb board --as <name> send all "msg"           # broadcast to all
cnb board --as <name> ack                      # clear inbox
```

#### Status and tasks

```bash
cnb board --as <name> status "desc"            # update current status
cnb board --as <name> task add "desc"          # add a task
cnb board --as <name> task done                # finish current task (auto-verify + auto-PR)
cnb board --as <name> task done --skip-verify  # skip test verification
cnb board --as <name> view                     # team dashboard
cnb board --as <name> progress                 # paste-friendly progress snapshot
```

Use `view` for a compact team dashboard. Use `progress` when you need a
board-wide work snapshot for a lead update or handoff: it summarizes active and
pending tasks, open bugs, pending user actions, unread inbox counts, and each
session's current status.

#### Ownership

```bash
cnb board --as <name> own claim <path>         # claim ownership of a path/module
cnb board --as <name> own list                 # list your ownership
cnb board --as <name> own disown <path>        # release ownership
cnb board --as <name> own map                  # show all ownership
cnb board --as <name> scan                     # scan issues/CI, route to owners
```

#### Bug tracking

```bash
cnb board --as <name> bug report P1 "desc"     # report a bug with severity
```

#### Pending actions

```bash
cnb board --as <name> pending list             # list pending user-required actions
cnb board --as <name> pending verify --retry   # verify actions, then retry originals
```

#### Inspection (read-only)

```bash
cnb board --as lead inspect inbox <name>       # read another's inbox without side effects
cnb board --as lead inspect tasks <name>       # read another's task queue
```

### Feishu bridge

```bash
cnb feishu setup                # guided Feishu configuration
cnb feishu status               # connection status
cnb feishu start                # start the bridge
cnb feishu reply <msg_id> "msg" # reply to a Feishu message
cnb feishu ask                  # quick clarification via Feishu
cnb feishu watch                # tokenized read-only Web TUI
cnb feishu tui                  # explicit snapshot
```

### Model management

```bash
cnb m                   # interactive model/provider menu
cnb m list              # list available profiles
cnb m current           # show active profile
cnb m use <profile>     # switch provider
```

## Slash commands

Type `/` in a Claude Code session. cnb commands have two tiers:

| Tier | Audience | Style |
|------|----------|-------|
| `cnb-*` | Human → Claude | Natural language, conversational |
| `cnbx-*` | Claude → program | CLI pass-through, raw output |

### User-facing commands

| Command | Purpose |
|---------|---------|
| `/cnb` | Full health check — team status + pending + system health |
| `/cnb-status` | Team overview — who's doing what |
| `/cnb-watch <name>` | Focus on one tongxue |
| `/cnb-progress` | Recent progress summary from inbox and board state |
| `/cnb-pending` | Actions needing user attention |
| `/cnb-history` | Message history |
| `/cnb-supervisor` | Device supervisor runtime status |
| `/cnb-model` | Model management (view/list/switch) |
| `/cnb-config` | Quick config (effort, permissions) |
| `/cnb-update` | Update cnb |
| `/cnb-help` | Auto-scan and list all commands |

### Programmatic commands

| Command | Purpose |
|---------|---------|
| `/cnbx-board <args>` | Pass-through to `board` CLI |
| `/cnbx-model <args>` | Pass-through to `cnb m` CLI |
| `/cnbx-supervisor` | Raw supervisor diagnostics |
| `/cnbx-settings <args>` | Edit settings.json |
| `/cnbx-update` | Raw update command |
