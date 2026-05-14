---
allowed-tools: Bash(board overview), Bash(board --as ${ME} inbox), Bash(board --as ${ME} view), Bash(board --as ${ME} pending list), Bash(cat ~/.cnb/live_state.json *), Bash(ps aux *), Bash(ls *), Bash(cat ~/.cnb/config.toml *)
description: 总入口 — 自动评估全局状态，调用所有工具，给出综合报告
---

用户输入 `/cnb`（无参数），你需要一次性做全面的团队 + 系统体检。

第一步：并行收集数据 — 调用 `/cnbx-board overview`、`/cnbx-board --as ${ME} inbox`、`/cnbx-board --as ${ME} view`、`/cnbx-board --as ${ME} pending list`、`/cnbx-supervisor`。

第二步：汇总成简洁报告，不求逐条罗列，要提炼关键：

- **团队概览**：谁在线、在做什么
- **最近动态**：有什么新消息/进展
- **需要你动手的**：高亮 `!` 开头的手动命令
- **系统状态**：机器主管是否正常
- **建议**：有没有值得关注的问题（阻塞、异常、过期任务）

报告要短，一屏能看完。不要贴原始输出。
