---
number: 25
title: "cnb compose: team configuration file"
state: CLOSED
labels: [enhancement]
assignees: []
created: 2026-05-06
updated: 2026-05-06
closed: 2026-05-06
---

# #25 cnb compose: team configuration file

**State:** CLOSED
**Labels:** enhancement

---

## Idea

Support a `cnb-compose.yml` (or `.toml`) that defines a team:

```yaml
team:
  - name: architect
    role: "系统设计，技术方案评审"
    skills: ["python", "architecture"]
  - name: frontend
    role: "UI 实现"
    skills: ["react", "css"]
  - name: tester
    role: "测试验证"
    skills: ["pytest", "e2e"]
```

`cnb up` reads the file, inits sessions with predefined roles and system prompts.

## Why

Currently teams are random-themed. For real projects you want fixed roles with specialized prompts — like docker-compose defines services instead of random containers.

## Non-goals (for now)

- volume mounts / shared workspaces
- network isolation between agents
- dependency ordering (start tester after backend is ready)
