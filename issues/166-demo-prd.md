---
number: 166
title: "Demo: 从零造产品 — PRD 到部署的全自动交付"
state: OPEN
labels: ["enhancement", "phase:2"]
assignees: []
created: 2026-05-12
updated: 2026-05-12
---

# #166 Demo: 从零造产品 — PRD 到部署的全自动交付

**State:** OPEN
**Labels:** enhancement, phase:2

---

## 目标

给一个产品需求文档（PRD），cnb 团队从架构设计到代码实现到测试到部署，全程自主交付。

## 为什么这是好 demo

- 最接近"AI 软件公司"的想象
- 展示 cnb 在工程流程中的完整价值链
- 前端/后端/测试/部署各有 owner，PR review 流程，持续集成
- 结果是一个能用的产品，不是一堆文件

## 候选产品

小型但完整的 web 应用，例如：
- 一个 URL 缩短器（后端 + 前端 + 数据库 + 部署）
- 一个 Markdown 笔记本（编辑器 + 存储 + 搜索）
- 一个 API 监控仪表板（采集 + 展示 + 告警）

## 展示重点

- 架构决策通过 proposals 投票
- 代码通过 own/verify/PR 流程
- bug 通过 bug report + SLA 跟踪
- 部署通过 pending actions 等待用户确认
