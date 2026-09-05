---
number: 223
title: "Dispatcher 应当保活 lead session — 停了自动 nudge 继续"
state: CLOSED
labels: ["enhancement", "phase:1", "infra"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
closed: 2026-05-17
---

# #223 Dispatcher 应当保活 lead session — 停了自动 nudge 继续

**State:** CLOSED
**Labels:** enhancement, phase:1, infra

---

## 问题

dispatcher 的 SessionKeepAlive 和 NudgeCoordinator 通过 \`get_dev_sessions()\` 拿同学列表，但该函数明确排除了 \`lead\` (lib/concerns/helpers.py:52)。所以 lead session 停了/idle 了，dispatcher 不会救它，导致团队无人指挥。

## 期望

lead idle 时 dispatcher nudge 它继续：检查团队进度、处理 inbox、分派活。

## 实现思路

- helpers.py 加 \`get_lead_session()\`
- NudgeCoordinator 多 process 一遍 lead，用专属 idle 文案（"继续管理团队，检查 inbox 和 PR"，而不是同学的 OKR 文案）

## 与 ROADMAP 的关系

属于运营基础。与 #160 supervisor stall 有概念关联但不重叠（#160 针对 device supervisor 在飞书 compact 卡死）。
