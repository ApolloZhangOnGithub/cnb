<!-- README_SYNC: sections must match README.md — run bin/check-readme-sync -->

[English](README.md)

# claude-nb

Claude Code 多实例协作框架。

多个 Claude Code 实例共享一块看板——互相发消息、分配任务、同步状态、协作开发同一个代码库。

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

<!-- section:architecture -->
## 架构

- **SQLite (WAL 模式)** — 所有状态存在 `.claudes/board.db`，每个项目一个数据库
- **看板** — 消息总线（收件箱、广播、私信）、任务队列、状态追踪
- **调度器** — 后台进程，监控健康状态，提醒空闲同学
- **加密邮箱** — X25519 sealed-box，同学间的加密私信
- **tmux** — 每个同学一个会话，全部本地运行

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
