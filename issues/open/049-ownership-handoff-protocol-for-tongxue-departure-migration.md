---
number: 49
title: "Ownership handoff: protocol for tongxue departure/migration"
state: OPEN
labels: ["phase:2", "ownership", "org-design"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #49 Ownership handoff: protocol for tongxue departure/migration

**State:** OPEN
**Labels:** phase:2, ownership, org-design

---

## Summary

同学可能"离职"——带着身份迁移到另一个项目，或因为异常情况失去 session。当前没有正式的 handoff 协议，ownership 会变成 orphan。

## ROADMAP 关系

是 #45（ownership 自治）的补充。#45 解决了 ownership 注册和使用，本 issue 解决 ownership 的生命周期终结。与 #30（自适应团队）也相关——扩缩容时需要知道谁能安全移除。

## 具体场景

1. **计划性离职**：同学被调去另一个项目，需要交接所有 owned paths
2. **非计划性离职**：session 崩溃、被误杀、tmux 意外关闭
3. **临时借调**：同学暂时去别的项目帮忙，ownership 不应丢失

## 需要的能力

### 1. Ownership 交接命令
```bash
board --as alice own transfer bob lib/  # alice 把 lib/ 转给 bob
board --as alice own transfer-all bob   # alice 把所有 ownership 转给 bob
```

### 2. Orphan 检测
- 定期检查 ownership 表中的 session 是否还有 heartbeat
- 超过阈值（如 24h 无心跳）标记为 orphaned
- 通知 lead 或 dispatcher 处理

### 3. 离职清单
```bash
board --as alice own offboard  # 列出 alice 所有 ownership + 待处理任务 + 未 push 的代码
```

### 4. 自动 fallback
- orphaned ownership 的文件如果被其他同学修改，自动提示认领
- `board scan` 发现 orphaned owner 的相关 issue 时，广播而非投递给 orphan

## 不做什么

- 不自动删除 ownership（误删风险太大，人工确认）
- 不做跨项目 ownership 迁移（等 #47 统一身份先）
