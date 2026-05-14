---
number: 81
title: "Committee-first workflow: form governance groups before spawning work units"
state: CLOSED
labels: ["enhancement", "phase:2", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #81 Committee-first workflow: form governance groups before spawning work units

**State:** CLOSED
**Labels:** enhancement, phase:2, org-design

---

## 背景

这是 #79 的组织流程拆分任务。复杂研究或复杂工程不应该直接启动一堆 session，而应该先成立一个小型委员会，确定口径、边界、评审规则和工作组划分，再实例化执行组织。

这不是给某个项目写死管理层，而是给 cnb 一个通用 workflow。

## 问题

当前 cnb 可以启动 session、分配 task、发消息，但缺少“先治理、再执行”的流程。结果是：

- 大任务一开始就被拆给多人，口径还没定。
- QA 和主编角色混在执行里，没人独立拦错。
- 工作组职责边界靠口头约定。
- 后续研究越多，材料越难综合。

## 建议流程

```text
1. create committee
2. define mission / scope / evidence rules
3. define org units and role slots
4. define artifact contracts and review gates
5. instantiate work units
6. assign sessions
7. start execution
```

## 命令草案

```bash
cnb team create <team> --template research-org-v1
cnb team committee add <team> steering --roles chief,ops,qa
cnb team unit add <team> education --type research_bg
cnb team unit add <team> evidence --type platform
cnb team gate add <team> qa_evidence --reviewer-role qa
cnb team start <team>
```

## 委员会的最小职责

- chief：决定问题口径、最终判断、发布范围。
- ops：维护任务流、依赖、阻塞、日报和交接。
- qa/redteam：审计证据、反证、阻止 D 级估算伪装事实。

## 非目标

- 不做复杂投票制度。
- 不要求委员会成员必须是固定 session。
- 不替代现有 lead/terminal supervisor 设计。

## 验收标准

- 可以创建 committee 类型 org unit。
- committee 可以定义 role slots。
- team start 前可以检查必需 committee roles 是否已分配。
- dashboard 能区分 committee、platform、research/work units。
- docs 给出一个“先成立委员会，再实例化工作组”的端到端示例。
