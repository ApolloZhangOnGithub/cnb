# cnb roadmap

最后更新：2026-05-12

cnb 是一个组织。管理这个项目就是管理一个组织。这份 roadmap 按组织优先级排列，不按技术难度。

## 管理原则

1. **组织架构先于功能开发。** 角色不清、责权不明时，先解决组织问题再写代码。在流沙上建不了楼。
2. **一切基础设施必须有 owner。** CI、测试、安全、文档 — 没有 owner 的东西会自然腐化。"待定"不是负责人。
3. **研究和执行分开管理。** 实验假设（`experiment` 标签）是研究议程，不是执行 backlog，不和 bug 修复争注意力。
4. **同一个问题只有一个 issue。** 发现重复时合并，不要两个 issue 讨论同一件事。
5. **运营问题指定负责人并执行，不讨论。** CI 挂了不需要 design doc，需要有人负责修。

---

## 第一优先级：组织架构

### Lead 角色定义 (#64，含 #58)

| | |
|---|---|
| **问题** | lead 同时承担面向用户的终端服务和团队内部的项目管理，两个职责冲突 |
| **方向** | 拆分为「终端主管同学」（per-machine，面向用户）和「项目负责同学」（per-repo，管理团队）|
| **阻塞** | 所有 ownership、通讯、调度设计都依赖角色定义 |
| **决策者** | 用户 |

### 基础设施 Owner (#48，含 #59)

| | |
|---|---|
| **问题** | CI、测试环境、安全配置没有常驻负责人。#59 原文：「没有常驻的负责同学」|
| **做什么** | 指定 code health owner，正式 ownership assignment，不是"有空了顺手修" |
| **管辖范围** | CI pipeline、ruff/mypy、测试稳定性、依赖安全、migration 一致性 |

---

## Ownership 生命周期（核心产品）

cnb 的核心价值是 ownership。从 claim 到 transfer 到 archive，完整的生命周期。

### ✅ Ownership 注册与自治 (#45) — 核心已完成

claim/list/disown/map、verify + auto-PR、scan + 路由。待收尾：文档、集成测试、edge case。

### 🔄 Ownership 交接 (#49) — 进行中

transfer 命令、orphan 检测、offboard 清单、自动 fallback。当前分支 `codex/issue-49-ownership-handoff`。

### Ownership 路由准确性 (#87)

当前 `board scan` 已能把 issue/CI 通知路由到 owner，但仍是路径前缀和文本包含级别。下一步需要可解释 routing evidence、置信度、冲突处理和低置信度 fallback，避免把“关键词通知”包装成成熟的智能责任分配。

### Ownership 保护与自适应 (#30)

保护有 ownership 的同学不被随意 kill。先采集数据（utilization、throughput、coordination cost），再做扩缩决策。遵循 Bitter Lesson：不搞手工规则。

---

## 运营基础

让已有系统可靠运行。不需要设计讨论，需要指定负责人并执行。

| Issue | 内容 | Owner |
|-------|------|-------|
| #60 | 私钥安全：gitignore + 存储位置 + 路径统一 | 归 code health owner |
| #67 | pytest-randomly 屏蔽 | 归 code health owner |
| #73 | sync-issues workflow 修复 | 归 code health owner |
| #74 | 仓库维护 sweep：dirty worktree、stale PR | 归 code health owner |
| #39 | .claudes/ → .cnb/ 路径统一（与 #60 部分重叠）| 归 code health owner |
| #43 | 自动更新检查 | 待指定 |
| #63 | 隐藏目录导致项目看似空文件夹 | 待指定 |
| #61 | README 注明 issue 提到独立仓库 | 待指定 |

---

## 规模化准备

当前单机单项目够用。以下为多项目/多机器做准备，有依赖关系需按序推进。

| Issue | 内容 | 依赖 |
|-------|------|------|
| #34 | 待办操作队列（用户介入闭环）| 无 |
| #75 | 只读 board 查看（不冒充 session）| 无 |
| #41 | 自动化下班流程 | #39 |
| #42 | 全局 ~/.cnb/ dashboard | #41 |
| #47 | 跨项目统一身份 | #42 |
| #46 | task 功能使用调研 | 无 |
| #56 | GitHub Wiki 维护 | 无 |
| #96 | 终端主管同学 Mac companion（一期）| #34, #42 |
| #95 | iPhone Live Activity bridge（二期）| #96 |

---

## 研究议程

开放问题，需要实验验证。不是待开发的 feature，不排期，不指定 deadline。每个 issue 包含假设和实验设计，前置条件是核心 ownership 体系稳定。

| Issue | 假设 |
|-------|------|
| #50 | 单模块 ownership 是否导致全局理解退化？（轮岗）|
| #51 | 自主探索是否防止能力退化？（20% time）|
| #52 | 跨项目交流是否产生新视角？|
| #53 | 项目生命周期管理：何时封存、何时唤醒？|
| #54 | 上下文健康：文档裁剪 + 间隔复习（含 #55）|
| #62 | cnb 作为 LLM 行为研究平台 |

---

## 长期方向

记录方向，不做承诺，不排期。

| Issue | 方向 |
|-------|------|
| #26 | 架构债务：跨机器传输层选型 |
| #29 | 知识共享系统：知识是代码不是文本 |
| #44 | Team dreaming：周期性整合团队知识 |
| — | 云端/托管运行 |

---

## 产品 Ideas

| Issue | Idea |
|-------|------|
| #65 | GitHub Apps 给每个同学独立头像账号 |
| #66 | 资源分配/交易/激励机制 |

---

## 依赖图

```
组织架构 (#64)
  └── 所有 ownership/通讯/调度设计

Ownership 生命周期:
  #45 (✅) ──→ #49 (进行中)
           └─→ #87 路由准确性 ──→ #30 自适应

运营基础:
  #48 code health owner ──→ #60 #67 #73 #74 #39 #59

规模化:
  #39 ──→ #41 ──→ #42 ──→ #47
  #34, #75 (无依赖)

研究议程:
  Ownership 稳定 ──→ #50-#55 #62
```
