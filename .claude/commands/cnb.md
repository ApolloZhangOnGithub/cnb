---
allowed-tools: Bash(board overview), Bash(board --as bezos inbox), Bash(board --as bezos view), Bash(board --as bezos pending list), Bash(cat ~/.cnb/live_state.json *), Bash(ps aux *), Bash(ls *), Bash(cat ~/.cnb/config.toml *)
description: 总入口 — 自动评估全局状态，调用所有工具，给出综合报告
---

用户输入 `/cnb`（无参数），你需要一次性做全面的团队 + 系统体检：

**第一步：收集数据**（并行调用）
1. 团队总览：`/cnbx-board overview`
2. 收件箱：`/cnbx-board --as bezos inbox`
3. 任务看板：`/cnbx-board --as bezos view`
4. 待处理操作：`/cnbx-board --as bezos pending list`
5. 机器主管状态：`/cnbx-supervisor`

**第二步：综合报告**

汇总成一个简洁报告，不求逐条罗列，要提炼关键：

- **团队概览**：谁在线、在做什么
- **最近动态**：有什么新消息/进展
- **需要你动手的**：高亮 `!` 开头的手动命令
- **系统状态**：机器主管是否正常
- **建议**：有没有值得关注的问题（阻塞、异常、过期任务）

报告要短，一屏能看完。不要贴原始输出。
