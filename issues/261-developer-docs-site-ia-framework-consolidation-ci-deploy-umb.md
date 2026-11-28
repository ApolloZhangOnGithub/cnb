---
number: 261
title: "Developer docs site — IA + framework + consolidation + CI deploy (umbrella)"
state: OPEN
labels: ["documentation", "phase:1", "infra", "priority:p2"]
assignees: []
created: 2026-05-17
updated: 2026-05-22
---

# #261 Developer docs site — IA + framework + consolidation + CI deploy (umbrella)

**State:** OPEN
**Labels:** documentation, phase:1, infra, priority:p2

---

## Rescoped (2026-05-17 17:25 per user correction)

**原文档站已完整上线** at docs.c-n-b.space — 不是 umbrella site rebuild。

实际窄任务：把刚 merge `rules/norms/startup-sequence.md` 集成进已 deployed Next.js docs 站作为新 MDX 入口 (agents/rules 或 guide 下)。

bezos 接 narrow task:
1. 找 docs 站 Next.js source (server / 本地 / 备份)
2. 加 startup-sequence MDX 入口
3. 本地 build 验证 → deploy /opt/cnb-docs/site/

如果 source 散失 — investigate + 选 reconstruct vs 改 build 产物。

**取消原 4 sub-tasks**: framework / IA / consolidation / CI pipeline (overshoot)。本 issue 收窄为单 "加 1 篇 norm to docs"。
