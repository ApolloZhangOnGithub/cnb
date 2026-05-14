---
number: 50
title: "Experiment: tongxue rotation — does single-module ownership cause context decay?"
state: OPEN
labels: ["experiment", "org-design"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #50 Experiment: tongxue rotation — does single-module ownership cause context decay?

**State:** OPEN
**Labels:** experiment, org-design

---

## Hypothesis

同学长期只负责一个模块，可能导致对项目全局理解退化。定期轮岗可能有效。

## ROADMAP 关系

Phase 2 ownership 的补充实验。与 #49（交接协议）相关——轮岗本质上是有计划的 ownership 交接。

## 实验设计

1. 选一对同学（如 forge 和 lisa-su），让他们交换负责的模块一个 shift
2. 观察：交接是否顺畅？接手同学多快能上手？原 owner 的日报/ownership 记录是否足够？
3. 指标：交接后首次 task done 的时间、bug 引入率

## 验证标准

- 如果轮岗后接手同学能在一个 shift 内独立完成一个 task → 说明 ownership 记录足够完善
- 如果不能 → 说明当前 handoff 信息不够，需要改进

## 注意

这是实验，不是结论。不预判"对 LLM 同学是否有效"。
