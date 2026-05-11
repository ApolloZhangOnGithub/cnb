# Commands

[中文版](Commands‐zh)

CNB has two kinds of "commands" that look similar but work differently.

## Quick Reference

| | `/` Slash commands | Terminal `cnb` commands |
|---|---|---|
| **Where** | Inside a Claude Code conversation | In Terminal |
| **Who runs it** | Claude (AI) interprets intent, then executes | Shell runs it directly |
| **Syntax** | Natural language — say it however you want | Strict CLI syntax |
| **Examples** | `/cnb-status`, `/cnb-model switch to ds` | `cnb start`, `board --as bezos send` |
| **Essence** | Prompt snippet — tells Claude what to do | Bash/Python program |

## Slash Commands (`/cnb-*`)

When you type `/cnb-status` in Claude Code, Claude loads a prompt (from `.claude/commands/cnb-status.md`), understands your intent, then calls the underlying tools to execute.

**No need to memorize arguments** — just say it naturally:
- `/cnb-status` — team status
- `/cnb-model switch to deepseek` — switch model
- `/cnb-watch musk` — check what musk is doing
- `/cnb` — full health check

## Terminal Commands (`cnb`)

Programs that run in the terminal. Used for starting sessions, managing the board, sending messages, etc.

```bash
cnb start                              # launch team sessions
cnb help                               # show help
board --as bezos send musk "hello"     # send a message
```

## Two-Tier Architecture

Slash commands are split into two layers:

| Layer | Invocation | Purpose |
|-------|-----------|---------|
| **cnb-*** | `/cnb-status` | Natural language domain prompt — for humans |
| **cnbx-*** | `/cnbx-board overview` | Pure CLI pass-through — for Claude's internal use |

`cnb-*` commands are prompts written **for humans**. They describe a domain (model management, team status, config) and how Claude should handle requests. After understanding intent, Claude calls `cnbx-*` commands for the actual CLI operations.

### Why two layers?

- **Human → Claude**: needs context, judgment, flexible interpretation. `/cnb-status` knows when to show the overview vs the inbox.
- **Claude → Program**: needs precision, composability. `/cnbx-board overview` always runs exactly one board command, no interpretation.

### Command List

Run `/cnb-help` to see all available commands (auto-scanned).

## Adding New Commands

1. Create a `.md` file in the `commands/` directory
2. Write frontmatter (`allowed-tools`, `description`)
3. Commands are auto-installed to `.claude/commands/` on `cnb` startup

See the [Skills](Skills) page for details.
