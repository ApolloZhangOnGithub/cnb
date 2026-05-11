# 技能

[English](Skills)

CNB 的技能生态系统。

## 技能类型

| 类型 | 标签 | 安装方式 | 例子 |
|------|------|---------|------|
| CNB 内置 | `[内置]` | 随 cnb 自带 | `/cnb-status`, `/cnb-model` |
| 飞书 (Lark) | `[需安装]` | `npm install -g @lark-ai/lark-cli` | `lark-base`, `lark-im` |
| Claude Code 内置 | `[内置]` | Claude Code 自带 | `/init`, `/review` |
| 源码工具 | `[源码]` | clone repo | B站下载器、字幕提取 |

## 查看可用技能

在 Claude Code 中输入 `/cnb-skills`，会列出所有已注册技能，按分类展示，标注安装状态。

## 注册新技能

编辑 `registry/skills.yaml`，添加条目：

```yaml
- name: my-skill
  display: 我的技能
  category: dev           # cnb | lark | media | dev | infra | builtin
  repo: https://github.com/xxx/yyy
  desc: 一句话描述
  cmds:
    - /my-skill
```

**分类：**
- `cnb` — CNB 核心功能
- `lark` — 飞书集成
- `media` — 媒体处理
- `dev` — 开发工具
- `infra` — 基础设施
- `builtin` — Claude Code 自带

## 开发自定义命令

自定义命令放在 `commands/` 目录：

```
commands/
  my-command.md    →  /my-command
  cnbx-my-tool.md  →  /cnbx-my-tool  (程序层)
```

### 文件格式

```markdown
---
allowed-tools: Bash(...)        # 允许的工具
description: 一句话描述          # 显示在 /cnb-help
argument-hint: "<参数>"         # 可选
---

这里写给 Claude 的指令。可以是自然语言，也可以用 `!` 前缀跑 shell 命令。
```

### 用户层 vs 程序层

- **`cnb-*.md`**: 给 Claude 读的自然语言 prompt。描述领域知识 + 判断逻辑。
- **`cnbx-*.md`**: 纯 `!` CLI 透传。一行命令，无判断。

用户层命令调用程序层命令：`/cnb-status` → 调用 `/cnbx-board overview` + `/cnbx-board --as bezos inbox`

### 模板变量

命令文件中的 `${ME}` 会在安装时替换为当前 session 名称：

```markdown
allowed-tools: Bash(board --as ${ME} inbox)
```

安装到 `.claude/commands/` 后变为 `Bash(board --as bezos inbox)`。
