---
number: 88
title: "Testing roadmap: post-update regression matrix for local-first features"
state: OPEN
labels: ["phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
---

# #88 Testing roadmap: post-update regression matrix for local-first features

**State:** OPEN
**Labels:** phase:1, infra, priority:p1

---

## 背景

近期项目新增和重写了多个 local-first 能力面：

- web capture ingest protocol (`lib/capture_ingest.py`, `cnb capture`)
- Feishu `local_openapi` webhook/reply/setup/watch path (`lib/feishu_bridge.py`)
- global project discovery and marker mode (`lib/global_registry.py`, `cnb projects scan`)
- Codex engine launch path and terminal supervisor flow (`bin/cnb`, `lib/swarm.py`, `lib/swarm_backend.py`)
- daily/shutdown/ownership handoff related operational paths

现有测试数量很多，但新增能力的风险面已经从“函数单元行为”扩展到：本地文件系统持久化、SQLite board 集成、外部 CLI/OpenAPI 失败、全局 `~/.cnb` 隔离、tmux 命令构造、跨命令 CLI round trip。需要把测试集合从“功能点可用”升级为“更新后回归矩阵”。

## 需要补的测试层级

1. **Unit edge cases**：无效输入、缺字段、重复 id、fallback、timeout、corrupt JSON/TOML。
2. **Local integration**：真实临时 `.cnb/board.db`、真实 schema、真实 artifact 文件、CLI 命令 round trip。
3. **Boundary tests**：不触碰真实 `~/.cnb`、不写真实 registry/pubkeys、不调用真实 `tmux`/`gh`/Feishu OpenAPI。
4. **Contract tests**：README/CLI 文档中的命令示例能被 parser 接受，关键输出字段稳定。
5. **Regression matrix**：近期每个新增入口至少有成功、失败、降级、隔离四类用例。

## 建议拆分

- capture ingest：artifact、redaction、screenshot、board notify、CLI list/show、collision/error path。
- Feishu local_openapi：token fetch/reply failure、webhook verification/header token、setup config merge、watch server boundary。
- global discovery：marker-only registration skip、git/tmux summary timeout、CLI JSON/text output、legacy opt-out。
- Codex engine/swarm：permission flags、agent fallback、session command construction、docs/CLI consistency。

## Acceptance criteria

- 为上述专项建立或关联 issue。
- 每个近期新增 public entrypoint 至少有一个 CLI-level 或 integration-level 测试。
- 所有涉及用户 home/registry/pubkeys 的测试必须通过 `tmp_path`/monkeypatch 隔离。
- CI 继续跑 `ruff check`, `ruff format --check`, `mypy lib/`, `pytest`。

## 当前证据

本地盘点显示近 10 个 commit 改动约 3600 行，重点集中在 `capture_ingest.py`, `feishu_bridge.py`, `global_registry.py`, `bin/cnb`。`capture_ingest.py` 新增 388 行但测试初始只有 4 个用例，属于优先补强对象。
