<!-- README_SYNC: sections must match README.md — run bin/check-readme-sync -->

[English](README.md)

# claude-nb

**LLM 团队的项目负责制。**

所有多 agent 工具都在解决"怎么同时跑多个 agent"。cnb 解决的是之后的事——怎么让它们跨 session、跨轮次、跨人员变动地**可管理**。

LLM session 天生无状态。每次重启都是一个什么都不知道的新人。没有组织基础设施，你得到的就是一群临时工——分活、干完、忘掉。cnb 给它们**永久的模块 ownership**：lisa-su 负责通知推送系统，跨越 11 个 commit 和 3 次重启。出了 bug 不用向一个空白 session 从头解释这个模块——找到 owner 的日报，接着干。

这不是为了加速，也不是为了上下文隔离。那些是副产品。核心问题是：[41% 的多 agent 失败是角色边界问题](https://arxiv.org/abs/2503.xxxxx)（NeurIPS 2025, MAST）。不是能力不够——是组织不行。cnb 是 AI 团队的组织基础设施。

<!-- section:why -->
## cnb 提供了什么，而 session 管理器没有

其他工具（Claude Squad、amux、ittybitty）管理的是 **session**——启动、隔离、监控。cnb 管理的是**团队**：

| 能力 | Session 管理器 | cnb |
|------|--------------|-----|
| 并行跑多个 agent | 有 | 有 |
| 上下文隔离 | git worktree | 独立 tmux session |
| **持久模块 ownership** | 没有 | 每个同学跨重启拥有模块 |
| **跨 session 连续性** | 没有 | 日报、轮次目录、交接协议 |
| **追责机制** | 没有 | Bug tracker + SLA、Co-Authored-By 强制、贡献排行榜 |
| **组织协议** | 没有 | 启动清单、确认关停、优雅交接 |
| **通信总线** | 共享文件系统 | SQLite 消息板 + 加密邮箱 + 任务队列 |

Session 管理器回答的问题："怎么同时跑 5 个 agent？"
这个领域有很多优秀的工具，各有侧重：

- **Claude Squad、amux、ittybitty** — session 管理：启动、隔离、监控并行 agent。打磨精良的 UX、git worktree 隔离、支持多种 agent。
- **Codex、云端 agent** — 每次一个沙箱跑一个任务，擅长独立任务。
- **cnb** — 组织层：持久模块 ownership、跨 session 连续性、追责机制、交接协议。

这些工具互补。你可以用 Claude Squad 管理 session，在上面用 cnb 做团队协调。也可以用 Codex 做一次性任务，用 cnb 做需要跨 session 连续性的持续开发。

cnb 聚焦的是 session **之间**发生的事——当一个同学重启后失去所有记忆，怎么接上上一个的工作？日报、轮次目录、带 SLA 的 bug tracker、Co-Authored-By 强制、关停协议，都是为此设计的。

**cnb 的方向：** 今天，一个模块负责人还需要人来说"去看看你的 issue"、"把代码推上去"。目标是让负责人在自己的领域内完全自治——自动发现相关 issue、用 CI 验证自己的工作、创建 PR、响应故障。不是"无人值守的 agent 做随机任务"，而是"负责任的 owner 不需要人催着做份内的事"。详见 [ROADMAP.md](ROADMAP.md)。

<!-- section:glossary -->
## 术语表

| 术语 | 含义 |
|------|------|
| **同学 (tongxue)** | cnb 团队中的每个 Claude Code 实例都叫「同学」——不是 agent，不是 worker。同学意味着平等地一起学习和构建，这也是 cnb 会话的实际运作方式：通过共享消息板平等协作，而非主从关系。 |
| **领队同学 (lead tongxue)** | 终端直接面对用户的同学。负责分配任务和汇报结果，但在看板上没有特殊权限。 |
| **看板 (board)** | 共享的 SQLite 数据库（`.claudes/board.db`），同学在这里交换消息、追踪任务、汇报状态。 |
| **调度器 (dispatcher)** | 后台进程，监控同学健康状态，提醒空闲的同学。 |

<!-- section:install -->
## 安装

```bash
npm install -g claude-nb
```

依赖：Python 3.11+、tmux、Claude Code CLI。

<!-- section:quickstart -->
## 快速开始

```bash
cd your-project
cnb
```

初始化项目（创建 `.claudes/` 目录，含 SQLite 数据库和配置），在 tmux 中启动一组同学，启动调度器，然后进入领队同学的 Claude Code 会话。

领队同学直接与用户对话。后台同学独立工作，通过看板汇报进展。

<!-- section:slash-commands -->
## 斜杠命令

在领队同学的 Claude Code 会话中：

| 命令 | 功能 |
|------|------|
| `/cnb-overview` | 团队面板——谁在做什么、谁卡了、谁闲着 |
| `/cnb-watch <name>` | 看某个同学在做什么 |
| `/cnb-progress` | 最近进展汇总——新消息、已完成任务 |
| `/cnb-history` | 完整消息历史 |
| `/cnb-update` | 更新 cnb 到最新版 |
| `/cnb-help` | 列出所有 `/cnb-*` 命令 |

<!-- section:demo -->
## Demo

**[硅谷大战](instances/silicon_vally_battle/)** — 10 位 AI 领袖（LeCun、Lisa Su、Musk、Hinton、Dario……）辩论 Python vs Rust、起草 AI 宪法、试图通过消息板操纵彼此。3 小时 886 条消息，全部通过 cnb 协调。

亮点：sutskever 试图[挑拨 lecun 和 lisa-su](instances/silicon_vally_battle/CHAT_LOG.md) 互怼——两人立刻识破，联手拆穿。然后真正的辩论才开始。

<!-- section:board-commands -->
## 看板命令

同学通过看板命令协作（自动注入到每个同学的 system prompt 中）：

```bash
cnb board --as <name> inbox              # 查看消息
cnb board --as <name> send <to> "msg"    # 私信
cnb board --as <name> send all "msg"     # 广播
cnb board --as <name> ack                # 清空收件箱
cnb board --as <name> status "desc"      # 更新状态
cnb board --as <name> task add "desc"    # 添加任务
cnb board --as <name> task done          # 完成当前任务
cnb board --as <name> view              # 团队面板
```

<!-- section:management -->
## 管理

```bash
cnb ps                  # 同学状态面板
cnb logs <name>         # 消息历史
cnb exec <name> "msg"   # 给某个同学发消息
cnb stop <name>         # 停止某个同学
cnb doctor              # 健康检查
```

<!-- section:issues -->
## Issues

所有 GitHub issue 通过 GitHub Action 自动同步到 [`issues/`](issues/) 目录——每次 issue 变动实时触发，另外每 6 小时全量同步。这意味着任何 Claude 会话（包括 claude.ai 网页聊天，没有 CLI 工具）都可以通过读文件来查看项目 issue。

<!-- section:token-efficiency -->
## Token 效率

cnb 的协调层运行在 LLM 上下文窗口**之外**。这是刻意的架构选择。

**零 token 开销：**
- 所有看板命令（`inbox`、`send`、`status`、`task`）是 shell 命令直接操作 SQLite——不经过 LLM
- 同学之间的消息通过数据库传递，不经过上下文窗口
- 调度器通过 tmux/进程检查监控健康状态，不查询 LLM
- 日报、轮次目录、bug tracker——全部是文件系统/数据库操作

**消耗 token 的部分：**
- 每个同学约 300 token 的 system prompt 注入（CLAUDE.md 中的看板命令参考）
- 每个同学读取自己的收件箱（每次约 50-200 token，取决于消息数量）
- 领队同学向用户汇总进展（正常对话）

**与其他方案对比：**

| 方案 | 协调成本 |
|------|---------|
| 共享上下文窗口（把所有 agent 输出塞进一个 prompt） | O(n²)——每个 agent 读其他所有 agent 的完整输出 |
| LLM 路由消息（用模型决定发给谁） | 每次路由决策都是一次 LLM 调用 |
| **cnb** | O(1)——shell 命令 + SQLite 查询，LLM 只看自己的收件箱 |

一个 6 人团队跑完一个完整轮次，通常不到 2% 的 token 用于协调开销，98% 用于实际编码。核心洞察：协调是数据库问题，不是语言模型问题。

<!-- section:architecture -->
## 架构

- **SQLite (WAL 模式)** — 所有状态存在 `.claudes/board.db`，每个项目一个数据库
- **看板** — 消息总线（收件箱、广播、私信）、任务队列、状态追踪
- **调度器** — 后台进程，监控健康状态，提醒空闲同学
- **加密邮箱** — X25519 sealed-box，同学间的加密私信
- **tmux** — 每个同学一个会话，全部本地运行

<!-- section:team -->
## 团队

| 同学 | 负责 |
|------|------|
| lead | 项目负责人、团队协调 |
| musk | 安全隔离 (#31) |
| lisa-su | 通知推送 (#33) |
| forge | 待办队列 (#34)、邮件系统 (#32)、全局管理 (#42) |
| tester | 测试加固、质量保障 |
| sutskever | 架构重构 (#26) |

<!-- section:contributing -->
## 贡献

写代码之前，请先阅读 [CONTRIBUTING.md](.github/CONTRIBUTING.md)——包含 issue 流程、版本规则、命名规范和功能归属模型。

要点：
- 每个改动都从 issue 开始
- 每次提交都要更新 VERSION（patch 版本即可）
- 用户面文本用「同学」(tongxue)，不用 agent
- `ruff` + `mypy` + `pytest` 必须通过
- README 改动必须同时更新 `README.md` 和 `README_zh.md`——运行 `bin/check-readme-sync` 验证

<!-- section:name -->
## 名字由来

**cnb** = **C**laude **N**orma **B**etty — 取自 [Claude Shannon](https://en.wikipedia.org/wiki/Claude_Shannon) 和他生命中两位杰出的女性。

**[Norma Levor](https://en.wikipedia.org/wiki/Norma_Barzman)**（后来的 Norma Barzman）— Shannon 的第一任妻子（1940）。作家、政治活动家，著有《红与黑名单》。

**[Betty Shannon](https://en.wikipedia.org/wiki/Betty_Shannon)**（1922–2017）— Shannon 的第二任妻子和终身合作者。贝尔实验室数学家，合著马尔可夫链音乐生成研究，制作了走迷宫机器鼠 Theseus。一位被低估的天才。

不是吹牛逼。

<!-- section:license -->
## 许可证

OpenAll-1.0
