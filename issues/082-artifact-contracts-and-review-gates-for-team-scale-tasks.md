---
number: 82
title: "Artifact contracts and review gates for team-scale tasks"
state: CLOSED
labels: ["enhancement", "phase:2", "infra", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #82 Artifact contracts and review gates for team-scale tasks

**State:** CLOSED
**Labels:** enhancement, phase:2, infra, org-design

---

## 背景

这是 #79 的交付和质量控制拆分任务。大团队任务不能只有一句 description。每个任务都应该明确交付什么 artifact，并通过对应 review gate。

对研究型项目尤其重要：否则 10-15 个 session 会产出一堆散文，主编和 QA 无法判断哪些材料能进入结论。

## 问题

当前 task 字段主要是：session、description、status、priority。它能表达“谁在做什么”，但不能表达：

- 任务必须交付什么文件或结构化数据？
- 交付物类型是什么？source card、matrix、brief、code patch、test evidence？
- 哪个 review gate 负责验收？
- QA 是接受、驳回，还是要求修改？
- 哪些结论已通过证据审计？

## 建议模型

```text
artifact_contracts(
  id,
  team_id,
  contract_key,
  output_type,
  required_fields,
  output_path_pattern,
  verification_command,
  evidence_rules
)

artifacts(
  id,
  task_id,
  contract_id,
  path_or_url,
  submitted_by,
  submitted_at,
  status
)

review_gates(
  id,
  team_id,
  gate_key,
  reviewer_role,
  required_for_output_types
)

reviews(
  id,
  artifact_id,
  gate_id,
  reviewer_session,
  decision,          # accept / reject / request_changes
  notes,
  decided_at
)
```

## 命令草案

```bash
cnb team contract add <team> source-card --output-type source_card
cnb team task add <team> --role edu_vocational --contract source-card "..."
cnb team artifact submit <task-id> notes/evidence/...
cnb team review request <artifact-id> --gate qa_evidence
cnb team review accept <artifact-id> --gate qa_evidence
```

## 研究任务示例

```text
任务：整理职校体系公开数据源
contract：source_card_set
要求：区分中职、技工、高职、职业本科；每类至少 3 个来源；估算标 D 级
review_gate：qa_evidence
```

## 验收标准

- task 可以绑定 artifact_contract。
- artifact 可以从 task 提交。
- review gate 可以记录 accept / reject / request_changes。
- dashboard 能显示待 review artifact。
- `task done` 前可以检查必需 artifact 是否存在且 review gate 已通过。
- docs 说明 artifact contract 和普通附件的区别。
