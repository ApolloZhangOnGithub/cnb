---
number: 80
title: "Role slots: decouple organizational responsibility from running sessions"
state: CLOSED
labels: ["enhancement", "phase:2", "ownership", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #80 Role slots: decouple organizational responsibility from running sessions

**State:** CLOSED
**Labels:** enhancement, phase:2, ownership, org-design

---

## 背景

这是 #79 的拆分任务。当前 cnb 的强项是 session 和 ownership，但大团队里“职责”和“正在运行的同学”不能等同。

一个 role 可以暂时没人，一个 session 可以临时兼多个 role，一个 role 也可以在任务变大时拆给多个 session。

## 问题

如果继续把 session 当职责，会出现：

- 人名/会话名被写进组织设计，无法复用。
- session 重启或更换后，职责连续性依赖人工日报。
- 一个临时补位 session 很难表达“我只是代班”。
- dashboard 只能看到谁在线，看不到哪个职责缺人。
- ownership 只能偏向路径/模块，不能表达委员会职责、研究职责、审核职责。

## 建议模型

```text
role_slots(
  id,
  team_id,
  org_unit_id,
  role_key,
  title,
  responsibility,
  expected_outputs,
  status
)

session_assignments(
  id,
  team_id,
  role_slot_id,
  session,
  assignment_type,   # primary / deputy / temporary / observer
  started_at,
  ended_at
)
```

## 命令草案

```bash
cnb team role add <team> <org-unit> <role-key> --title "..."
cnb team assign <team> <role-key> --to <session>
cnb team unassign <team> <role-key> --from <session>
cnb team roles <team>
cnb team vacancies <team>
```

## 行为要求

- 一个 role slot 可以没有 session，但必须在 dashboard 中显示为空缺。
- 一个 session 可以承担多个 role，但 dashboard 要显式展示，不要藏在 status 文本里。
- role handoff 要落到 daily/handoff，而不是只发消息。
- task owner 优先绑定 role，再由当前 session assignment 执行。

## 验收标准

- 能在一个 team 内定义至少 3 个 role slot。
- 能把同一个 session 绑定到两个 role。
- 能把一个 role 从 A session 转给 B session，并保留历史。
- `team dashboard` 能展示 role -> session 的当前映射和空缺。
- task 可以显示 owner_role 和 current_session 两个字段。
