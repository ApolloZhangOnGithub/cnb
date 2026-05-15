<!-- README_SYNC: sections must match README.md — run bin/check-readme-sync -->

[English](README.md)

# c-n-b

[![CI](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml/badge.svg)](https://github.com/ApolloZhangOnGithub/cnb/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/claude-nb?label=npm)](https://www.npmjs.com/package/claude-nb)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)
[![Docs](https://img.shields.io/badge/docs-c--n--b.space-14865d)](https://c-n-b.space)
[![License](https://img.shields.io/badge/license-MIT-444)](LICENSE)

**LLM 团队的项目 ownership。** cnb 为 Claude Code 和 Codex 会话提供共享看板、持久化模块 ownership 和交接记录——重启后的会话能接续上一个的工作，而不是一个什么都不知道的新人。

<!-- section:install -->
## 安装

```bash
npm install -g claude-nb
```

依赖：Node.js 18+、Python 3.11+、tmux、git，以及至少一个 agent CLI（[Claude Code](https://claude.ai/code) 或 [Codex](https://github.com/openai/codex)）。

<!-- section:quickstart -->
## 快速开始

**方式 A — 在任何 Claude Code 会话中激活：**

```bash
claude        # 正常启动 Claude Code
/cnb          # 激活设备主管——cnb 治理上线
```

**方式 B — 完整团队启动：**

```bash
cd your-project
cnb           # 初始化 .cnb/、启动同学团队、启动 dispatcher
```

Codex：`cnb codex` 或 `CNB_AGENT=codex cnb`。启动参数、`/goal` 工作流、看板 nudge 和 smoke test 详见 [Codex 引擎](docs/codex-engine.md)。

飞书：`cnb feishu setup && cnb feishu start`。详见 [飞书 bridge](docs/feishu-bridge.md)。

<!-- section:docs -->
## 文档

| 我想要... | 去哪里 |
|-----------|--------|
| 从零开始 | [快速上手](docs/getting-started.md) |
| 查看所有命令 | [命令参考](docs/commands.md) |
| 连接飞书 | [飞书 bridge](docs/feishu-bridge.md) |
| 使用 Codex 引擎 | [Codex 引擎](docs/codex-engine.md) |
| 了解定价 | [定价](docs/pricing.md) |
| 切换 LLM 模型 | [模型管理](docs/cnb-model.md) |
| 贡献代码 | [贡献指南](CONTRIBUTING.md) |
| 浏览全部文档 | [完整文档索引](docs/index.md) |

架构、设计决策和内部文档：[`docs/dev/`](docs/dev/)。

<!-- section:project-management -->
## 项目管理

GitHub Issues 是所有工作的唯一真相源。5 个 Project Board 按模块过滤：

| Board | 范围 |
|-------|------|
| [cnb](https://github.com/users/ApolloZhangOnGithub/projects/1) | 所有 issue |
| [cnb Core](https://github.com/users/ApolloZhangOnGithub/projects/2) | CLI、board、runtime、测试、CI |
| [Feishu Bridge](https://github.com/users/ApolloZhangOnGithub/projects/3) | 飞书集成 |
| [Mac Companion](https://github.com/users/ApolloZhangOnGithub/projects/4) | Mac/iPhone 应用 |
| [Org Design](https://github.com/users/ApolloZhangOnGithub/projects/5) | 组织架构 |

新 issue 按标签自动路由到对应 board。优先级详见 [ROADMAP.md](ROADMAP.md)。

<!-- section:demo -->
## Demo

**[硅谷大战](instances/silicon_vally_battle/)** — 10 位 AI 领袖通过 cnb 辩论 Python vs Rust。3 小时 886 条消息。先看[精华解说](instances/silicon_vally_battle/HIGHLIGHTS.md)。

<!-- section:why -->
## 为什么用 cnb

所有多 agent 工具都在解决"怎么跑多个 agent"。cnb 解决的是之后的事——怎么让它们跨重启、跨班次、跨团队变动保持**可管理**。[42% 的多 agent 失败是组织问题](https://arxiv.org/abs/2503.13657)，不是能力问题。cnb 是组织基础设施。

与 Claude Squad、amux、Codex 等的对比见 [快速上手](docs/getting-started.md#comparison)。

<!-- section:contributing -->
## 贡献

先读 [CONTRIBUTING.md](CONTRIBUTING.md)。核心规则：每个改动先有 issue，每次提交 bump VERSION，`ruff` + `mypy` + `pytest` 必须通过。

<!-- section:license -->
## 许可证

[MIT](LICENSE)
