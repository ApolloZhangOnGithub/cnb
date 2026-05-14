---
number: 44
title: "Team dreaming: periodic background consolidation of shared project knowledge"
state: OPEN
labels: ["phase:3", "org-design"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #44 Team dreaming: periodic background consolidation of shared project knowledge

**State:** OPEN
**Labels:** phase:3, org-design

---

## 问题

每个同学单独产出日报、board 消息、task 记录、commit。这些信号散落各处，没有人定期把它们整合成可靠的共享知识。结果：

- ROADMAP 进展标记靠人手动更新
- 跨同学的决策散落在 board 消息历史里，新同学无从了解
- 同一模块两个同学的理解可能已经矛盾，但没人发现
- stale task、未响应的 bug 需要人盯着才能发现

## 灵感来源

Claude Code 的 auto-dream 机制（`services/autoDream/`）。它在用户无感的情况下，后台 fork 一个子 agent 回顾最近的会话 transcript，整理/合并/修剪个人 memory 文件。

核心设计：
1. **三层 gate**（成本递增）：time gate → activity gate → lock，最便宜的检查排最前
2. **Lock-as-timestamp**：lock 文件的 mtime 就是 lastConsolidatedAt，不需要额外状态
3. **四阶段 prompt**：orient → gather → consolidate → prune
4. **Fire-and-forget**：不阻塞任何同学的工作

## 方案

借鉴机制，但把信号源从个体 transcript 换成团队产出物，把产出从个体 memory 换成共享知识文件。

### Gate 设计

| Gate | 检查内容 | 成本 |
|------|----------|------|
| Time | 距上次 team consolidation >= 12h | 1 次 DB query |
| Activity | 期间 >= N 个 task done / daily report / board message | 1 次 DB query |
| Lock | `consolidation_log` 表：`last_at`, `holder_session`, `status` | 同上 |

SQLite 比文件锁更自然（cnb 已有 `board.db` 基础设施）。`updated_at` 列同时承担 lock 和 timestamp。

### 四阶段 Prompt

**Phase 1 — Orient**
- 读 ROADMAP.md、现有 shared docs
- `board view` 看 board 全景
- 读 `.claudes/dailies/`（或 `.cnb/dailies/`）最近的日报

**Phase 2 — Gather**
- 扫描各同学日报（最富信号的源）
- board message 历史中的跨同学对话
- task 完成/创建记录
- `git log` 中各同学的提交
- bug report 趋势

**Phase 3 — Consolidate**
- 更新 ROADMAP.md 的进展标记
- 生成/更新 `DECISIONS.md` — 从散落的 board 消息中提炼决策记录
- 识别项目健康问题（卡住的 task、未响应的 bug、长期 idle 的同学）
- 识别矛盾 — 两个同学对同一模块的理解不一致

**Phase 4 — Prune**
- 标记已完成的 ROADMAP 项
- 清理过期的 board 公告
- 归档已关闭的 bug

### 触发点

- dispatcher 的 idle loop
- 某个同学完成 task 后顺便检查 gate
- 用户手动 `cnb dream`

### 产出物

- `.cnb/team_digest.md` — 一页纸的项目现状
- ROADMAP.md 进展标记更新
- `DECISIONS.md` — 结构化决策记录
- `board send all "..."` 广播关键发现

### 不做的事

- **不做个体 memory 整理** — Claude Code 的 auto-dream 已经覆盖
- **不扫描原始 transcript** — daily report 和 board message 已经是经过同学自己提炼的摘要

## 与现有 issue 的关系

- 与 #29 知识共享有关联但不重叠 — #29 是跨机器的可执行知识体系，本 issue 是单项目内的周期性整理
- 与 #42 全局巡检有关联但不重叠 — #42 是基础设施健康（孤儿 tmux、stale lock），本 issue 是知识健康
- 受益于 #41 自动下班（daily report 是主要信号源），但可以先用已有的 board message + task history 启动
- 不依赖 #39 重命名（路径无关）

## 建议阶段

Phase 2。不需要跨机器基础设施，用现有 SQLite + board 即可实现。

## MVP

最小版本只做 Team Health Check：gate + 读日报/task history + 生成 `team_digest.md` + 广播摘要。ROADMAP 自动更新和 DECISIONS.md 可以后续迭代加。
