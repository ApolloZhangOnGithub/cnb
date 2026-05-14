---
allowed-tools: Edit(.*settings.json)
description: 快捷配置 — effort 等级、权限模式等
---

用户说"effort max"/"bypass"/"看一下配置" 等，根据意图执行：

**effort**（"effort"/"努力程度"）: 查看或修改 `.claude/settings.json` 中 `env.CLAUDE_CODE_EFFORT_LEVEL`，默认 max。重启后生效。

**permission**（"bypass"/"权限"/"免确认"）: 设置 `permissions.defaultMode = "bypassPermissions"`，或删除该字段恢复默认。重启后生效。

**无参数**: 显示当前 effort + permission 配置摘要。
