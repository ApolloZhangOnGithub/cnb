---
allowed-tools: Bash(cat ~/.cnb/live_state.json *), Bash(ps aux *), Bash(ls *), Bash(cat ~/.cnb/config.toml *)
description: 机器主管状态 — 设备端 cnb 运行面是否正常
---

用户问"机器主管怎么样"/"supervisor 状态"/"设备端" 时，调用 `/cnbx-supervisor` 获取原始数据，汇总成简洁报告：

- 机器主管是否在线（live_state 的 updatedAt 是否新鲜）
- Mac Companion 进程是否运行
- 飞书 bridge 进程是否运行
- 最近日报
- 有无异常

注意：机器主管（device supervisor）≠ 项目 lead。机器主管管整台机器的 cnb 运行面。
