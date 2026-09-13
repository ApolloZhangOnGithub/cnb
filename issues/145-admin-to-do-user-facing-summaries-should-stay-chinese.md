---
number: 145
title: "ADMIN_TO_DO user-facing summaries should stay Chinese"
state: CLOSED
labels: ["bug", "documentation", "module:mac-companion", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #145 ADMIN_TO_DO user-facing summaries should stay Chinese

**State:** CLOSED
**Labels:** bug, documentation, module:mac-companion, priority:p2

---

## 背景

`ADMIN_TO_DO.md` 会被 iOS 状态页、Live Activity/Dynamic Island、Mac companion 状态页读取并展示。之前文件内容以英文维护说明为主，App 原样展示后会出现不符合中文阅读习惯的待办标题和摘要。

本次先做了人工修正：

- `ADMIN_TO_DO.md` 已改为中文可读说明；
- 命令、包名、URL、issue 链接、错误码和终端输出保留原文；
- 文件顶部已写明规范：面向用户、状态页、实时活动、灵动岛和 Mac companion 的维护待办标题与摘要必须使用中文。

## 问题

后续仍可能发生：

- 维护者从英文 CI / npm / GitHub Actions 输出中直接粘贴待办；
- 设备状态页再次抓到英文段落；
- iOS/Mac companion 的卡片摘要显示英文维护语境；
- 原始待办内容和面向用户展示内容混在一起，导致可执行信息和用户阅读体验互相牵制。

## 期望

先不要接入 GitHub Actions agent 或自动翻译流水线。后续再讨论是否做结构化方案。

建议方向：

- 保持 `ADMIN_TO_DO.md` 源文件可读，并要求用户可见摘要使用中文；
- 如需自动化，优先考虑旁路文件，例如 `ADMIN_TO_DO.zh.md` 或 `admin_todo.zh.json`；
- App 默认读取中文展示字段，必要时仍可查看原文；
- 任何自动翻译都不能改写命令、包名、URL、错误码和代码块。

## 验收口径

- 新增维护待办时，用户可见标题和摘要默认中文；
- iOS 状态页、Live Activity/Dynamic Island、Mac companion 不再把英文维护段落直接露给用户；
- 原始命令和诊断证据仍然保真；
- 在明确决定之前，不启用 GitHub Actions agent 自动翻译。

