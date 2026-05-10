---
number: 84
title: "Dogfood research pilot: young talent flow as the first team-organization sample"
state: CLOSED
labels: ["phase:2", "experiment", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #84 Dogfood research pilot: young talent flow as the first team-organization sample

**State:** CLOSED
**Labels:** phase:2, experiment, org-design

---

## 背景

这是 #79-#83 的 dogfood 任务。年轻人才流向研究已经足够复杂，适合作为 cnb 团队组织层的第一个真实样本。

不要把这次研究硬编码进 cnb；它只是一个 TeamInstance / Template 的验证案例。

## Pilot 目标

用 cnb 管理一个中等规模研究团队，验证：

```text
committee -> platform -> working groups -> artifact contracts -> review gates -> synthesis
```

是否能跑通。

## 建议 TeamInstance

```text
young-talent-flow-pilot
```

建议组织：

```text
committee
  chief
  ops
  qa

platform
  evidence
  schema

education-bg
  undergrad
  vocational
  degree-oversea

province-bg
  education-flow
  industry-flow

company-entry-bg
  internet-toc
  internet-tob
  iot-toc
  iot-tob

mobility-bg
  internal-flow
  startup-ecosystem
```

这只是实例，不是产品默认配置。

## Pilot 研究边界

不要一上来覆盖全国。先做最小可验证底图：

- 字段字典：本科高校、职校、社会劳动力、学历/留学、省份、岗位族、组织入口。
- 证据源清单：国家级数据源、3-5 个重点省份、学校就业质量报告、公开招聘源。
- 三张样表：cohort_profile、org_entry_profile、flow_edge。
- QA 规则：D 级估算不得写成事实；每个关键判断必须有证据等级。

## 需要验证的 cnb 能力

- committee-first workflow 是否真的减少混乱。
- role slot 是否比写死 session 名更稳。
- artifact contract 是否防止研究产出散文化。
- review gate 是否能把 QA 从口头提醒变成流程。
- dashboard 是否能显示 team/org_unit 维度的真实进展。
- daily/handoff 是否能支撑 role 换人和活水。

## 成功标准

- 不需要用户人工追问每个人“你研究到哪了”。
- chief 只需要看 synthesis brief 和 rejected artifacts，不需要读所有原始材料。
- QA 可以明确拦截不合格证据。
- 每个工作组都有 output_path，而不是只发消息。
- pilot 结束后能产出 `research-org-v1` 或类似 team template 候选。

## 输出

- cnb dogfood 复盘：哪些组织对象必要，哪些是过度设计。
- 一份可复用 research team template 草案。
- 对 #79-#83 的实现反馈。
