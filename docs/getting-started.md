# Getting started

## Install

```bash
npm install -g claude-nb
```

This installs the `cnb` command. The npm package is named `claude-nb` (not `cnb` — that name belongs to an unrelated package).

### Requirements

- Node.js 18+
- Python 3.11+ with `cryptography>=41.0`
- tmux and git
- At least one agent CLI: [Claude Code](https://claude.ai/code) or [Codex](https://github.com/openai/codex)

Verify your setup:

```bash
cnb doctor
```

## Quick start

### Option A: Activate in an existing Claude Code session

```bash
claude          # start Claude Code normally
/cnb            # activate device supervisor — cnb governance comes online
```

This registers the current session as the device supervisor tongxue, activates hooks for operation tracking and ownership matching, and shows the project overview.

### Option B: Launch a full team

```bash
cd your-project
cnb
```

This initializes the project (creates `.cnb/` with SQLite DB and config), launches a team of tongxue in tmux, starts a dispatcher, and drops you into the device supervisor's session.

### Using Codex as the engine

```bash
cnb codex
# or
CNB_AGENT=codex cnb
```

See [Codex engine notes](codex-engine.md) for launch flags, `/goal` workflow, board nudges, and smoke testing.

### Connecting Feishu

```bash
cnb feishu setup    # guided configuration
cnb feishu status   # verify connection
cnb feishu start    # start the bridge
```

See [Feishu bridge](feishu-bridge.md) for full setup and operations.

## Key concepts

### Tongxue (同学)

Each Claude Code instance in a cnb team is called a tongxue — not an "agent" or "worker". The word means "classmate" in Chinese and reflects how sessions coordinate: as peers through a shared message board, not through a hierarchy.

### Device supervisor (设备主管同学)

The user-facing session for this Mac. Per-machine (not per-project), it manages all cnb projects on the machine. Activated by `/cnb` in a Claude Code session.

### Board

The shared SQLite database (`.cnb/board.db`) where tongxue exchange messages, track tasks, report status, publish progress snapshots, and manage ownership.

### Ownership

Tongxue claim ownership of code paths. When a bug surfaces or an issue arrives, cnb routes it to the owner — not to a blank session that needs re-explaining.

## What to do next

- Browse [all commands](commands.md)
- Check [pricing and usage](pricing.md) to understand costs
- Read the [demo highlights](../instances/silicon_vally_battle/HIGHLIGHTS.md) to see cnb in action

<a id="comparison"></a>
## How cnb compares

| Tool | Focus | Relationship to cnb |
|------|-------|---------------------|
| **Claude Squad, amux, ittybitty** | Session management: launching, isolating, monitoring parallel agents | Complementary — use them for session management, cnb for team coordination on top |
| **Codex, cloud agents** | One task per sandbox | Complementary — cnb can use Codex as an engine for sustained multi-session work |
| **cnb** | Organizational layer: persistent ownership, cross-session continuity, handoff | The layer between sessions |

cnb's specific focus is what happens **between** sessions — when a tongxue restarts with no memory, how does it pick up where the last one left off?
