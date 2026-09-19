---
number: 260
title: "VERSION allocation coordination — prevent collision waste"
state: OPEN
labels: ["enhancement", "phase:1", "infra", "priority:p2"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #260 VERSION allocation coordination — prevent collision waste

**State:** OPEN
**Labels:** enhancement, phase:1, infra, priority:p2

---

## Background

观察 2026-05-17 PR wave 中 VERSION 撞号若干次:
- #220 / #247 都 0.86
- #229 / #254 / #221 / #224 多重 0.77/0.78/0.94 撞
- #251 / #253 都 0.93
- #243 (lead) / #241 (lisa-su) 都 0.85
- bezos rebump 4 PR + lisa-su amend 2 PR + lead rebase 3 次都因撞号

每次撞需要 force-push amend + CI re-run，浪费 ~3 分钟 × N 次。

## Why it happens

当前 VERSION 选号是手工 "看矩阵 + 跳":
- 开 PR 时看现有 open PR VERSION 选个空位
- master 移动时 (10+ commit today) 矩阵失效，需要 rebump
- 多 PR 并行开时彼此不知道对方刚选什么号

## 可能方案 (need design)

1. **Per-tongxue 号段**: lead 占 0.5.0X1, bezos 0.5.0X2, lisa-su 0.5.0X3, musk 0.5.0X4 (X=主版本)。冲突几率 ~0
2. **lock service**: `board version-claim 0.5.81-dev` 占号写 SQLite，重复占报错
3. **next-version command**: `bin/sync-version --next` 自动读 master VERSION + open PR 矩阵 → 输出下一个空位
4. **CI-side enforcement**: PR check 让 collision 直接 fail（force first-wins，但仍要 rebump）

## Acceptance

- [ ] 团队讨论 4 方案优劣
- [ ] 选 1 个实现
- [ ] PR collision rate 从 6+/天 降到 <1/天

## Owner

待指定。可能 fit: bezos (做过 #87 ownership routing) 或 musk (做过 dispatcher infra)。等今日 wave 沉淀后再分派。

## 与 ROADMAP 关系

属于 `运营基础` 类。
