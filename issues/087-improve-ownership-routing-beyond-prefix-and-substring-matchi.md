---
number: 87
title: "Improve ownership routing beyond prefix and substring matching"
state: OPEN
labels: ["phase:2", "ownership", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #87 Improve ownership routing beyond prefix and substring matching

**State:** OPEN
**Labels:** phase:2, ownership, infra

---

## 背景

当前 `board own` 和 `board scan` 已经有可用的 ownership 基础能力，但路由准确性还处在早期阶段：

- 文件 owner 使用最长路径前缀匹配。
- issue 路由通过在 title/body 中查找 ownership pattern。
- CI failure 目前基本广播给所有 owner，让 owner 自行判断。

这足够支撑早期本地协作，但不应该被描述成成熟的智能责任分配。继续直接堆规则容易误路由，误路由比不路由更糟。

## 为什么这次不直接修

这不是一个单点 bug。要做好需要先定路由语义、证据优先级、置信度和 fallback 策略，并补全可解释输出和测试矩阵。否则只是把 substring matching 包装得更复杂。

## 建议方案

1. 定义路由输入优先级：GitHub assignee、label、changed files、ownership path、issue body references、CI job/file evidence。
2. 为每次路由生成解释：matched owner、matched evidence、confidence、fallback reason。
3. 低置信度或多 owner 冲突时 fallback 到 terminal supervisor/project responsible tongxue，而不是误发给单一 owner。
4. CI failure 不再简单通知所有 owner；优先解析 failed job、相关 paths、最近 diff，再决定 owner 或 fallback。
5. 保留 dedup 和 audit log，便于复盘误路由。

## Acceptance criteria

- `board scan` 对每条 issue/CI 通知写入可解释 routing evidence。
- issue routing 覆盖 assignee、label、path reference、无匹配 fallback、多匹配冲突。
- CI routing 覆盖失败 run、不可解析 run、无 gh CLI、gh timeout、重复通知。
- 误路由风险明确可见：低置信度必须 fallback，不允许静默猜 owner。
- README/ROADMAP 明确标注当前路由成熟度，直到该 issue 完成。

## 相关位置

- `lib/board_own.py`：`find_owner()`, `_scan_issues()`, `_scan_ci()`
- `tests/test_ownership.py`：当前 ownership/scan 测试
- `docs/design-ownership-autonomy.md`：已有设计方向，可作为输入但需要落到当前 schema 和 CLI 行为

## Labels

phase:2, ownership, infra
