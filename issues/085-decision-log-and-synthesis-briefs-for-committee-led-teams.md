---
number: 85
title: "Decision log and synthesis briefs for committee-led teams"
state: CLOSED
labels: ["enhancement", "phase:2", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #85 Decision log and synthesis briefs for committee-led teams

**State:** CLOSED
**Labels:** enhancement, phase:2, org-design

---

## 背景

这是 #79 和 #81 的配套任务。团队规模到 10-15 个 session 后，chief / committee 不应该阅读所有原始消息和材料，而应该依赖可审计的 synthesis brief 和 decision log。

否则 cnb 只能记录“谁说了什么”，不能记录“组织最终决定了什么”。

## 问题

当前 cnb 有 messages、mail、daily、proposals/votes 等基础，但缺少面向执行组织的决策记录：

- 这个研究/项目当前采用哪个口径？
- 哪个争议被 chief 定了？
- 哪个结论被 QA 驳回？
- 哪个工作组 brief 被吸收到最终报告？
- 哪个历史决策覆盖了后续 task？

如果没有 decision log，团队越大，越容易回到群聊式协作。

## 建议模型

```text
decisions(
  id,
  team_id,
  org_unit_id,
  decision_key,
  title,
  body,
  decided_by_role,
  decided_by_session,
  status,          # active / superseded / rejected
  supersedes_id,
  created_at
)

synthesis_briefs(
  id,
  team_id,
  org_unit_id,
  author_role,
  title,
  summary,
  included_artifacts,
  open_questions,
  recommended_decisions,
  status
)
```

## 命令草案

```bash
cnb team brief submit <team> --unit education --file notes/briefs/edu.md
cnb team brief list <team>
cnb team decide <team> --key school-tier-taxonomy --from-brief <brief-id>
cnb team decisions <team>
cnb team decision supersede <decision-id> --with <new-decision-id>
```

## 使用场景

研究团队中：

- education-bg 提交“本科/职校/留学分层 brief”。
- province-bg 提交“省份流动类型 brief”。
- QA 对证据做 accept/reject。
- chief 把通过 QA 的 brief 收敛成 decision。
- 后续 task 依赖 decision，而不是重新争论口径。

工程团队中：

- design group 提交方案 brief。
- review gate 通过后，lead 记录 architecture decision。
- 后续 owner 按 decision 执行。

## 验收标准

- 能提交 synthesis brief，并关联 org_unit 和 artifact。
- 能从 brief 生成或手动创建 decision。
- decision 能标记 active / superseded / rejected。
- dashboard 能显示 team 当前 active decisions。
- task 能引用 decision id 作为执行依据。
- docs 说明 decision 与普通 message/mail/proposal 的区别。
