---
number: 83
title: "Team templates and instance commands for reusable org design"
state: CLOSED
labels: ["enhancement", "phase:2", "infra", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #83 Team templates and instance commands for reusable org design

**State:** CLOSED
**Labels:** enhancement, phase:2, infra, org-design

---

## 背景

这是 #79 的实例化机制拆分任务。团队组织不能写死为某一次 15 人研究组，而应该通过 template -> instance 的方式生成。

同一套 cnb 应该能实例化研究团队、代码团队、数据团队、审稿团队、产品团队，而不是每次重新写命名规范。

## 问题

如果只有 session 配置和 README 约定：

- 研究组、代码组、审稿组的结构无法复用。
- 新项目启动时无法快速生成 committee、platform、work units、role slots。
- 组织设计散落在文档里，工具无法检查缺人、缺 task、缺 artifact。
- 好的团队结构无法沉淀为样本。

## 建议能力

```text
TeamTemplate：可复用组织蓝图
TeamInstance：在某个 repo/project 中实例化出来的团队
OrgUnit：committee/platform/research_bg/engineering_group/review_group 等
RoleSlot：chief、ops、qa、schema、evidence、worker 等
```

## 命令草案

```bash
cnb team template list
cnb team template show research-org-v1
cnb team create young-talent-flow --template research-org-v1
cnb team view young-talent-flow
cnb team units young-talent-flow
cnb team roles young-talent-flow
cnb team archive young-talent-flow
```

## 模板存储草案

可以先用 repo-local 文件，不必一开始做复杂 registry：

```text
.cnb/team_templates/research-org-v1.yml
.cnb/teams/young-talent-flow.yml
```

或进入 SQLite，但需要导出/导入能力，方便复用。

## 示例模板

```yaml
id: research-org-v1
units:
  - id: committee
    type: committee
    roles: [chief, ops, qa]
  - id: platform
    type: platform
    roles: [evidence, schema]
  - id: research
    type: working_group
    roles: [researcher]
gates:
  - id: qa_evidence
    reviewer_role: qa
```

## 验收标准

- 能列出可用 team templates。
- 能从 template 创建 team instance。
- team instance 可以被 view/dashboard 读取。
- template 不绑定具体 session 名。
- role assignment 在 instance 层发生，不污染 template。
- docs 给出如何把一次成功 pilot 提炼成 template 的规则。
