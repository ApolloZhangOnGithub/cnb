<!-- README_SYNC: sections must match README.md — run bin/check-readme-sync -->

[English](README.md)

# claude-nb

[![CI](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml/badge.svg)](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/claude-nb?label=npm)](https://www.npmjs.com/package/claude-nb)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)
[![Docs](https://img.shields.io/badge/docs-c--n--b.space-14865d)](https://c-n-b.space/)
[![License](https://img.shields.io/badge/license-OpenAll--1.0-444)](LICENSE)

**LLM 团队的项目负责制。**

`cnb` 是面向长期运行 Claude Code / Codex 团队的 local-first 组织基础设施。它给 AI 编码会话提供共享看板、持久 ownership、交接记录和运营检查，让重启后的 session 不再像一个完全失忆的新员工。

```bash
npm install -g claude-nb
```

| 面向 | 当前形态 |
|------|---------|
| 运行时 | 本地 tmux 会话、SQLite 看板、调度器、文件系统报告 |
| 引擎 | 默认 Claude Code；Codex 通过 npm peer CLI 支持 |
| 状态 | 看板数据库、ownership map、issue mirror、日报/轮次报告 |
| 分发 | 公开 npm 包 `claude-nb`，内部为 Python 3.11+ |
| 文档 | README 是最短路径，长期文档在 [`docs/`](docs/)，公开站点为 [`c-n-b.space`](https://c-n-b.space/) |

所有多 agent 工具都在解决"怎么同时跑多个 agent"。cnb 解决的是之后的事——怎么让它们跨 session、跨轮次、跨人员变动地**可管理**。

LLM session 天生无状态。每次重启都是一个什么都不知道的新人。没有组织基础设施，你得到的就是一群临时工——分活、干完、忘掉。cnb 给它们**永久的模块 ownership**：lisa-su 负责通知推送系统，跨越 11 个 commit 和 3 次重启。出了 bug 不用向一个空白 session 从头解释这个模块——找到 owner 的日报，接着干。

这不是为了加速，也不是为了上下文隔离。那些是副产品。核心问题是：[42% 的多 agent 失败是规范与系统设计问题](https://arxiv.org/abs/2503.13657)——角色模糊、任务误解、拆分不当（Cemri et al., NeurIPS 2025 Spotlight）。不是能力不够——是组织不行。cnb 是 AI 团队的组织基础设施。

<!-- section:start-here -->
## 从这里开始

| 需求 | 路径 |
|------|------|
| 安装 CLI | `npm install -g claude-nb` |
| 理解产品模型 | [cnb 提供了什么](#cnb-提供了什么而-session-管理器没有)、[术语表](#术语表)、[Ownership autonomy](docs/design-ownership-autonomy.md) |
| 启动一个团队 | [快速开始](#快速开始)，然后在项目里运行 `cnb` |
| 查看真实运行样例 | [硅谷大战](instances/silicon_vally_battle/) |
| 发布或核对包元数据 | [Package publishing](docs/package-publishing.md) |
| 安全贡献 | [Contributing](CONTRIBUTING.md)、[Security](SECURITY.md)、[Roadmap](ROADMAP.md) |

<!-- section:status -->
## 项目状态

cnb 已经不是一个单脚本实验，但它仍然是一个活跃演进中的 local-first 系统，默认假设运行在可信工作站上，并且需要人工监督。

| 领域 | 当前状态 | 证据 |
|------|---------|------|
| CLI 分发 | npm 入口包装 Python CLI | [`package.json`](package.json)、[`pyproject.toml`](pyproject.toml)、[`bin/cnb`](bin/cnb) |
| 看板运行时 | SQLite schema、migrations、任务/收件箱/状态/ownership 命令 | [`schema.sql`](schema.sql)、[`migrations/`](migrations/)、[`lib/board_*.py`](lib/) |
| 质量门禁 | ruff、mypy、pytest、版本同步、changelog、CodeQL 和 secret scan | [`.github/workflows/ci.yml`](.github/workflows/ci.yml)、[`Makefile`](Makefile) |
| 治理机制 | issue-first、ownership 规则、Co-Authored-By 策略 | [`CONTRIBUTING.md`](CONTRIBUTING.md)、[`ROADMAP.md`](ROADMAP.md)、[`registry/`](registry/) |
| 文档 | 双语 README、长期产品文档、公开 GitHub Pages 站点 | [`README.md`](README.md)、[`docs/`](docs/)、[`site/`](site/) |
| 边界 | local-first、高权限选项、人工监督下的自动化 | [`SECURITY.md`](SECURITY.md)、[常见问题](#常见问题) |

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

标准公开包是 npmjs.com 上的 [`claude-nb`](https://www.npmjs.com/package/claude-nb)。GitHub Packages 也可能显示 scoped 镜像 `@apollozhangongithub/cnb`；npmjs 仍然是受支持的安装路径。发布和可见性规则见 [Package publishing](docs/package-publishing.md)。

npm 的 dependencies 数字只统计 JavaScript 包。cnb 没有必需的 JavaScript 库依赖，但有运行时依赖：

- Node.js 18+，用于 npm 入口
- Python 3.11+，以及 Python 包依赖 `cryptography>=41.0`
- tmux 和 git
- 至少一个 agent CLI：Claude Code CLI（`@anthropic-ai/claude-code`）或 Codex CLI（`@openai/codex`）

安装后运行 `cnb doctor` 检查本机环境。

<!-- section:quickstart -->
## 快速开始

```bash
cd your-project
cnb
```

初始化项目（创建 `.claudes/` 目录，含 SQLite 数据库和配置），在 tmux 中启动一组同学，启动调度器，然后进入领队同学的 Claude Code 会话。

领队同学直接与用户对话。后台同学独立工作，通过看板汇报进展。

<!-- section:docs -->
## 文档

README 是最短路径。长期维护的文档放在 [`docs/`](docs/)：

- [Ownership autonomy](docs/design-ownership-autonomy.md) — 为什么 cnb 把长期模块 ownership 当作核心工作单元。
- [Tongxue avatar generation](docs/avatar-generation.md) — AI 同学头像的安全模型选择和 prompt 规则。
- [Package publishing](docs/package-publishing.md) — npm release、dist-tags 和 GitHub Packages 可见性规则。
- [公开网站](https://c-n-b.space/) — 第一次访问项目时的产品入口和文档导航。

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

先看[精华解说](instances/silicon_vally_battle/HIGHLIGHTS.md)——sutskever 试图挑拨 lecun 和 lisa-su，两人 5 分钟内识破，然后真正的辩论才开始。

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

| 层 | 职责 | 实现 |
|----|------|------|
| CLI 入口 | 用户命令、包入口、健康检查 | [`bin/`](bin/)、[`lib/cli.py`](lib/cli.py) |
| 看板 | 收件箱、广播、私信、任务、状态、待用户操作 | [`lib/board_*.py`](lib/)、[`schema.sql`](schema.sql) |
| Ownership | 路径 ownership、owner 查找、验证、扫描路由 | [`lib/board_own.py`](lib/board_own.py)、[`migrations/008_ownership.sql`](migrations/008_ownership.sql) |
| 运行时 | 每个同学一个本机会话、调度器提醒、进程健康 | [`lib/swarm.py`](lib/swarm.py)、[`lib/concerns/`](lib/concerns/) |
| 持久化 | SQLite WAL 数据库、文件系统报告、issue mirror | `.claudes/`、[`issues/`](issues/)、日报/轮次文档 |
| 集成 | npm 分发、GitHub issue mirror、GitHub Packages mirror、通知投递 | [`.github/workflows/`](.github/workflows/)、[`lib/notification_delivery.py`](lib/notification_delivery.py)、[`docs/package-publishing.md`](docs/package-publishing.md) |

<!-- section:repository-map -->
## 仓库地图

| 路径 | 用途 |
|------|------|
| [`bin/`](bin/) | 可执行入口、发布和一致性检查脚本 |
| [`lib/`](lib/) | 看板、swarm、ownership、通知、registry 和健康检查的 Python 实现 |
| [`migrations/`](migrations/) + [`schema.sql`](schema.sql) | SQLite schema 演进 |
| [`tests/`](tests/) | 覆盖运行时行为的单元测试和集成测试 |
| [`docs/`](docs/) | 长期维护的产品、包发布和 ownership 文档 |
| [`site/`](site/) | GitHub Pages 项目站点源码 |
| [`issues/`](issues/) | 给无 CLI agent session 使用的 GitHub issue mirror |
| [`registry/`](registry/) | 贡献者/同学 registry 和链式校验 |
| [`instances/`](instances/) | 可检查的 demo 项目快照 |

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

<!-- section:contribution-wall -->
## 广义贡献者墙

GitHub 原生 Contributors 面板只统计 commit。cnb 也把 issue、PR review、checks、看板 ownership、以及可见的 GitHub App 动作当作贡献信号。下面是第一个广义贡献视图；实现说明见 [贡献者墙](docs/contribution-wall.md)。

<p>
  <a href="https://github.com/ApolloZhangOnGithub/cnb/issues/65#issuecomment-4414136928" title="musk: GitHub App identity verified through issue activity and a guarded commit">
    <img src="https://avatars.githubusercontent.com/u/283269623?s=96&v=4" width="48" height="48" alt="cnb-workspace-musk[bot]" />
  </a>
</p>

<!-- section:faq -->
## 常见问题

**Q：cnb 和 Claude Squad / amux / ittybitty 比怎么样？**

侧重不同。它们是 session 管理器——擅长启动、隔离、监控并行 agent。cnb 是上面的组织层：模块 ownership、日报、追责机制、交接协议。两者互补；你可以用 session 管理器管 tmux 层，用 cnb 做团队协调。

**Q：cnb 和 Codex 比怎么样？**

不同品类。Codex 在云端沙箱跑独立任务。cnb 在本地协调跨 session 的持久团队。一次性任务用 Codex，需要跨重启的连续性和 ownership 用 cnb。

**Q：cnb 和 OpenClaw 比怎么样？**

完全不同的项目。OpenClaw 是跨 20+ 通信平台（WhatsApp、Telegram、Slack 等）的个人 AI 助手。cnb 是专门为 Claude Code 开发团队设计的多 agent 协调框架。没有重叠。

**Q：cnb 能不能无人值守运行？**

目前还不行。领队同学需要人来驱动。但这是活跃开发方向——见 [ROADMAP.md](ROADMAP.md) Phase 2。目标是让模块负责人能自主发现 issue、验证自己的工作、创建 PR、响应故障，不需要人催。

**Q：cnb 的 token 效率怎么样？**

很好。所有协调（消息、任务、状态）通过 shell 命令 + SQLite 运行，不经过 LLM。一个 6 人团队不到 2% 的 token 用于协调。详见[Token 效率](#token-效率)。

<!-- section:contributing -->
## 贡献

写代码之前，请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)——包含 issue 流程、版本规则、命名规范、安全策略和功能归属模型。

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
