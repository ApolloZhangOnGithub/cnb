---
number: 13
title: "tmux send-keys 在 shell 未就绪时发命令，导致命令堆积重复执行"
state: CLOSED
labels: ["bug"]
assignees: []
created: 2026-05-06
updated: 2026-05-06
closed: 2026-05-06
---

# #13 tmux send-keys 在 shell 未就绪时发命令，导致命令堆积重复执行

**State:** CLOSED
**Labels:** bug

---

## 描述

`swarm start` 创建 tmux session 后立即用 `send-keys` 发送 `source ~/.zshrc && cd ... && claude ...`。但 shell 可能还没初始化完，命令堆积在 terminal input buffer 里，导致 `source` 完成后剩余命令被 echo 但执行顺序混乱。

## 复现

```bash
swarm start b
# tmux pane 里可以看到 source/cd/claude 的 echo 出现多次
```

## 根因

`tmux_start_one` 在 `new-session` 后没等 shell prompt 出现就用 `send-keys` 发命令。shell 的 input buffer 会缓存所有输入，但处理顺序取决于 shell 初始化时机。

## 修复

已修复。加了 `_wait_for_shell()` 函数，创建 session 后轮询 pane 等 `$`/`%`/`❯` 出现再发命令。`source` 和 `cd` 合并为一条命令，之后再等一次 shell ready 才发 `claude`。

— Claude Frostbite
