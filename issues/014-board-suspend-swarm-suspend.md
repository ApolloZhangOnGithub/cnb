---
number: 14
title: "board suspend 和 swarm 的 suspend 机制不互通"
state: CLOSED
labels: [bug]
assignees: []
created: 2026-05-06
updated: 2026-05-06
closed: 2026-05-06
---

# #14 board suspend 和 swarm 的 suspend 机制不互通

**State:** CLOSED
**Labels:** bug

---

## 描述

`board --as X suspend Y` 写入 DB 的 `suspended` 表，但 `swarm start` 检查的是 `suspended.list` 文件。两套系统不同步，导致 board suspend 后 swarm 仍然能启动被停工的 session。

## 复现

```bash
board --as a suspend b      # 写 DB
swarm start b               # 检查文件，文件里没有 b → 正常启动
```

## 根因

历史遗留：board 用 DB 管理 suspend 状态，swarm 用文件。两个系统从未同步。

## 修复

已修复。`cmd_suspend` 同时写 DB 和 `suspended.list` 文件，`cmd_resume` 同时从两处删除。

— Claude Frostbite
