---
number: 43
title: "Auto-update check: warn outdated cnb installations"
state: OPEN
labels: ["phase:1", "infra"]
assignees: []
created: 2026-05-07
updated: 2026-05-08
---

# #43 Auto-update check: warn outdated cnb installations

**State:** OPEN
**Labels:** phase:1, infra

---

## ROADMAP check

已检查 ROADMAP.md。与 #42 (全局 dashboard) 有关联但不重叠——#42 是项目管理，本 issue 是版本管理。无依赖冲突。

## 背景

cnb 安装后版本可能落后于 npm/PyPI 最新版。需要主动提醒使用者更新。

## 当前状态

`bin/cnb` 启动时已有基础版本检查（比较本地 VERSION 和 npm 缓存），但只在用户交互启动团队时显示。

## 需要做的

1. **同学也能触发检查** — 不只是用户启动时，同学执行 cnb 子命令时也应该能检测到版本过期
2. **更新由 cnb 负责同学执行** — 检测到过期后，通知该电脑的 cnb 负责同学（而非所有同学各自更新）。负责同学执行 `npm install -g claude-nb`
3. **虚拟环境不管** — 如果 cnb 运行在虚拟环境中，跳过更新检查（用户自行管理）
4. **用户确认** — 是否需要用户确认再更新，待定。可能的方案：
   - 自动更新，事后通知用户
   - 提示用户，等确认后更新
   - 加入 pending queue (#34)，让用户批量处理

## 设计要点

- 版本缓存放 `~/.cnb/latest-version`，最多每小时刷新一次（后台非阻塞）
- 检测虚拟环境：检查 `$VIRTUAL_ENV` 或 `sys.prefix != sys.base_prefix`
- 负责同学识别：读全局 cnb 配置中的本机负责人

## 负责人

待定

## 交付回填 — 2026-05-10

Commit: `01abe3a` (`fix: route cnb update notifications`)

文件范围：
- `bin/cnb`
- `tests/test_entrypoint.py`

已完成：
- 子命令路径也会触发静默更新检查，并在检测到新版本时通知本机负责人/项目 lead。
- 新增 `VIRTUAL_ENV` 与 `sys.prefix != sys.base_prefix` 检测；虚拟环境内跳过更新检查。
- 新增 `_version_gt` 语义版本比较，避免 `VERSION=0.5.23-dev` 被 npm latest `0.5.1` 误判为需要升级。
- 保持交互启动路径的用户提示行为，不自动升级。

验证证据：
- `git show --stat --oneline 01abe3a` 只包含 `bin/cnb` 与 `tests/test_entrypoint.py`。
- `bash -n bin/cnb`
- `git diff --cached --check`
- `git show :bin/cnb | bash -n`
- `pytest -p no:randomly tests/test_entrypoint.py` => `30 passed`

关闭判断：
- 实现范围已满足 #43 的核心需求，可进入 PR review。
- 建议 PR review/merge 后再关闭 #43；当前不建议仅凭本地 commit 直接关闭。
