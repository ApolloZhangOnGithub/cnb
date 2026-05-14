---
allowed-tools: Bash(board overview), Bash(board --as ${ME} inbox), Bash(board --as ${ME} view), Bash(board --as ${ME} inspect *)
description: 团队状态总览 — 谁在干什么、进展如何、有无阻塞
---

用户问"团队怎么样"/"进展如何"/"谁在干什么"/"有什么消息" 等，根据意图组合调用：

- **总览全局**: 调用 `/cnbx-board overview`
- **最新消息**: 调用 `/cnbx-board --as ${ME} inbox`
- **整体进度**: 调用 `/cnbx-board --as ${ME} view`
- **看某人**: 用户提具体名字时，调用 `/cnbx-board --as ${ME} inspect tasks <名字>`

汇总成一个简洁报告：谁在做什么、有什么进展、有无阻塞。不要逐条贴原始输出，要归纳提炼。
