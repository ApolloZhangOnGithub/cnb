---
number: 77
title: "Tests pollute real ~/.cnb project registry and pubkeys"
state: CLOSED
labels: ["bug", "phase:1", "infra", "priority:p0"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
closed: 2026-05-10
---

# #77 Tests pollute real ~/.cnb project registry and pubkeys

**State:** CLOSED
**Labels:** bug, phase:1, infra, priority:p0

---

## Problem

Running the local test suite can mutate the developer's real machine-level cnb state instead of staying inside pytest temp directories.

Observed on 2026-05-10 from the cnb checkout:

- `~/.cnb/projects.json` contained 2181 registered projects.
- 2171 entries were stale.
- 2175 entries looked like pytest temp paths under `/private/var/.../pytest-of-zhangkezhen/...`.
- The remaining 10 existing board entries were also pytest temp projects.
- No non-test real project was registered, so `cnb projects list` was effectively unusable as a machine inventory.

The same test run also mutated `registry/pubkeys.json` until manually reverted. The likely source is tests that invoke `bin/init` without isolating `HOME` and without isolating the repo-level pubkey registry.

## Evidence

`tests/test_entrypoint.py` has a `board_project` fixture that runs:

```python
subprocess.run([
    str(CLAUDES_HOME / "bin" / "init"), "lead", "alpha", "bravo"
], cwd=project_dir, capture_output=True)
```

Unlike `_run()`, this fixture does not set `HOME` to a temp directory. `bin/init` then calls `register_project(project_dir, project_dir.name)`, which writes to the real `~/.cnb/projects.json`.

`bin/init` also generates keypairs and updates the shared pubkey registry, which can dirty `registry/pubkeys.json` during tests.

## Impact

This breaks the core machine-level registry feature:

- terminal supervisor / global dashboard logic sees thousands of fake projects
- `cnb projects list` becomes too noisy to be useful
- stale pytest paths hide real project state
- tests are not hermetic and can dirty the working tree

## Expected behavior

Tests must not touch real machine-level cnb state.

## Suggested fix

- In all subprocess-based tests that call `bin/init`, set `HOME` to a pytest temp directory.
- Add an override for global pubkey storage or make test invocations isolate `registry/pubkeys.json`.
- Add a regression test that asserts `~/.cnb/projects.json` and tracked `registry/pubkeys.json` are not modified by the test suite.
- Consider a safety guard in `register_project()` to ignore pytest temp paths unless explicitly enabled.
