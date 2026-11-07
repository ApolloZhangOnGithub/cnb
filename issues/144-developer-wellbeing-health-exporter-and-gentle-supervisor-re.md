---
number: 144
title: "Developer wellbeing health exporter and gentle supervisor reminders"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "module:runtime", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #144 Developer wellbeing health exporter and gentle supervisor reminders

**State:** OPEN
**Labels:** enhancement, phase:2, infra, module:runtime, priority:p2

---

## Background

CNB is becoming a long-running device supervisor for developers and owners. That makes developer wellbeing part of operational safety: if the human operator is exhausted, distracted, or overworking, the system can still produce code but the overall outcome may get worse.

This should not become a medical product. The goal is a consent-based, local-first wellbeing signal that lets CNB make gentle reminders and reduce unnecessary interruption.

## Problem

Current CNB coordination focuses on agents, repositories, issues, sessions, and Feishu activity. It does not consider the user's working state.

Risks:

- long coding/review sessions continue without break prompts;
- late-night work accumulates because agents keep asking for decisions;
- Feishu notifications can interrupt rest;
- token/agent automation may hide that the human is still carrying too much cognitive load;
- supervisors may optimize for code output rather than sustainable owner attention.

## Proposal

Add an optional `health-exporter` integration and gentle reminder policy for developer wellbeing.

The exporter should be local-first and opt-in. Potential signals, depending on platform permission and user choice:

- active work duration and idle intervals;
- local time, late-night windows, and sleep/protected hours;
- meeting/load calendar signals if explicitly authorized;
- rough interaction intensity, such as frequent Feishu replies or terminal activity;
- optional Apple Health / wearable aggregates where available and explicitly authorized.

CNB should use these only for low-stakes operational behavior:

- suggest breaks after long continuous sessions;
- postpone non-urgent Feishu notifications during rest windows;
- batch status updates instead of asking the owner repeatedly;
- warn when a task needs high-quality human judgment but the user appears overloaded;
- include a wellbeing section in daily/shift summaries.

## Privacy and safety requirements

- Opt-in only; default off.
- Local-first storage; no cloud upload by default.
- Store derived signals where possible, not raw health data.
- Never infer or diagnose medical conditions.
- Never shame the user or make manipulative claims.
- User can disable, pause, or delete wellbeing data.
- Health data must not be sent to external models unless explicitly approved for a specific operation.
- Reminders should be gentle and sparse, not another notification burden.

## Suggested commands/config

```bash
cnb health status
cnb health pause --for 2h
cnb health config set protected_hours 23:30-08:00
cnb health export --redacted
```

Possible config:

```toml
[health]
enabled = false
protected_hours = "23:30-08:00"
max_focus_minutes = 90
notify_policy = "gentle"
store_raw = false
allow_model_access = false
```

## Non-goals

- Not a medical diagnosis or wellness coaching app.
- Not a replacement for user judgment.
- Not a surveillance system for employers or teams.
- Not a reason to block urgent user commands.
- Not required for CNB 1.0-alpha, but useful for responsible long-running usage.

## Acceptance criteria

- A documented wellbeing/health data boundary exists.
- A minimal local exporter can report work duration, idle interval, and protected-hours status without raw sensitive data.
- Device supervisor can use the signal to batch or soften non-urgent reminders.
- Feishu/device-supervisor messages clearly distinguish wellbeing suggestions from task failures.
- The user can inspect and disable all collected wellbeing signals.

