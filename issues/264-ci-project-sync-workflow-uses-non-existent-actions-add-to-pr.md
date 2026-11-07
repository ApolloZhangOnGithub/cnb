---
number: 264
title: "CI: project-sync workflow uses non-existent actions/add-to-project@v1 tag"
state: OPEN
labels: ["bug", "phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #264 CI: project-sync workflow uses non-existent actions/add-to-project@v1 tag

**State:** OPEN
**Labels:** bug, phase:1, infra, priority:p1

---

## ROADMAP check

属于运营基础类，无现有 issue 重复 (#73 是 sync-issues 不是 project-sync)。

## Bug

`.github/workflows/project-sync.yml` 5 处 uses `actions/add-to-project@v1`，但该 action 没有 `v1` tag (只有 v1.0.0/v1.0.1/v1.0.2/v2/v2.0.0)。每个 issue 事件都触发 workflow failure。

## Evidence

```
##[error]Unable to resolve action `actions/add-to-project@v1`, unable to find version `v1`
```

run examples: 25987118091, 25987117151, 25987116362 — all failure。Workflow runs since first issue event with this version.

## Fix

```bash
sed -i.bak 's|actions/add-to-project@v1|actions/add-to-project@v2.0.0|g' .github/workflows/project-sync.yml
rm .github/workflows/project-sync.yml.bak
```

5 处全改成 `@v2.0.0` (latest stable) 或 `@v1.0.2`（最新 v1.x.x）。我推荐 v2.0.0 — newer API。

## Impact

每个 GitHub issue 事件 spam fail run，CI noise + 真实失败被掩盖。

## Owner

待指定。fix 单行 sed，scope 5 分钟。等当前 wave merge / freeze 解除后接。

## 与 ROADMAP 关系

属于 `运营基础` 类，跟 `#73 sync-issues workflow` 类似 (CI workflow 故障) 但 fix 不同。
