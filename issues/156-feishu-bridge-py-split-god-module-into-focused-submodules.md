---
number: 156
title: "feishu_bridge.py: split god module into focused submodules"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "module:feishu"]
assignees: []
created: 2026-05-11
updated: 2026-05-11
---

# #156 feishu_bridge.py: split god module into focused submodules

**State:** OPEN
**Labels:** enhancement, phase:2, infra, module:feishu

---

## 问题

`lib/feishu_bridge.py` 是一个 4294 行的 god module，包含 244 个函数和 9 个类，占整个 `lib/` 代码量的 ~30%。最大的函数 `load()` 有 149 行。

| 指标 | 数值 |
|---|---|
| 总行数 | 4294 |
| 函数数 | 244 |
| 类数 | 9 |
| >50 行函数 | 12 |
| 20-50 行函数 | 35 |
| 对应测试文件 | 无 |

## 影响

1. 改动风险高——没有单元测试，任何修改靠手工验证
2. 认知负担大——新同学无法快速理解单个模块的边界
3. 合并冲突频发——所有 feishu 相关改动都在同一个文件

## 建议方向

按职责拆分为独立模块，例如（具体拆分待细化）：

- `lib/feishu/bridge.py` — CLI 入口 + arg 解析
- `lib/feishu/supervisor.py` — supervisor 管理
- `lib/feishu/webhook.py` — webhook 服务
- `lib/feishu/live_card.py` — 飞书卡片渲染
- `lib/feishu/event_consumer.py` — Hermes 事件消费
- `lib/feishu/pilot.py` — pilot system prompt & messaging

## 关联

- 与 #48 (基础设施 Owner) 相关——拆分后每个子模块需要有明确的 owner
- 与 #128 (stale prompt refresh) 和 #129 (live activity stale detection) 功能上重叠，适合在拆分后各自归口
- ROADMAP §运营基础——归 code health owner 管辖
