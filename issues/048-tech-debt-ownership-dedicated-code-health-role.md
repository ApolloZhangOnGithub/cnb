---
number: 48
title: "Tech debt ownership: dedicated code health role"
state: OPEN
labels: ["phase:1", "infra", "priority:p0"]
assignees: []
created: 2026-05-08
updated: 2026-05-10
---

# #48 Tech debt ownership: dedicated code health role

**State:** OPEN
**Labels:** phase:1, infra, priority:p0

---

## Summary

项目开发了一段时间，技术债会自然积累。当前没有明确的同学负责工程化和代码健康——ruff 规则更新、测试覆盖率监控、migration 一致性、依赖安全更新等没人盯。

## ROADMAP 关系

与 Phase 2 全局管理 (#42) 有交集（巡检部分），但 #42 侧重跨项目运维，本 issue 侧重项目内代码质量。不重叠。

## 具体问题

1. **无人巡检代码质量**：ruff 规则、mypy 配置、测试覆盖率没有定期检查
2. **依赖腐化**：没有同学负责检查过时的依赖、安全漏洞
3. **migration 一致性**：schema.sql 和 migrations/ 可能漂移，没有自动校验
4. **测试残留**：~/.cnb/projects.json 有 1510 条 pytest 残留，说明测试 cleanup 不到位

## 方案

- 指定一个同学（或角色）为"code health owner"，相当于 platform team / SRE
- 职责：定期 ruff audit、测试覆盖率报告、依赖更新、migration 校验
- 可以做成 `board scan --health` 或 `cnb doctor --deep` 的扩展
- 长期：集成到 CI，每次 push 自动检查

## 不做什么

- 不新建独立工具，优先扩展 `bin/doctor`
