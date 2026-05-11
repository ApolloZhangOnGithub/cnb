# 命令

[English](Commands)

CNB 有两种"命令"形式，长得像但本质不同。

## 快速区分

| | `/` 斜杠命令 | 终端 `cnb` 命令 |
|---|---|---|
| **在哪里输入** | Claude Code 对话里 | 终端 (Terminal) |
| **谁执行** | Claude (AI) 理解意图后执行 | Shell 直接运行 |
| **语法** | 自然语言，人怎么说就怎么打 | 严格的 CLI 语法 |
| **例子** | `/cnb-status`、`/cnb-model 切ds` | `cnb start`、`board --as bezos send` |
| **本质** | Prompt snippet，告诉 Claude 做什么 | Bash/Python 程序 |

## 斜杠命令 (`/cnb-*`)

你在 Claude Code 里输入 `/cnb-status`，Claude 读入一段 prompt（来自 `.claude/commands/cnb-status.md`），理解你的意图，然后调用底层工具去执行。

**不需要记参数** — 你可以说：
- `/cnb-status` — 看团队状态
- `/cnb-model 切ds` — 切换模型
- `/cnb-watch musk` — 看 musk 在干嘛
- `/cnb` — 全局体检

## 终端命令 (`cnb`)

在终端里跑的程序。用于启动 session、管理 board、发送消息等。

```bash
cnb start                              # 启动团队 sessions
cnb help                               # 查看帮助
board --as bezos send musk "hello"     # 发消息
```

## 两层架构

斜杠命令分两层：

| 层 | 调用方式 | 特点 |
|---|---------|------|
| **cnb-*** | `/cnb-status` | 自然语言 domain prompt，人用的 |
| **cnbx-*** | `/cnbx-board overview` | 纯 CLI 透传，Claude 内部调用 |

`cnb-*` 命令是给**人**读的 prompt，描述一个领域（模型管理、团队状态、配置）和 Claude 该怎么处理。Claude 理解后，调用 `cnbx-*` 命令去执行具体的 CLI 操作。

### 为什么分两层？

- **人 → Claude**：需要上下文、需要判断、需要灵活理解。`/cnb-status` 知道什么时候该看 overview，什么时候该看 inbox
- **Claude → 程序**：需要精确、可组合。`/cnbx-board overview` 永远只跑一个 board 命令，不掺杂解释

### 命令列表

运行 `/cnb-help` 查看当前所有可用命令（自动扫描）。

## 添加新命令

1. 在 `commands/` 目录创建 `.md` 文件
2. 写 frontmatter (`allowed-tools`, `description`)
3. `cnb` 启动时自动安装到 `.claude/commands/`

详见[技能](Skills‐zh)页面。
