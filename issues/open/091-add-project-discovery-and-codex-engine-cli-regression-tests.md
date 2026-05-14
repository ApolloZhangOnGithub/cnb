---
number: 91
title: "Add project discovery and Codex engine CLI regression tests"
state: OPEN
labels: ["phase:1", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #91 Add project discovery and Codex engine CLI regression tests

**State:** OPEN
**Labels:** phase:1, infra

---

## 背景

近期新增了 terminal supervisor 项目发现、marker discovery mode、Codex engine 启动路径和 `bin/cnb` 多子命令分发。已有测试覆盖了不少函数级行为，但 public CLI/command contract 仍偏薄。

## 需要补的测试

- `cnb projects scan --json/--register/--mode marker/--no-legacy` 的 CLI-level 输出和 registry 写入。
- git/tmux summary command timeout/OSError 时 discovery 仍 graceful degradation。
- marker-only project 不被 register，但在 marker audit 中可见。
- Codex launch command 的 permission flags、`CNB_AGENT=codex`、`SWARM_AGENT=codex` 路径保持一致。
- `bin/cnb` 新增子命令和 docs/README 中命令示例的 parser contract。
- 测试必须隔离 HOME/CNB_PROJECT，避免复发 #77 中的真实 `~/.cnb` 污染。

## Acceptance criteria

- 至少新增一组 CLI-level tests，不只测 internal helper。
- 外部命令使用 fake subprocess，不依赖本机 tmux/git 状态。
- 相关测试和全量 CI 门禁通过。

## Parent

Part of #88. Related to #77.
