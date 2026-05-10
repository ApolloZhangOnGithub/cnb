---
number: 53
title: "Project archival and hibernation: cost-aware project lifecycle"
state: OPEN
labels: ["experiment", "ownership", "org-design"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #53 Project archival and hibernation: cost-aware project lifecycle

**State:** OPEN
**Labels:** experiment, ownership, org-design

---

## Summary

项目可以保留负责同学，但维护是有成本的（token、attention、context）。和人不同，项目可以封存——但何时封存、何时唤醒是关键决策。

## ROADMAP 关系

与 #42（全局 dashboard）和 #30（自适应团队）相关。全局管理需要知道哪些项目活跃、哪些该封存；自适应团队需要决定是否值得为一个低活跃项目保留同学。

## 具体问题

1. **封存 (archive)**: 项目代码完整、测试通过、文档齐全，但不再需要日常开发。同学可以释放。
2. **休眠 (hibernate)**: 项目仍需偶尔维护（安全更新、依赖升级），但不需要常驻同学。
3. **唤醒 (wake)**: 封存/休眠项目重新启动时，如何快速恢复上下文？日报和 ownership 记录是否够用？
4. **裁员**: 活跃项目中，部分同学可能不再需要（功能稳定后）。如何优雅释放而不丢失 ownership？

## 可能的命令

```bash
cnb archive                    # 封存当前项目：验证测试通过、生成封存报告、标记所有 ownership 为 archived
cnb hibernate                  # 休眠：保留 ownership 记录但释放同学
cnb wake                       # 唤醒：读封存报告、重建同学、恢复 ownership
cnb downsize [--keep owner]    # 缩编：只保留 ownership 同学，释放其余
```

## 不做什么

- 不自动封存（误封风险太大）
- 不删除任何数据（封存 = 标记状态，不是删文件）
