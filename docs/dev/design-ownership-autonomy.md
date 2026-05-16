# 负责人自治能力设计

ROADMAP Phase 2 核心功能。让 ownership 不只是"这个模块是你的"，而是负责人能独立闭环完成工作。

## 问题

现在的负责人是等指令的执行者：

- 不会自己去看 issue — 需要人说"去查一下"
- `task done` 自己说了算 — 没有验证
- 代码停在本地 — 需要人催着 push/PR
- CI 挂了不知道 — 需要人转告

这四个缺口不是"通信问题"，是 ownership 的不完整定义。

## 设计原则

借鉴传统行业几百年积累的管理智慧，但不盲从 — LLM 团队有自己的特殊性。

### 约束即管理（军队：任务式指挥）

不告诉同学怎么改代码，告诉它约束：测试覆盖率 ≥ 80%、响应时间 ≤ 200ms、不引入安全漏洞。执行细节同学自己决定。写好约束，你就不需要在场。

**对应实现**：每个模块一个 contract 文件（`.cnb/contracts/<module>.yml`），定义该模块的验收标准。`task done` 时自动检查 contract。

### 不确定时停下来（丰田：安灯绳）

同学说"我不知道怎么做"比猜着做然后出垃圾 PR 有价值得多。

**对应实现**：引入 `task blocked "reason"` 命令。被 block 的任务自动通知 lead 和 dispatcher，不会被 idle killer 杀掉。

### 确定性验证（航空：检查单）

`task done` 后不能靠 LLM 自己说"我觉得没问题"。必须过一个硬编码的 CI 检查单。信任但验证，验证用机器不用人。

**对应实现**：`task done` 触发 verification pipeline：
1. `pytest` 通过
2. `ruff check` + `mypy` 通过
3. 变更范围在预期内（diff 文件数、行数）
4. 没有引入已知反模式（`git add -A`、硬编码密钥等）

全部通过才允许 close task。

### 纵深防御（核电站：分层安全壳）

不依赖任何单一安全层。每层都假设内层会失效：

1. 同学自查（最弱 — LLM 判断）
2. CI 测试
3. 安全扫描（secret scan）
4. 独立 LLM review（不同模型如果可能）
5. 变更影响评估（diff 范围检查）

目前大多数工具只有 1-2 层。

### 拉动式节奏（丰田供应链：看板）

不要一次 dispatch 20 个任务然后祈祷。验证管线的吞吐量是节拍器：

```
CI 合并 PR → 触发下一个任务 → 验证通过 → 拉下一个
```

同学速度不决定节奏，验证能力决定节奏。

### 分诊（急诊室：分级制度）

任务进来先分级，再分配：

| 级别 | 含义 | 例子 | 处理方式 |
|------|------|------|----------|
| 绿色 | 全自动 | 升依赖、修 lint、格式化 | 同学自主完成，自动合并 |
| 黄色 | 谨慎 | 改业务逻辑、重构 | 同学完成，需 review |
| 红色 | 必须人工 | DB migration、权限变更、发布 | 提交到 pending_actions 等用户确认 |

分诊成本远低于同学搞砸一个红色任务的代价。

### 可控遗忘（农业：轮作）

不要让同一个 session 无限期跑同一个模块。context 退化、惯性思维累积。定期杀旧 session 起新的。遗忘防止路径依赖 — 这是功能不是缺陷。

### 共识验证（生态学：冗余与多样性）

关键任务用两个独立 agent 处理（甚至不同模型）。一致则自动合并，不一致则提交人工。成本翻倍，可靠性可能翻十倍。

### LLM 团队的特殊性

以上原则来自管理"记得住但不靠谱"的人。LLM 相反："靠谱但记不住"。

- 人类团队需要减少沟通 → LLM 团队需要组织记忆
- 人类团队需要激励 → LLM 团队需要上下文
- 人类团队会偏离指令 → LLM 团队严格执行但重启就忘

cnb 解决失忆问题（日报、交接、ownership 持久化）。上面的原则解决可靠性问题。两者都需要。

---

## 四个缺失能力及实现方案

### 1. 任务感知 — IssueRoutingConcern

负责人自动发现相关 issue，不需要人告诉"去看一下"。

**已有基础**：`issues/` 目录由 GitHub Action 自动同步，每个 issue 有 YAML frontmatter（assignees、labels）。

