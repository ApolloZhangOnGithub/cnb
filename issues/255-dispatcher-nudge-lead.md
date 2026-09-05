---
number: 255
title: "Dispatcher nudge lead 时附带空闲员工清单"
state: OPEN
labels: ["enhancement", "phase:1", "infra", "org-design", "priority:p1"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #255 Dispatcher nudge lead 时附带空闲员工清单

**State:** OPEN
**Labels:** enhancement, phase:1, infra, org-design, priority:p1

---

## 背景

我们已确立组织原则：员工 idle 是合理的（避免 PR conflict 级联、给 lead 协调留缓冲），lead idle 不合理（已通过 PR #244/#252 修复 lead keep-alive）。

但目前 lead 被 nudge 时只收到通用提醒"扫描团队状态、派活"，必须自己 capture-pane 看谁空了。这增加 lead 摩擦。

## 期望

dispatcher nudge lead 时附带具体空闲员工清单，例如：

```
lead 不能 idle。空闲员工：musk (idle 32s)、bezos (idle 18s)。
PR queue: 3 个等 review。Open phase:1 issues: 5 个。
请直接派下一个 issue 给空闲员工。
```

## 与现有 issue 关系

- 基于 #223 lead 保活（已 close）做内容增强
- 与 #235 dispatcher 自动 reload 无关
- 与 #134 sprint plan 兼容（不冲突）

## 设计要点

- IdleDetector 已有 cache，复用即可，不重复 capture-pane
- 空闲清单按 idle 秒数排序，最久空闲在前
- 阈值：员工 idle > 15s 才进清单（避免短暂思考间隙噪音）
- nudge 文案模板可注入实时数据
