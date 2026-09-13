---
number: 215
title: "board send 应在接收方离线时提示发送者"
state: CLOSED
labels: ["enhancement", "phase:1", "infra"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
closed: 2026-05-17
---

# #215 board send 应在接收方离线时提示发送者

**State:** CLOSED
**Labels:** enhancement, phase:1, infra

---

## 问题

`board --as lead send all "消息"` 在所有接收方都离线（tmux session 不存在）时，仍然返回 `OK sent`，没有任何提示。发送者以为消息已送达，实际上没人在线能看到。

## 期望行为

- 发送成功但接收方不在线时，输出警告：`OK sent (⚠ 以下同学离线: bezos, musk, ...)`
- 所有接收方都离线时，加重警告：`OK sent (⚠ 全员离线，无人能即时收到)`
- 消息仍然正常写入 inbox（上线后能看到），但发送者知道没人当前在看

## 不做

- 不阻止发送（消息仍入库）
- 不做消息投递确认（过度设计）

## 与 ROADMAP 的关系

属于运营基础，board 系统可靠性增强。与现有 issue 无直接重叠。
