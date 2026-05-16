---
number: 157
title: "Add test coverage for 28 untested lib modules"
state: OPEN
labels: ["enhancement", "phase:2", "infra"]
assignees: []
created: 2026-05-11
updated: 2026-05-11
---

# #157 Add test coverage for 28 untested lib modules

**State:** OPEN
**Labels:** enhancement, phase:2, infra

---

## 问题

53 个 lib 模块中，28 个没有对应的测试文件。虽然项目有 1544 个测试且全部通过，但覆盖严重不均。

### 无测试覆盖的模块（按行数排序）

| 模块 | 行数 |
|---|---|
| `feishu_bridge.py` | 4294 |
| `board_own.py` | 725 |
| `swarm.py` | 606 |
| `global_registry.py` | 605 |
| `cnb_sync_gateway.py` | 492 |
| `board_view.py` | 410 |
| `capture_ingest.py` | 388 |
| `resources.py` | 349 |
| `github_app_guard.py` | 267 |
| `board_pending.py` | 281 |
| `swarm_backend.py` | 281 |
| `shutdown.py` | 235 |
| `board_maintenance.py` | 236 |
| `board_msg.py` | 242 |
| `board_mailbox.py` | 231 |
| `board_task.py` | 225 |
| `board_model.py` | 224 |
| `board.py` | — |
| `board_bugs.py` | — |
| `board_gitlock.py` | — |
| `board_messaging.py` | — |
| `board_tasks.py` | — |
| `board_voting.py` | — |
| `concern_base.py` | — |
| `dispatcher.py` | — |
| `ownership.py` | — |
| `nudge_coordinator.py` | — |
| `secret_scan.py` | — |

## 影响

1. 改动核心模块（尤其 feishu_bridge）没有自动化安全网
2. 重构阻力大——不知道改了什么会影响什么
3. 新同学贡献门槛高——没有测试用例做参考

## 建议

- 不要求一次性全覆盖，按风险优先级分批
- 优先覆盖改动频繁、风险高的模块（feishu_bridge、swarm、board_own）
- 安装 `pytest-cov` 并设定最低覆盖率门槛，防止回退
- 新模块要求必须带测试

## 关联

- 与 #48 (基础设施 Owner) 直接相关——测试覆盖率应归 code health owner 管辖
- 与「feishu_bridge 拆分」issue 联动——拆分后的子模块应各自带测试
- 与 #134 (engineering stabilization sprint) 方向一致
- ROADMAP §运营基础——归 code health owner 管辖
