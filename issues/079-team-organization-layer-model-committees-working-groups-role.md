---
number: 79
title: "Team organization layer: model committees, working groups, role slots, and team instances"
state: OPEN
labels: ["enhancement", "phase:2", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #79 Team organization layer: model committees, working groups, role slots, and team instances

**State:** OPEN
**Labels:** enhancement, phase:2, org-design

---

## 背景

这件事来自一次外部研究项目的 dogfood：当研究难度上升到 10-15 个 AI session 时，cnb 当前的个人/小队 board 不够用了。但这个需求不应该污染 cnb 仓库，不能拆成一堆分散 issue，也不能把某个 15 人团队写死进产品。

本 issue 作为唯一总 issue，整合此前关于 team organization、role slots、committee-first workflow、artifact contracts、review gates、team templates、decision log、research pilot 的讨论。

关联：#64、#76。

## 核心问题

当前 cnb 已经有 session、message/inbox、status、task、ownership、mail、pending、daily、dashboard 等协作原语，适合单人或小队协作。

但复杂团队需要先成立委员会/小组，再根据具体研究或项目实例化组织。现在 cnb 还不能直接回答：

- 谁属于哪个委员会或工作组？
- 哪个工作组负责哪个问题域？
- 哪个 role 空缺？
- 哪个 session 只是临时坐在某个 role slot 上？
- 哪个 task 属于哪个 team / org unit / role？
- 哪个交付物应该进入哪个 review gate？
- 哪个结论已经被 chief / QA 接受？
- 哪个决策覆盖了后续任务？

这些目前只能靠命名约定、README、日报和人工理解。

## 设计原则

```text
team 是组织实例，不是 session 列表
role 是职责槽位，不是运行中的 session
org_unit 是组织边界，不是聊天室
task 必须有 owner_role 和 output，不只是自由文本
artifact 是交付物，不是可有可无的附件
review gate 是流程，不是口头提醒
decision 是组织记忆，不是消息历史
```

## 建议对象

最小组织层可以先包含：

```text
TeamTemplate      # 可复用组织蓝图
TeamInstance      # 某个项目里的团队实例
OrgUnit           # committee / platform / working_group / review_group
RoleSlot          # chief / ops / qa / evidence / schema / researcher 等职责槽位
SessionAssignment # 当前哪个 session 坐在哪个 role 上
ArtifactContract  # 任务必须交付什么
ReviewGate        # 谁审核、如何通过/驳回
DecisionLog       # 委员会最终决定
SynthesisBrief    # 工作组给 chief 的综合简报
```

## Committee-first workflow

复杂项目不应直接启动一堆 session，而应先建治理小组：

```text
1. create team instance
2. create committee
3. define mission / scope / evidence rules
4. define org units and role slots
5. define artifact contracts and review gates
6. assign sessions
7. start execution
8. collect synthesis briefs
9. record decisions
```

委员会最小角色：

```text
chief：决定问题口径、最终判断、发布范围
ops：维护任务流、依赖、阻塞、日报和交接
qa/redteam：审计证据、反证、阻止不合格结论进入成果
```

## 命令草案

先做最小可用命令，不做复杂 HR/权限系统：

```bash
cnb team template list
cnb team create <team> --template research-org-v1
cnb team unit add <team> committee --type committee
cnb team role add <team> committee chief
cnb team assign <team> chief --to <session>
cnb team task add <team> --unit education --role researcher --contract source-card "..."
cnb team artifact submit <task-id> <path>
cnb team review request <artifact-id> --gate qa_evidence
cnb team decision add <team> --key school-tier-taxonomy --from-brief <brief-id>
cnb team dashboard <team>
```

## Dogfood 样本，不写死

“年轻人才流向研究”可以作为第一个样本，但只能作为 TeamInstance / Template 验证案例，不能写死进 cnb。

可能的 pilot：

```text
young-talent-flow-pilot

committee: chief / ops / qa
platform: evidence / schema
education-bg: undergrad / vocational / degree-oversea
province-bg: education-flow / industry-flow
company-entry-bg: internet-toc / internet-tob / iot-toc / iot-tob
mobility-bg: internal-flow / startup-ecosystem
```

这个样本用于验证：

- role slot 是否比写死 session 名稳定。
- artifact contract 是否防止研究产出散文化。
- review gate 是否能把 QA 从口头提醒变成流程。
- chief 是否只看 synthesis brief，而不是读所有原始材料。
- pilot 结束后是否能提炼出 `research-org-v1` 模板。

## 非目标

- 不拆成多个 issue 追踪。
- 不做完整 HR/组织图产品。
- 不做复杂权限系统。
- 不要求自动调度先上线。
- 不把某次研究团队写死为默认配置。
- 不打断 #64/#76 的既有组织改革主线。

## 最小验收标准

- 一个 repo 内可以声明至少一个 team instance。
- team instance 可以包含 committee / platform / working_group 等 org unit。
- org unit 可以包含 role slots。
- session 可以绑定到一个或多个 role slot。
- task 可以绑定 team / org_unit / owner_role / artifact_contract。
- dashboard 能显示 role 空缺、活跃 role、待 review artifact。
- review gate 可以记录 accept / reject / request_changes。
- decision log 能记录当前 active decision。
- 文档说明：session 是执行者，role slot 是职责，team instance 是组织实例。

## 收敛说明

此前拆出的 #80-#85 已合并回本 issue，避免给 cnb 原项目制造过多 issue 噪音。
