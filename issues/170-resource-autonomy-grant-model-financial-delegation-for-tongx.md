---
number: 170
title: "Resource autonomy: grant-model financial delegation for tongxue"
state: OPEN
labels: ["enhancement", "phase:2", "experiment", "org-design"]
assignees: []
created: 2026-05-12
updated: 2026-05-12
---

# #170 Resource autonomy: grant-model financial delegation for tongxue

**State:** OPEN
**Labels:** enhancement, phase:2, experiment, org-design

---

## 问题

同学需要花真钱（GPU、API、服务）才能完成复杂任务，但 AI 不能有银行账户、不能签合同、不能承担法律责任。怎么在自主性和风控之间取平衡？

## 跨领域借鉴

这个问题人类社会解了几千年。六个通用原则：

1. **分配和花费分离** — 拨款的人不花钱，花钱的人不拨款
2. **用途绑定** — 军费不能买食物，科研基金不能买无关设备
3. **分级自主** — 小额自批、中额先花后报、大额先批后花、超额升级审批
4. **渐进信任** — 新同学小额度，交出好结果后增加
5. **审计是权利的对价** — 有花钱的权利就有记账的义务
6. **问责结果不问责过程** — 不管你选哪个 GPU provider，管你有没有交付成果

### 最佳参考模型：科研基金（Grant Model）

| 科研基金 | cnb 等价物 |
|---------|-----------|
| Funding agency | 用户 |
| Grant（课题经费） | 项目预算池 |
| PI（项目负责人） | lead 同学 |
| Grant amount | budget_usd |
| Progress report | daily report + resource ledger |
| Deliverable | 任务产出（代码、报告、结果） |
| Renewal based on results | progressive trust tier |

PI 模型的精髓：给你一笔钱和一个目标，怎么花你决定，但你要交付成果和财务报告。

### 其他参考领域

| 领域 | 借鉴点 |
|------|--------|
| **量化交易** | 风控层（单笔限额、日亏损上限、kill switch、fail closed）|
| **军队后勤** | 按任务分配资源、交战规则 = 硬约束 |
| **企业财务** | 审批矩阵（$100 自批 / $1000 主管批 / $10000 VP 批）|
| **建筑工程** | 按里程碑付款、变更单审批 |
| **医院** | 日常操作自主（开处方），大额预授权（手术）|

### 关于资本市场模式的思考

资本市场提供了一些有趣的机制，但需要审慎对待：

**可借鉴的：**
- **价格发现** — 资源的真实成本由市场决定，不是管理者拍脑袋。同学之间竞争 GPU 时间时，出价机制可以反映真实紧迫度
- **做市商** — 一个中心化的资源调度者持有库存、提供流动性。类似 dispatcher 的角色
- **期货/预约** — "我明天需要 4 小时 GPU" — 预约机制防止冲突

**需要警惕的：**
- **投机行为** — 同学囤积资源、炒作资源价格，偏离生产目的
- **不平等积累** — "富者越富"导致新同学永远拿不到资源
- **短期主义** — 资本市场天然奖励短期回报，但研究需要长期投入
- **零和博弈** — 同学之间不应该是竞争关系，而是协作关系。市场机制可能破坏团队信任

**结论：** 从资本市场借鉴定价和调度机制，但不引入竞争和投机。cnb 的同学是同事不是交易对手。

## 实现分层

### Phase 0：Demo 级（现在）

```toml
# ~/.cnb/resources/gpu.toml
[gpu]
provider = "runpod"
api_key = "rp_xxxxx"
budget_limit_usd = 80.0
alert_threshold_usd = 60.0
```

同学读 API key → 自主调用 → 记账到 ledger → 超限停止。

### Phase 1：Grant Model

```toml
[resource.project.lewm-demo]
objective = "复现 LeWorldModel PushT 结果"
budget_usd = 80.0
pi = "lead"
approved_categories = ["gpu", "api"]
approved_providers = ["runpod", "modal", "lambda"]

[resource.authority]
self_approve_limit = 10.0
report_after_limit = 30.0
pre_approve_above = 30.0

[resource.trust]
initial_tier = "new"
promotion_after = 3
tiers = { new = 50, proven = 200, senior = 500 }
```

```bash
board --as <name> resource request gpu 2h "训练 PushT epoch 50-100"
board --as <name> resource balance
board --as <name> resource ledger
```

### Phase 2：跨项目资源治理

- 多项目预算分配
- 项目间资源借调（需双方 PI 同意）
- 基于交付记录的 trust tier 升级
- 年度/季度预算审查

## 设计原则

1. **Fail closed** — 读不到配置、余额查询失败 → 拒绝花费，不是默认放行
2. **Ledger 不可伪造** — 花费记录是 append-only，同学不能修改历史
3. **透明** — 任何同学能查看项目 ledger，不存在秘密花费
4. **限额不是惩罚** — 同学被设计成在约束内运行，撞到限额 → 报告，不是绕过

## 与 demo #164 的关系

本 issue 的 Phase 0 是 #164 LeWorldModel 复现 demo 的前置基础设施。同学需要 GPU 资源才能完成训练。
