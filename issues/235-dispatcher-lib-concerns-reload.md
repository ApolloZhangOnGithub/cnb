---
number: 235
title: "Dispatcher 应检测 lib/concerns/* 改动并自动 reload"
state: OPEN
labels: ["enhancement", "phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #235 Dispatcher 应检测 lib/concerns/* 改动并自动 reload

**State:** OPEN
**Labels:** enhancement, phase:1, infra, priority:p1

---

## ROADMAP check

已检查 ROADMAP.md。无相关条目，无现有 issue 重复。

## 问题

PR #227 (#226 nudge 去重修复) merge 到 master 后，运行中的 dispatcher 进程不会自动 pickup 新代码。需要人工 kill + 重启 dispatcher 才能让修复生效。

具体证据（musk 观察）：
- dispatcher PID 49535 在 2026-05-17 14:19 启动
- PR #227 (commit 3d4f748) 在 15:00 merge
- musk 还在被旧代码的 NudgeCoordinator 反复 nudge

## 为什么是问题

违反 CLAUDE.md rule 6 ("Fix the tool, never do the tool's job")。dispatcher 修复在 PR merge 后还需要人手 restart，本质上是人工补自动化的缺。每次改 lib/concerns/* 都要全员手动 restart 自己的 dispatcher，成本累积且容易遗漏。

## 期望

dispatcher 检测 lib/concerns/*.py（或更广的 lib/*.py）文件 mtime 变化时：
- 选项 A: 优雅退出（让 dispatcher launcher / systemd / supervisor 重启）
- 选项 B: 进程内 reload (importlib.reload + 重建 Concerns 实例)

选项 A 更稳但依赖 supervisor，选项 B 更快但 reload 边界容易踩坑。推荐先做 A，等用例积累后再考虑 B。

## 与现有的关系

- 相关 #226 #227（触发本 issue 的具体 case）
- 跟 #223 (lead 保活) 同组运维 issue，但维度不同（#223 是 idle nudge，本 issue 是 code reload）
- 不冲突 #160 (supervisor stall) — 那个是外部 supervisor，本 issue 是 internal dispatcher

## 实现思路

- bin/dispatcher 启动时记录 lib/concerns/__init__.py 等关键文件的 mtime
- 主 loop 周期检查 mtime，变化则触发选项 A 退出
- 详细 spec 等 owner 接手时定
