---
number: 54
title: "Context health: audit, prune, and maintain documentation freshness"
state: OPEN
labels: ["experiment", "infra"]
assignees: []
created: 2026-05-08
updated: 2026-05-09
---

# #54 Context health: audit, prune, and maintain documentation freshness

**State:** OPEN
**Labels:** experiment, infra

---

## Summary

文档和上下文越来越多，维护成本逐渐超过收益。需要定期审计和裁剪机制。

## ROADMAP 关系

与 #48（技术债 ownership）相关。代码健康包含文档健康。

## 具体问题

1. **ROADMAP 膨胀**: 已有 10+ issue，每次启动要读完才能做决策
2. **MEMORY.md 增长**: 自动记忆文件越来越多，相关性下降
3. **CLAUDE.md 规则堆积**: 规则只增不减，新同学启动负担越来越重
4. **日报堆积**: dailies/ 目录越来越大，旧日报价值递减

## 可能的方案

- `cnb audit`: 扫描所有文档，标记过时/冲突/重复内容
- ROADMAP 自动按完成状态折叠已完成 issue
- MEMORY.md 定期 prune（等 Dreaming 功能上线后可自动化）
- 日报保留策略：>30 天的自动归档到 archive/

## 与 Dreaming 的关系

Claude Dreaming（已公布，未正式发布）可以自动做个人记忆整理。但团队级文档（ROADMAP、CLAUDE.md、bulletin）仍需手动或专门工具管理。
