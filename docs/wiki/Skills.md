# Skills

[中文版](Skills‐zh)

The CNB skill ecosystem.

## Skill Types

| Type | Tag | Install | Examples |
|------|-----|---------|----------|
| CNB built-in | `[built-in]` | Shipped with cnb | `/cnb-status`, `/cnb-model` |
| Lark (Feishu) | `[install]` | `npm install -g @lark-ai/lark-cli` | `lark-base`, `lark-im` |
| Claude Code built-in | `[built-in]` | Shipped with Claude Code | `/init`, `/review` |
| Source tools | `[source]` | Clone repo | Video downloader, subtitle extraction |

## Browse Available Skills

Type `/cnb-skills` in Claude Code to list all registered skills, grouped by category with install status.

## Register a New Skill

Edit `registry/skills.yaml` and add an entry:

```yaml
- name: my-skill
  display: My Skill
  category: dev           # cnb | lark | media | dev | infra | builtin
  repo: https://github.com/xxx/yyy
  desc: One-line description
  cmds:
    - /my-skill
```

**Categories:**
- `cnb` — CNB core functionality
- `lark` — Feishu/Lark integration
- `media` — Media processing
- `dev` — Development tools
- `infra` — Infrastructure
- `builtin` — Claude Code built-in

## Developing Custom Commands

Custom commands live in the `commands/` directory:

```
commands/
  my-command.md    →  /my-command
  cnbx-my-tool.md  →  /cnbx-my-tool  (program layer)
```

### File Format

```markdown
---
allowed-tools: Bash(...)        # Permitted tools
description: One-line summary   # Shown in /cnb-help
argument-hint: "<args>"         # Optional
---

Instructions for Claude. Can be natural language or `!`-prefixed shell commands.
```

### User Layer vs Program Layer

- **`cnb-*.md`**: Natural language prompts for Claude. Describe domain knowledge + judgment logic.
- **`cnbx-*.md`**: Pure `!` CLI pass-through. One command, no interpretation.

User layer calls program layer: `/cnb-status` → calls `/cnbx-board overview` + `/cnbx-board --as bezos inbox`

### Template Variables

`${ME}` in command files is replaced with the current session name at install time:

```markdown
allowed-tools: Bash(board --as ${ME} inbox)
```

After installation to `.claude/commands/`, becomes `Bash(board --as bezos inbox)`.
