# 开工流程 — Startup Sequence

类比工业流水线：先点检产线、装基础设施、再上人。乱序开工 = 边搭路边开车，会反复返工。

## 顺序

每次会话恢复或全新开工，按这个顺序，**不要跳步**：

### 0. 检查你是谁

- 你是面向用户的对接同学，还是 lead，还是某个项目同学？
- 用 `--name` 启动参数确认。没有名字的，你是用户的对接同学，不是 lead。
- lead 是单独的 tmux session (`cc-<prefix>-lead`)，由 swarm 管理；不是任何一个 claude 会话的别名。

### 1. 检查基础设施（不要碰人）

按这个顺序检查，任何一项不通过先修，**别拉人**：

| 项 | 命令 | 通过标准 |
|---|------|---------|
| git worktree 干净 | `git status --short` | 主 worktree 没有他人脏改 |
| master 同步 | `git fetch && git log master..origin/master` | 不落后 |
| dispatcher 运行 | `pgrep -f "bin/dispatcher$"` | 至少 1 个 PID |
| dispatcher 是最新代码 | `ps -o lstart= -p <PID>` | 启动时间晚于最近 dispatcher PR merge |
| 模型可用 | （启动一个 session 看有没有 "model not available" 错误）| 无错误 |
| 残留 worktree | `git worktree list` | 没有 /tmp/ 下死分支 |

任何一项不通过 → 先修这一项，提 PR、合 PR、重启对应服务，**然后**才进入下一步。

### 2. 拉人按角色顺序

```
swarm start lead         # 项目主管先起，所有员工要看 lead 派活
swarm start <dev>        # 按需要的最小集合起，不要一次全开
```

**不要一次全部 start。** 每开一个：
1. 等 10 秒
2. tmux capture-pane 看是否正常（无 model error、无 stuck queue）
3. 不正常 → kill 重启
4. 正常 → 再起下一个

满负载 ≠ 高效。3-4 人精干 > 7 人混乱。

### 3. 给员工派活前，先有 PR queue 视图

`gh pr list --state open --json number,title,mergeable` 先看：
- 多少 PR 待 review/merge
- 多少 conflict 需要 rebase
- 哪些 PR 阻塞 master CI（必须先合）

**先把 master CI 解锁**，再让员工开新分支。否则新 PR 一开就撞老 conflict。

### 4. 员工的初始任务必须独立

第一波派活时：
- 每个员工分别在 `/tmp/cnb-<name>-<issue>` worktree 干，不动主 worktree
- issue 之间无文件交叠（看 `gh pr diff` 历史，错开热点文件）
- 避免同时改 `lib/concerns/*` 或 `lib/board_*` — 这些是高冲突区

### 5. 派活后才设监控周期

lead 工作模式确认（自身要持续 nudge，员工 idle 不 nudge）后，才开放并行开发。

## WIP Limit — 在制品上限

每个员工同时 **最多 2 个 open PR**。这是 Kanban / Lean Manufacturing 的核心约束。

为什么：
- PR 数 = 库存。库存越多，flow 越慢。
- 每多一个 in-flight PR，rebase 链反应越严重（今天 lisa-su 7 个 PR、musk 5 个 → 任何 master 改动引爆全部）
- 员工注意力分散到 7 个分支，质量下降
- review 负担堆给 lead，lead 来不及消化变瓶颈

执行：
- lead 派活前先检查目标员工 `gh pr list --author <name> --state open` 数量
- 超过 2 → 不派新活，告诉员工"先合掉一个再说"
- 员工自己也要主动 close stale/重复 PR
- 例外：master CI 紧急修复 PR 不算 in-flight

观察指标：
- in-flight PR 总数 ≤ 团队人数 × 2
- 超过 → 暂停 issue dispatch，全员转 review/merge 模式直到降到阈值
- 这是 **流动效率 (flow efficiency)** 而非利用率 (utilization)

## 反模式 — 不要做

- ❌ 一上来 `swarm start`（全员）：会一次性触发 7 个 claude × N 个 init bug，根本看不清谁挂了
- ❌ 边修基础设施边派活：员工拿到的代码可能下一秒就被 PR 改写
- ❌ "先让他们跑着，我边看边修"：等于让 7 个产线同时调试
- ❌ 修一个组件就重启 dispatcher 一次：累积 6+ 次重启等于一直在重置 nudge 状态
- ❌ 在主 worktree 切到员工分支去 rebase：员工的 worktree 会被锁定，他无法继续

## 校准

每次开工后 30 分钟，停下来对账一次：
- 有多少 PR merged
- 有多少时间在修 self-inflicted 问题（你/lead/员工流程错误）
- 比值低于 50% → 流程有问题，停下来修流程，不是继续开发

工业里这叫 **OEE (Overall Equipment Effectiveness)** — 设备综合效率。低 OEE 时优先修设备，不是堆产量。
