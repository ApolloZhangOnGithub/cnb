---
number: 47
title: "Cross-project identity: unified tongxue across multiple .cnb/ projects"
state: OPEN
labels: ["phase:2", "infra", "org-design", "priority:p2"]
assignees: []
created: 2026-05-08
updated: 2026-05-10
---

# #47 Cross-project identity: unified tongxue across multiple .cnb/ projects

**State:** OPEN
**Labels:** phase:2, infra, org-design, priority:p2

---

## Summary

一个能力强的同学可能同时参与多个项目。当前每个项目的 .cnb/ 是完全独立的，同一个人在不同项目里是不同身份，无法统一查看跨项目状态。

大厂同样面临这个问题（统一身份 + 跨项目 dashboard）。

## ROADMAP 关系

与 #42（全局 dashboard）强相关。#42 目前只做跨项目发现和清理，但缺少统一身份层。本 issue 补充身份部分。

## 具体问题

1. **身份碎片化**：alice 在 project-A 和 project-B 是两个独立 session，日报、ownership、消息不互通
2. **状态不可见**：用户无法一眼看到"alice 现在在哪个项目干什么"
3. **跨项目 ownership**：alice 负责 project-A 的 lib/ 和 project-B 的 api/，没有统一视图

## 可能的方案

- `~/.cnb/identity.toml`：全局身份注册，每个同学有唯一 ID
- `cnb global status`：跨项目聚合 dashboard（扩展 #42）
- 项目级 .cnb/config.toml 引用全局 identity，而非自行定义 session 名

## 不做什么

- 不做跨项目消息传递（那是 #26 架构债务的范畴）
- 不做跨项目任务调度（太复杂，先观察需求）
