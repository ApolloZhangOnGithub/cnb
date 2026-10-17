---
number: 67
title: "Default pytest can fail when ambient pytest-randomly reseeds numpy"
state: CLOSED
labels: ["bug", "phase:1", "infra", "priority:p0"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
closed: 2026-05-10
---

# #67 Default pytest can fail when ambient pytest-randomly reseeds numpy

**State:** CLOSED
**Labels:** bug, phase:1, infra, priority:p0

---

## Summary

During Codex-engine smoke work on 2026-05-10, multiple targeted test runs failed before project assertions executed because an ambient `pytest-randomly` install reseeded numpy with an out-of-range value.

## Evidence

Observed commands that failed under the default pytest plugin set:

```bash
pytest tests/test_token_usage.py -q
pytest tests/test_idle_concerns.py
pytest tests/test_entrypoint.py tests/test_swarm.py tests/test_swarm_backend.py tests/test_coral.py tests/test_init.py
```

The same target logic passed when the external plugin was disabled, for example:

```bash
pytest tests/test_token_usage.py -q -p no:randomly
# 23 passed

pytest -p no:randomly tests/test_idle_concerns.py
# 22 passed
```

## Why this matters

New contributors and agents can misread this as a source regression. The project should either isolate itself from ambient pytest plugins or configure pytest so `pytest-randomly` cannot break setup/teardown before assertions run.

## Suggested fix

Pin project test behavior in pytest configuration or `tests/conftest.py`, then verify with the default `python -m pytest` path and targeted test commands.

