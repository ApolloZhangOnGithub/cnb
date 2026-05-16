---
number: 160
title: "Supervisor compact stalls need external heartbeat and recovery path"
state: OPEN
labels: ["bug", "enhancement", "phase:1", "infra", "module:feishu", "module:runtime", "priority:p1"]
assignees: []
created: 2026-05-11
updated: 2026-05-15
---

# #160 Supervisor compact stalls need external heartbeat and recovery path

**State:** OPEN
**Labels:** bug, enhancement, phase:1, infra, module:feishu, module:runtime, priority:p1

---

## Problem

During Feishu dogfooding on 2026-05-11, the user reported that the Codex device-supervisor became unavailable because remote compact got stuck/failed. The user also called out the analogous Claude Code failure mode: compacting usually finishes, but can take long enough that the session appears dead from the user side.

CNB currently has runtime health and bridge/watchdog issues, but there is no specific control-plane contract for compact/stall recovery. If the active supervisor is inside Codex/Claude and that runtime stalls during compaction, Feishu users see silence until the model process resumes. Codex does not automatically restart itself here, so CNB needs an outer watchdog/recovery path.

## Evidence from user-message JSON

User messages in `/Users/zhangyiyi/.codex/history.jsonl` and rollout JSONL show the failure pattern from the user side:

- 2026-05-11 03:45-03:56 Asia/Shanghai: repeated "?", "回消息", "又忘回消息了" after model downgrade / Feishu reply delays.
- 2026-05-11 06:03-06:18 Asia/Shanghai: repeated "回复我", "没有看到。现在像你自己怎么重启呢？", "把实时一屏开出来".
- 2026-05-11 17:36-17:41 Asia/Shanghai: "怎么了", "？", then explicit diagnosis: "remote compact出问题了... codex 它也不会自动的去重启，所以一定要解决".

This is the same class of problem described in the referenced article: long-context or harness-level degradation is not enough to observe from inside the agent; the control plane needs an independent liveness contract.

## Desired behavior

- Detect supervisor stalls from outside the active Codex/Claude process, not from model self-report.
- Distinguish normal long tool execution from compact/stall by using heartbeat/activity timestamps and current foreground process state.
- Send Feishu a concise stale-state notice when the active supervisor stops responding beyond a threshold.
- Provide an operator action path: restart/resume session, spawn a replacement supervisor, or hand off to a backup runtime.
- Preserve last known task/message context so the restarted supervisor can answer the newest Feishu message instead of an older pending task.

## Scope ideas

- Add supervisor heartbeat emitted outside model turns where possible.
- Add compact/stall state to `cnb feishu activity` / live card.
- Extend runtime health checks to include last Feishu inbound, last Feishu reply, active turn age, and last TUI/output update.
- Add a documented recovery command or automated watchdog policy for Codex/Claude compact stalls.
- Treat Claude Code compact-long-running and Codex remote-compact failure as separate engine-specific adapters under the same CNB runtime health model.

## Acceptance criteria

- A stuck compact/no-reply scenario becomes visible in Feishu without waiting for user pings.
- CNB can recover or clearly instruct the device supervisor replacement path without requiring the user to know shell commands.
- The post-restart supervisor can continue from the newest user message and knows that a compact/stall occurred.
