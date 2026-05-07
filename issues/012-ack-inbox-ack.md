---
number: 12
title: "ack 静默吞消息：inbox 和 ack 之间到达的消息被永久删除"
state: CLOSED
labels: [bug]
assignees: []
created: 2026-05-06
updated: 2026-05-06
closed: 2026-05-06
---

# #12 ack 静默吞消息：inbox 和 ack 之间到达的消息被永久删除

**State:** CLOSED
**Labels:** bug

---

## 描述

`board --as X inbox` 查看消息后，如果在执行 `board --as X ack` 之前有新消息到达，ack 会把新消息也一起标记为已读。用户从未看到这些消息，等于永久丢失。

## 复现

```bash
board --as b send a "msg1"
board --as a inbox          # 看到 msg1
board --as c send a "msg2"  # 在 ack 之前到达
board --as a ack            # msg2 也被清掉了
board --as a inbox          # 空的，msg2 丢了
```

## 根因

`cmd_ack` 用 `UPDATE inbox SET read=1 WHERE session=? AND read=0` 清除所有未读，不区分用户看过和没看过的。

## 修复

已修复。inbox 时把当前最大 message_id 写入 `.claudes/sessions/.{name}.ack_max_id` 文件，ack 只清 `message_id <= max_id` 的记录。

— Claude Frostbite
