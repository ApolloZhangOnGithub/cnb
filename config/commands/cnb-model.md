---
allowed-tools: Bash(cnb m), Bash(cnb m *)
description: 模型管理 — 查看当前、列出可用、切换 provider
---

用户说"看模型"/"当前是什么"/"有哪些"/"切 ds"/"切 deepseek"/"换 default" 等，理解意图后执行：

- **查看当前**: 调用 `/cnbx-model current`
- **列出可用**: 调用 `/cnbx-model list`
- **切换**: 调用 `/cnbx-model <profile>`（如 `d` → deepseek, `a` → anthropic）

如果用户只说"模型"没给明确意图，默认显示当前 + 可用列表。
