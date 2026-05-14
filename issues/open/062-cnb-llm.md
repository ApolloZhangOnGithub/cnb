---
number: 62
title: "探索：cnb 作为 LLM 行为研究实验平台"
state: OPEN
labels: ["enhancement", "experiment"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #62 探索：cnb 作为 LLM 行为研究实验平台

**State:** OPEN
**Labels:** enhancement, experiment

---

## 背景

在设计 tongxue 认知指纹（#60 讨论）时发现：这类 LLM 多 agent 行为实验，市面上没有合适的框架。cnb 天然具备多 session 并行、session 间通信、任务调度、持久身份——恰好是 LLM 复杂实验所需的基础设施。

## cnb 已有的实验能力

- 多 session 并行管理（tmux 隔离）
- session 间通信（board 消息总线）
- 任务分配与状态追踪
- 持久身份与日报系统（长周期观察）

## 还需要的变种能力

| 能力 | 用途 |
|------|------|
| 沙箱隔离 | 实验不污染生产环境 |
| 环境镜像/快照 | 可复现的实验初始状态 |
| 大规模并行 (50+ session) | 统计显著性 |
| 可调参 (temperature, model, prompt) | 控制实验变量 |
| 数据采集管线 | 结构化收集实验数据 |

## 定位

这是 cnb 的变种用途，不是核心使命。但如果能兼任，就是市面上唯一一个同时解决"多 agent 协作管理"和"多 agent 行为实验"的框架。

## 可能的研究场景

- LLM 认知指纹（#60）
- 多 agent 协作效率 vs 团队规模的 scaling law
- 不同 persona 对任务完成质量的影响
- 上下文压力下的能力退化曲线
- tongxue 间信息传递的损耗率

不急，先记录。

— ritchie
