---
number: 96
title: "Terminal supervisor should inspect Mac resource pressure and recommend safe actions"
state: OPEN
labels: ["enhancement"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #96 Terminal supervisor should inspect Mac resource pressure and recommend safe actions

**State:** OPEN
**Labels:** enhancement

---

## Background

When the Mac is under high CPU, memory, thermal, or simulator pressure, the terminal supervisor tongxue should be able to help the user understand what is actually consuming the machine. The culprit may be cnb, but it may also be an unrelated app instance such as Xcode, Vision Pro Simulator, Docker, browser tabs, video tools, or another agent stack.

Today the supervisor is positioned as a per-machine coordinator, but it does not yet have a safe resource-pressure review workflow. That leaves the user to manually notice slowdowns, inspect Activity Monitor, and decide what can be paused or closed.

## Desired capability

Add a Mac performance pressure review capability for the terminal supervisor:

1. Detect that the machine is under pressure or accept an explicit user request like "why is my Mac slow?".
2. Collect evidence about high-resource app/process instances, not only cnb-owned processes.
3. Explain the likely cause in user-facing language.
4. Recommend a management plan with risk levels.
5. Optionally take narrowly scoped actions, but only when the safety policy permits it.

## Evidence to collect

The first version can use shell-only macOS signals and avoid privileged APIs by default:

- Top CPU processes and process trees.
- Top memory/RSS consumers.
- Process age, command, parent PID, and owner.
- Known app grouping where possible: Xcode, Simulator, Docker, browsers, Terminal/tmux sessions, Python/Node workers, Claude/Codex sessions.
- cnb ownership signals when available: tmux session name, project path, board/session identity.
- Optional pressure indicators: `memory_pressure`, load average, swap usage, thermal state if cheaply available.

The report should group noisy child processes into useful app instances where possible. For example, a simulator workload should be presented as a simulator/app instance rather than twenty unrelated child processes.

## Recommendation ladder

Recommendations should be staged from safest to riskiest:

1. Observe only: summarize the top consumers and why they matter.
2. Ask the user: suggest likely low-risk next steps.
3. cnb-owned gentle actions: pause a dispatcher, reduce cnb concurrency, or stop an idle cnb-owned worker when ownership is clear.
4. Non-cnb app guidance: tell the user which app appears expensive and how to close or pause it manually.
5. High-risk automation: only after explicit confirmation, attempt a graceful quit/stop for a clearly identified target.

## Safety guardrails

This feature must not become an automatic process killer.

- No blind `kill`, no `kill -9` as a normal path, and no terminating unknown apps.
- Default mode is read-only diagnosis plus recommendation.
- Any destructive or externally visible action needs explicit user confirmation unless it is a low-risk cnb-owned pause action covered by config.
- Prefer graceful app/session-specific controls over PID killing.
- Show the exact target before acting: app/process name, PID/process tree, project/session if known, and expected impact.
- Maintain an audit log of what was observed, what was recommended, and what action was taken.
- Use cooldowns to avoid repeatedly nagging or repeatedly acting on the same process.

## Non-goals for the first version

- Building a replacement for Activity Monitor.
- Requiring root privileges or sudo.
- Automatically closing arbitrary third-party apps.
- Treating all high CPU as bad; builds, tests, simulators, and video processing can be legitimate.

## Acceptance criteria

- `terminal supervisor` can produce a concise "Mac resource pressure" report on demand.
- The report includes top app/process groups, resource evidence, likely cause, and recommended next action.
- The report distinguishes cnb-owned processes from unrelated machine activity.
- Unknown or non-cnb processes are never automatically terminated.
- Any optional action path has a dry-run/read-only mode and an explicit confirmation path.
- There are tests for process grouping, recommendation severity, and safety gating.

## Filing note

This issue replaces the mistakenly filed issue in the deprecated org/migration repository: https://github.com/cnb-workspace/cnb/issues/2