**新增**：dispatcher concern，每 5 分钟扫描 `issues/`：

```python
class IssueRoutingConcern(Concern):
    interval = 300

    def tick(self, now):
        for issue in scan_issues(self.cfg.project_root / "issues"):
            if issue.state != "OPEN" or issue.number in self.routed:
                continue
            owners = match_owners(issue, self.ownership_map)
            for owner in owners:
                board_send(self.cfg, owner, f"[Issue #{issue.number}] {issue.title}")
            self.routed.add(issue.number)
```

**ownership 匹配规则**：
- `assignees` 字段直接映射到 session name
- `labels` 匹配 ownership map（e.g. `notification` → `lisa-su`）
- 无匹配 → 发给 lead

**测试重点**：
- frontmatter 解析（各种畸形格式）
- 匹配逻辑（多 label、无 assignee、未知 label）
- 去重（同一 issue 不重复路由）
- issue 状态变更（OPEN → CLOSED 不再路由）
- `issues/` 目录不存在时 graceful 降级

**预计**：~120 行实现 + ~200 行测试

### 2. 完成验证 — VerificationPipeline

`task done` 后自动跑验证，不是同学自己说 done 就 done。

**触发点**：hook 进 `board_task.py` 的 `cmd_task()` → `done` 分支。

**pipeline 步骤**：

```python
CHECKS = [
    ("pytest", ["python", "-m", "pytest", "--tb=short", "-q"]),
    ("ruff", ["ruff", "check"]),
    ("mypy", ["mypy", "lib/"]),
]

def verify_task_done(task_id, session, cfg):
    results = []
    for name, cmd in CHECKS:
        r = subprocess.run(cmd, capture_output=True, timeout=120, cwd=cfg.project_root)
        results.append((name, r.returncode == 0, r.stderr[:500]))

    if all(ok for _, ok, _ in results):
        return TaskVerdict.PASS
    else:
        # 通知同学哪些检查失败了
        failures = [f"{name}: {err}" for name, ok, err in results if not ok]
        board_send(cfg, session, f"验证未通过:\n" + "\n".join(failures))
        return TaskVerdict.FAIL
```

**分级处理**：
- 绿色任务（lint fix 等）：验证通过 → 自动 commit + push
- 黄色任务（业务逻辑）：验证通过 → 创建 PR 等 review
- 红色任务（migration 等）：验证通过 → 进 pending_actions 等人工确认

**测试重点**：
- 各种 pytest/ruff/mypy 失败组合
- timeout 处理（测试跑太久）
- 部分通过部分失败的报告格式
- 验证失败后任务状态回退（done → active）
- 重复验证的幂等性
- 没有 pytest/ruff 安装时的降级

**预计**：~150 行实现 + ~250 行测试

### 3. 产出交付 — AutoPR

改完代码自动创建 PR，不是停在本地等人推。

**触发点**：验证通过后（黄色/绿色任务），或 shutdown 流程中。

```python
def auto_pr(session, task, cfg):
    # 1. 确保所有变更已 commit + push
    ensure_pushed(cfg.project_root)

    # 2. 创建 PR
    branch = get_current_branch(cfg.project_root)
    if branch == "master":
        # 创建 feature branch
        branch = f"{session}/{task.id}-{slugify(task.description)}"
        git("checkout", "-b", branch)
        git("push", "-u", "origin", branch)

    result = gh_pr_create(
        title=f"[{session}] {task.description}",
        body=generate_pr_body(task, session),
        base="master",
        cwd=cfg.project_root,
    )

    # 3. 通知
    board_send(cfg, "lead", f"PR 已创建: {result.url}")
    board_send(cfg, session, f"PR 已创建: {result.url}")
```

**安全约束**：
- 红色任务不自动 PR — 进 pending_actions
- PR body 包含：任务描述、变更文件列表、验证结果摘要
- 不 force push，不直接合并到 master

**测试重点**：
- `gh` CLI 不可用时的降级
- 已在 feature branch vs 在 master 上
- PR 创建失败（网络、权限）
- PR body 生成（各种 diff 大小）
- 幂等性（不重复创建 PR）
- git 状态异常（未 commit 的变更、冲突）

**预计**：~120 行实现 + ~200 行测试

### 4. 外部触发 — ExternalEventConcern

