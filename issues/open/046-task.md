---
number: 46
title: "调研：task 功能使用情况及推广"
state: OPEN
labels: ["phase:2"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #46 调研：task 功能使用情况及推广

**State:** OPEN
**Labels:** phase:2

---

## 背景

task 子系统（`board task add/done/list/next`）功能完整：支持优先级、跨人指派+通知、自动推进下一个任务。但目前不确定是否有同学在实际使用。

## 目标

1. **调研现状**：查历史数据（board.db 的 tasks 表），确认各 demo/instance 中 task 的实际使用量
2. **对比分析**：同学们是用 task 管理工作，还是靠 send/status 口头协调？如果没人用，找出原因
3. **推广决策**：如果功能好用但缺曝光，考虑在 Show HN 帖子中作为卖点展示；如果功能有缺陷，记录改进方向

## 与 ROADMAP 的关系

ROADMAP 中 ownership autonomy 提到 `task done` 后要接 CI 验证。本 issue 是前置调研——如果 task 本身没人用，接 CI 验证的优先级也要重新评估。与 #45 有关联但不重叠。

## 验收标准

- [ ] 统计至少 2 个 instance 的 task 使用数据（总数、完成率、是否跨人指派）
- [ ] 给出结论：推广 / 改进 / 降优先级
- [ ] 如果结论是推广，在 Show HN 草稿中体现 task 功能
