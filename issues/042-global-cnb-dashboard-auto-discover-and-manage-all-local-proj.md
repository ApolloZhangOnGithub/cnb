---
number: 42
title: "Global ~/.cnb/ dashboard: auto-discover and manage all local projects"
state: OPEN
labels: ["phase:2", "infra", "priority:p2"]
assignees: []
created: 2026-05-07
updated: 2026-05-10
---

# #42 Global ~/.cnb/ dashboard: auto-discover and manage all local projects

**State:** OPEN
**Labels:** phase:2, infra, priority:p2

---

## Problem

目前每个项目有自己的 `.claudes/`，但没有全局视图。用户在一台电脑上可能同时跑多个 cnb 项目（cnb、TokenDance_BBS、其他），无法：
- 一眼看到所有项目的状态
- 统一管理下班/启动
- 跟踪哪些项目有活跃同学、哪些已关停
- 汇总全机器的 token 用量

## 与 #36 的关系

#36 实现了 `~/.cnb/projects.json` 注册表，但只是被动记录（init 时注册）。本 issue 要求主动扫描和持续跟踪。

## Expected behavior

`~/.cnb/` 作为全局控制中心：

### 1. 自动发现
- 低开销扫描（不轮询全盘）：利用 #36 的注册表 + inotify/FSEvents 监听已知路径
- 新项目 `cnb init` 时自动注册（#36 已做）
- 定期 cleanup 已删除的项目（#36 已做）

### 2. 全局 dashboard
```bash
cnb global status     # 所有项目一览
cnb global projects   # 等同 cnb projects list，但带活跃状态
cnb global usage      # 全机器 token 汇总（关联 #38）
```

### 3. 全局控制
```bash
cnb global shutdown          # 所有项目优雅关停（关联 #41）
cnb global shutdown <project> # 指定项目关停
```

### 4. 性能约束
- 不能轮询全盘扫描
- 不能常驻后台进程吃资源
- 读取时按需查询各项目的 board.db（SQLite 只读很快）
- 可选：轻量 FSEvents watcher，只监听已注册项目的 `.claudes/board.db` 变化

## 关联 issues
- #36 全局注册表（基础设施，已完成）
- #38 token 用量追踪
- #41 自动化下班流程