CI 挂了、有新 issue、PR 被评论 — 负责人自动收到通知并响应。

**已有基础**：
- `issues/` 同步（GitHub Action，事件驱动 + 6h 轮询）
- `BugSLAChecker` concern（轮询 overdue bugs）
- `notification_log` 表（去重）

**新增 CI 状态检查**：

```python
class CIStatusConcern(Concern):
    interval = 120  # 2 分钟

    def tick(self, now):
        runs = gh_run_list(self.cfg.project_root, limit=3)
        for run in runs:
            if run.id in self.notified:
                continue
            if run.conclusion == "failure":
                # 找到失败的 job，匹配到 owner
                owner = match_ci_failure_to_owner(run, self.ownership_map)
                board_send(self.cfg, owner, f"CI 失败: {run.name} — {run.url}")
                self.notified.add(run.id)
```

**PR 评论监听**（依赖 issue sync 扩展或 webhook）：
- 短期：concern 轮询 `gh pr list --json comments`
- 长期：GitHub webhook → 写入 board

**测试重点**：
- `gh` CLI 失败 / timeout / 不安装
- CI 状态去重（同一次失败不重复通知）
- 失败匹配到 owner 的逻辑（按文件路径、按 label）
- 网络抖动时的重试策略
- 大量 CI run 的性能

**预计**：~130 行实现 + ~200 行测试

---

## Schema 变更

```sql
-- 模块 ownership 映射
CREATE TABLE IF NOT EXISTS ownership(
    module TEXT PRIMARY KEY,
    session TEXT NOT NULL REFERENCES sessions(name),
    labels TEXT DEFAULT '[]',    -- JSON array of GitHub labels
    paths TEXT DEFAULT '[]',     -- JSON array of file path patterns
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);

-- 任务验证记录
CREATE TABLE IF NOT EXISTS task_verifications(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    check_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    output TEXT DEFAULT '',
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_verify_task ON task_verifications(task_id);
```

---

## 实现顺序

```
Phase 2a — 验证管线（先让 task done 可信）
├─ VerificationPipeline        ~150 行 + ~250 行测试
├─ task blocked 命令            ~40 行 + ~60 行测试
└─ schema: task_verifications   ~10 行

Phase 2b — 任务感知（让负责人知道该做什么）
├─ ownership 表 + CLI           ~80 行 + ~100 行测试
├─ IssueRoutingConcern         ~120 行 + ~200 行测试
└─ CIStatusConcern             ~130 行 + ~200 行测试

Phase 2c — 产出交付（让负责人能交活）
├─ AutoPR                      ~120 行 + ~200 行测试
└─ 分诊分级集成                  ~60 行 + ~80 行测试
```

### 为什么验证先做

没有可信的验证管线，自动 PR 就是自动制造垃圾。验证是整个自治体系的信任基础 — 先让 `task done` 有含金量，再让它触发后续动作。

### 工作量估算

| 组件 | 实现 | 测试 | 合计 |
|------|------|------|------|
| VerificationPipeline | 150 | 250 | 400 |
| task blocked | 40 | 60 | 100 |
| ownership 表 + CLI | 80 | 100 | 180 |
| IssueRoutingConcern | 120 | 200 | 320 |
| CIStatusConcern | 130 | 200 | 330 |
| AutoPR | 120 | 200 | 320 |
| 分诊分级 | 60 | 80 | 140 |
| schema + migration | 20 | 30 | 50 |
| **合计** | **720** | **1120** | **1840** |

测试代码量是实现的 1.5 倍。这是正常的 — 每个组件都涉及外部命令（pytest/gh/git）的 mock、各种失败路径、状态机转换。用户说得对：**测试是不简单的**。

### 风险

1. **`gh` CLI 依赖** — 不是所有用户都装了 gh。需要 graceful 降级。
2. **CI 轮询频率** — 太频繁浪费 API quota，太慢则反馈延迟。需要自适应。
3. **ownership 匹配准确度** — label/path 匹配是模糊的。误路由比不路由更糟。需要 fallback 到 lead。
4. **并发安全** — 多个同学同时 `task done` 触发验证，pytest 可能冲突。需要排队或隔离。
5. **测试中 mock 外部命令** — subprocess mock 容易漏，真实 pytest/ruff 的 exit code/output 格式会变。需要 snapshot 测试。
