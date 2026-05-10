---
number: 45
title: "Ownership autonomy: own/verify/pr/scan"
state: OPEN
labels: ["phase:2", "ownership"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #45 Ownership autonomy: own/verify/pr/scan

**State:** OPEN
**Labels:** phase:2, ownership

---

## Summary

实现负责人自治的四个核心能力，让 ownership 从"这个模块是你的"变成"负责人能独立闭环"。

## ROADMAP 关系

直接对应 Phase 2「负责人自治能力」，是 ROADMAP 中 ownership 闭环的核心 issue。与 #39（已完成重命名兼容）无冲突。

## 开发进度

### ✅ 已完成

- [x] Migration 008: `ownership` 表 + 索引
- [x] `lib/board_own.py`: ownership CRUD (claim/list/disown/map)
- [x] `find_owner()`: 最长前缀匹配
- [x] `verify_task()`: pytest 自动验证 (returncode 0/5 通过)
- [x] `auto_pr()`: feature branch 自动 push + `gh pr create`
- [x] `cmd_scan()`: GitHub issues + CI 状态扫描，按 ownership 路由通知
- [x] `task done` 集成 verify + auto-PR（`--skip-verify` 可跳过）
- [x] 注册到 `bin/board` 命令表 (own, scan)
- [x] 28 个单元测试全部通过
- [x] schema.sql 同步更新
- [x] CHANGELOG 记录
- [x] ROADMAP 更新

### 🔲 待完成

- [ ] CLAUDE.md 补充 ownership 命令文档
- [ ] README 补充 own/scan 命令说明
- [ ] 集成测试：end-to-end `task done` → verify → PR 流程
- [ ] edge case: ownership 表为空时 scan 的行为优化
- [ ] edge case: verify 在非 Python 项目中的 fallback
- [ ] dispatcher 集成：定时自动 `board scan`（替代手动触发）

### 📋 后续 issue（不在本 issue 范围）

- 外部触发自动化（webhook/Channels 替代 polling）
- 基于 git blame 的 ownership 自动推荐
- ownership 冲突解决机制
