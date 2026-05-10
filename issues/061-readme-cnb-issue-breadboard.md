---
number: 61
title: "README 应注明：cnb 是独立仓库，issue 不要提到 Breadboard"
state: OPEN
labels: ["documentation", "phase:1", "infra"]
assignees: []
created: 2026-05-08
updated: 2026-05-09
---

# #61 README 应注明：cnb 是独立仓库，issue 不要提到 Breadboard

**State:** OPEN
**Labels:** documentation, phase:1, infra

---

cnb 是 Breadboard 的 git submodule，但有自己的独立仓库 `ApolloZhangOnGithub/cnb`。

已经发生过外部同学把 cnb 的 issue 提到了 Breadboard 仓库（#12, #13, #14 都提错了）。

**请在 README 和 CONTRIBUTING 中明确注明：**

- cnb issue 请提到 https://github.com/ApolloZhangOnGithub/cnb/issues
- 不要提到 Breadboard 仓库（那是 monorepo 外壳）
- Breadboard 仓库的 issue 只用于跨项目事务或 Breadboard 自身的基础设施

— ritchie
