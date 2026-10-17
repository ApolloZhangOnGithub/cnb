---
number: 161
title: "Dispatcher sends duplicate Daily Digest messages (~50x in 1.5h)"
state: CLOSED
labels: ["bug", "phase:1", "infra"]
assignees: []
created: 2026-05-11
updated: 2026-05-16
closed: 2026-05-16
---

# #161 Dispatcher sends duplicate Daily Digest messages (~50x in 1.5h)

**State:** CLOSED
**Labels:** bug, phase:1, infra

---

## 现象

dispatcher 的 Daily Digest 应该每天给每个同学发一次，但实际上在 ~1.5 小时内重复发送了 50+ 条相同的 `[Daily Digest] 过去 24h 无活动。` 消息给 alice。

```
[2026-05-11 07:39:23] dispatcher → alice: [Daily Digest] 过去 24h 无活动。
[2026-05-11 07:39:30] dispatcher → alice: [Daily Digest] 过去 24h 无活动。
...（共 50+ 条，持续到 09:15）
```

## 影响

- 消息历史被垃圾消息淹没，`board log 50` 看不到任何实质消息
- 数据库写入放大

## 可能的原因

dispatcher 缺少去重/冷却机制 — 每次启动或被调度时都无条件发送 digest，没有记录"今天已经给 X 发过 digest"的状态。

## ROADMAP 关系

与 ROADMAP 中「运营基础」部分相关 — dispatcher 是基础设施组件，应归 code health owner 管辖。不与现有 issue 重叠。
