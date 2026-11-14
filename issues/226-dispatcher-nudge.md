---
number: 226
title: "Dispatcher nudge 应检查屏幕是否已有同样命令，避免重复塞"
state: CLOSED
labels: ["bug", "phase:1", "infra"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
closed: 2026-05-17
---

# #226 Dispatcher nudge 应检查屏幕是否已有同样命令，避免重复塞

**State:** CLOSED
**Labels:** bug, phase:1, infra

---

## 问题

NudgeCoordinator._try_inbox / _try_idle 在 tmux_send 前没有检查 tmux pane 屏幕上是否已经有未提交的同样命令。同学在思考/工作中收到 nudge，命令塞进 prompt 但没执行，下一次 nudge cooldown 过后又塞一次，结果屏幕显示：

\`\`\`
❯ /Users/.../board --as lead inbox
❯ /Users/.../board --as lead inbox
❯ /Users/.../board --as lead inbox
...
\`\`\`

## 期望

发命令前：capture-pane 最后几行，如果已经包含同样命令 prefix（如 \`board --as <name> inbox\`），直接 skip，本轮不再发。

## 实现思路

在 \`_try_inbox\`, \`_try_idle\` 里 tmux_send 之前加一个 \`_already_queued(sess, cmd)\` 检查：
- capture-pane 最后 5 行
- 如果包含 cmd 字符串（去掉路径前缀），return True 表示已有
- 已有就 skip

## 与 ROADMAP 的关系

属于运营基础。修今天看到的实际 bug。
