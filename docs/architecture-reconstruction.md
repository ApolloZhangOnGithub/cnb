# cnb Architecture Reconstruction Guide

本文档记录当前 checkout 里的实际架构。目标不是描述理想中的 cnb, 而是让后来者能按这份文档重新搭出同样的系统边界、运行路径和数据模型。

日期: 2026-05-11

## 0. Reading Boundary

本次梳理覆盖这些面:

- 根目录产品文档: `README.md`, `README_zh.md`, `ROADMAP.md`, `CONTRIBUTING.md`, `SECURITY.md`, `ADMIN_TO_DO.md`.
- CLI 入口: `bin/cnb`, `bin/claudes-code`, `bin/cnb.js`, `bin/_pip_entry.py`, `bin/board`, `bin/swarm`, `bin/init`, `bin/dispatcher`, `bin/dispatcher-watchdog`, `bin/doctor`, `bin/hygiene`, `bin/notify`, `bin/registry`, `bin/shutdown`, `bin/cnb-sync-gateway`, `bin/secret-scan`, `bin/sync-version`, `bin/check-*`.
- Python 核心模块: `lib/*.py`, `lib/concerns/*.py`.
- 数据模型: `schema.sql`, `migrations/*.sql`.
- 发布和 CI: `package.json`, `pyproject.toml`, `Makefile`, `.github/workflows/*.yml`.
- 运行和产品文档: `docs/*.md`, `bin/README.md`, `tools/*/README.md`.
- 侧车工具: `tools/cnb-mac-companion`, `tools/cnb-island`, `tools/web-capture`, `tools/cnb-sync-gateway`, `tools/project-discovery`, `tools/github-app-guard`.
- 测试面: `tests/test_*.py`.
- 当前工作区状态: `git status --short`, `bin/hygiene --json`.

当前 worktree 不是干净 release 状态, 本文档本身也在本轮维护中更新。因此本文以当前可读源码和最近提交为准, 同时在“技术债”章节标出会影响复现的分裂点。发布或打包前仍必须重新看 `git status --short --untracked-files=all` 和 CI 输出。

## 1. Product Model

cnb 是 local-first 的 LLM 团队组织层。它不只是启动多个 agent, 而是给长期运行的 Claude Code / Codex 会话提供:

- 项目级共享 board: SQLite 数据库, 消息、任务、状态、ownership、pending action 都在这里。
- 持久同学身份: 每个后台会话叫 tongxue / 同学, 有 session 文件、CV、ownership 和日报。
- 本地运行编排: tmux 或 screen 承载 Claude/Codex 进程。
- 调度器: 后台 concern loop 做心跳、空闲检测、提醒、资源检查、日报/周报和通知。
- 设备主管: 面向用户的本机主管会话, 可以由 CLI 或 Feishu 唤醒。
- 跨项目视角: `~/.cnb/projects.json` 记录本机项目, Mac companion 和 project discovery 读取它。
- 可选外部面: Feishu bridge、Web TUI、capture ingest、sync gateway、Mac/iOS companion。

核心架构原则:

- 代码和任务在本机项目目录里运行。
- 协作事实写入 SQLite 和文件系统, 不依赖 LLM 上下文窗口。
- 外部系统只作为控制面或通知面, 不成为默认状态源。
- 高风险动作应进入 pending action 或需要显式确认。

## 2. Runtime Topology

```text
User
  |
  | cnb / slash command / Feishu message
  v
bin/cnb
  |-- bin/init               -> creates .cnb/ and board.db
  |-- bin/board              -> board command registry
  |-- bin/swarm              -> starts/stops tmux or screen sessions
  |-- bin/dispatcher         -> concern loop
  |-- python -m lib.feishu_bridge
  |-- python -m lib.capture_ingest
  |-- bin/doctor / hygiene / notify / shutdown
  |
  v
Project root
  .cnb/
    config.toml
    board.db
    sessions/<name>.md
    cv/<name>.md
    logs/
    files/
    okr/
    keys/
    captures/
    dailies/

tmux/screen
  |-- <prefix>-<tongxue>     -> Claude Code / Codex / other agent CLI
  |-- <prefix>-dispatcher    -> dispatcher/coral session when used
  |-- cnb-device-supervisor  -> machine-level supervisor for Feishu
  |-- cnb-feishu-bridge      -> bridge process when daemonized
  |-- cnb-watch              -> read-only Web TUI server

Global machine state
  ~/.cnb/
    config.toml
    projects.json
    latest-version
    shared/credentials.json
    captures/
    feishu_resources/
    device-supervisor/
    device-chief/
    live_state.json
    feishu_chat.json
```

`.cnb/` 是当前产品语言中的 canonical 项目目录, 但大量测试和兼容代码仍支持旧 `.claudes/`。复现时必须保留 fallback, 否则现有测试、历史 demo 和部分 hook 会断。

## 3. Distribution And Entrypoints

### npm package

`package.json` 定义公共包名为 `claude-nb`, 安装后命令名是 `cnb`。

```text
package.json
  bin.cnb = bin/cnb.js
  files = bin/, lib/, migrations/, registry/, schema.sql, pyproject.toml, VERSION, Makefile
```

`bin/cnb.js` 是 Node wrapper:

```text
npm bin/cnb.js -> spawn bash bin/cnb with inherited cwd and env
```

运行要求:

- Node.js 18+
- Python 3.11+
- `cryptography>=41.0`
- tmux, git
- Claude Code CLI or Codex CLI

### Python package

`pyproject.toml` 定义:

```text
[project]
name = "claude-nb"

[project.scripts]
cnb = "lib.cli:main"

[tool.setuptools.packages.find]
include = ["lib*"]
```

`lib.cli` 是 pip/uv console script 的 Python wrapper, 它会尝试找到:

```text
repo/bin/cnb
/opt/homebrew/bin/cnb
PATH:cnb
```

找到源码 checkout 里的 `bin/cnb` 时, 它用 `bash bin/cnb ...` 执行; 找到全局 binary 时直接 `execvp`。

- `pyproject.toml` 当前指向 `lib.cli:main`。
- `bin/_pip_entry.py` 是另一份 pip/uv 入口实现, 它寻找 `bin/claudes-code`; 当前没有被 `pyproject.toml` 使用。
- `bin/claudes-code` 与 `bin/cnb` 当前内容完全一致, 是兼容命名入口。

现状注意: Python wheel 当前只包含 `lib*`, 不包含 `bin/`, `schema.sql`, `migrations/`。如果从 pip wheel 复现, 必须先修 packaging contract: 保留 `lib.cli`, 同时把 runtime 资源打进 wheel; 或者明确把 pip/uv 包定义为源码 checkout 专用入口。源码 checkout 和 npm tarball 是更接近当前真实运行路径的分发形态。

### Makefile install

`Makefile install` 是另一条传统安装路径:

```text
$(PREFIX)/bin/cnb -> symlink to $(PREFIX)/lib/cnb/bin/cnb
$(PREFIX)/lib/cnb -> bin/, lib/, schema.sql, VERSION
```

它不等同于 npm 或 pip 包, 但表达了早期架构假设: 一个安装目录里同时有 Bash 脚本、Python 模块和 schema 文件。

## 4. Project Initialization

初始化入口:

```bash
cnb init <sessions...>
cnb compose cnb.toml
cnb
```

关键实现:

- `bin/cnb` 默认检测当前项目是否已有 `.cnb/config.toml` 或 `.claudes/config.toml`。
- 新项目调用 `bin/init`.
- `bin/init` 创建 `.cnb/`, 如果没有 `.cnb/` 但已有 `.claudes/`, 则使用 legacy 目录。
- `bin/init` 写入 `config.toml`, 初始化 SQLite, 生成 session markdown, 安装 hook, 写 CLAUDE/AGENTS 协作片段, 注册全局项目, 生成密钥。
- `bin/init` 会合并或创建 `.claude/settings.json`, 添加 `PostToolBatch` pulse hook。
- `bin/cnb` 正常启动时还会生成 `.claude/commands/cnb-*.md` slash command 文件, 这些文件是运行期产物, 不属于核心源码。
- 如果项目是 Git repo, `bin/init` 会安装 `bin/secret-scan` 到 `.git/hooks/pre-commit`。
- keygen 路径会写项目本地 `.cnb/pubkeys.json` 或 legacy `.claudes/pubkeys.json`; 旧的源码级 `registry/pubkeys.json` 只作为兼容读取 fallback。

新项目初始目录:

```text
.cnb/
  config.toml
  board.db
  .gitignore
  sessions/
  files/
  okr/
  cv/
  logs/
```

运行后还会出现:

```text
.cnb/
  keys/
  captures/
  dailies/
  dispatcher.pid
  resource-monitor-state
```

`config.toml` 最小结构:

```toml
claudes_home = "/path/to/installed/cnb"
sessions = ["lead", "alice", "bob"]
prefix = "cc-abcd"

[session.lead]
persona = ""
role = "lead"
github_app_slug = "optional"
github_app_installation_id = "optional"
```

`prefix` 用项目路径 hash 生成, tmux session 形如 `<prefix>-<name>`。

初始化时的 schema 路径:

```text
bin/init -> schema.sql -> board.db -> meta.schema_version -> lib.migrate.run_migrations()
```

现状注意: `schema.sql` 已经包含 009 之前的表, 但 `bin/init` 仍把新库标成 schema version 4, 然后再跑 005 到 009。重建时要么保留这个行为, 要么显式设定 schema baseline 版本并修迁移测试。

## 5. Project State And Database Model

SQLite 是 board 的单一事实源。`lib/board_db.py` 和 `lib/common.py` 封装连接:

- 每次操作新建连接。
- WAL mode.
- `PRAGMA foreign_keys=ON`.
- row factory 使用 `sqlite3.Row`.
- `BoardDB(ClaudesEnv)` 会自动跑 pending migrations.
- `BoardDB(path)` 用于测试和轻量调用, 不一定有完整 env。

当前 `schema.sql` 表:

| Table | Purpose |
|-------|---------|
| `sessions` | tongxue 名称、状态、persona、更新时间、心跳 |
| `messages` | board 消息主表 |
| `inbox` | 消息投递和已读状态 |
| `proposals` / `votes` | 治理提案和投票 |
| `files` | shared file attachment 索引 |
| `bugs` | 内置 bug tracker 和 SLA |
| `threads` / `thread_replies` | BBS 讨论 |
| `kudos` | 贡献认可 |
| `suspended` | 暂停的 session |
| `tasks` | 每个 session 的 active/pending/done 队列 |
| `meta` | schema version、dispatcher session 等元信息 |
| `mailbox` | 加密异步消息 |
| `git_locks` | git index 协作锁 |
| `notification_log` | 通知去重记录 |
| `pending_actions` | 需要用户执行或确认的动作 |
| `ownership` | session 到 path pattern 的 ownership map |
| `session_runs` | session engine clock-in/out 记录 |
| `mail` | persistent mail, CC, thread |

Column-level schema contract:

```text
bugs: id, severity, sla, reporter, assignee, status, description, reported_at, fixed_at, evidence
files: hash, original_name, extension, sender, stored_path, ts
git_locks: id, session, reason, acquired_at, expires_at
inbox: id, session, message_id, delivered_at, read
kudos: id, sender, target, reason, evidence, ts
mail: id, thread_id, sender, recipients, cc, subject, body, ts, read_by
mailbox: id, ts, sender, recipient, encrypted_body, read
messages: id, ts, sender, recipient, body, attachment
meta: key, value
notification_log: id, notif_type, recipient, ref_type, ref_id, channel, sent_at
ownership: id, session, path_pattern, claimed_at
pending_actions: id, type, command, reason, verify_command, retry_command, status, created_by, created_at, resolved_at
proposals: id, number, slug, type, content, status, created_at, decided_at
session_runs: id, session, engine, started_at, ended_at
sessions: name, status, persona, updated_at, last_heartbeat
suspended: name, suspended_by, ts
tasks: id, session, description, status, priority, created_at, done_at
thread_replies: id, thread_id, author, body, ts
threads: id, title, author, created_at
votes: id, proposal_id, voter, decision, reason, ts
```

Foreign-key contract:

```text
inbox.session -> sessions.name ON DELETE CASCADE
inbox.message_id -> messages.id ON DELETE CASCADE
tasks.session -> sessions.name ON DELETE CASCADE
suspended.name -> sessions.name ON DELETE CASCADE
ownership.session -> sessions.name ON DELETE CASCADE
session_runs.session -> sessions.name ON DELETE CASCADE
votes.proposal_id -> proposals.id ON DELETE CASCADE
thread_replies.thread_id -> threads.id ON DELETE CASCADE
mail.thread_id -> mail.id ON DELETE CASCADE
```

Operational indexes:

```text
messages: sender, recipient, ts
inbox: session, read
tasks: session, status
bugs: status
mailbox: recipient, read
mail: sender, thread_id, ts
notification_log: notif_type/recipient/ref_id, sent_at
ownership: session, path_pattern
pending_actions: status, created_by
thread_replies: thread_id
session_runs: session/ended_at, session/started_at
```

当前 migrations:

```text
001_foreign_keys        rebuild core tables with FK constraints
002_session_persona     sessions.persona
003_mailbox             encrypted mailbox
004_heartbeat           sessions.last_heartbeat
005_notification_log    notification dedup
006_pending_actions     user-required operation queue
007_mail                persistent mail
008_ownership           path ownership registry
009_session_runs        engine run history
```

`BoardDB.deliver_to_inbox()` 负责投递:

- recipient 为 `all` 时投递给除 sender 外的所有 sessions。
- 私信时确保 recipient session 存在。
- 投递后触发 `inbox_delivered` signal, 供运行时 concern 做即时响应。

## 6. Board Command Architecture

`bin/board` 是 Python 命令注册表, 不是长 if/elif 分发。核心结构:

```text
Command(name, module, function, help, usage, needs_identity, takes_rest, aliases)
```

执行流程:

```text
bin/board
  -> ClaudesEnv.load()
  -> BoardDB(env)
  -> parse --as <identity>
  -> validate_identity()
  -> lazy import module
  -> call cmd function
```

主要模块:

| Module | Commands / Responsibility |
|--------|---------------------------|
| `lib.board_msg` | `send`, `status`, `inbox`, `ack`, `log` |
| `lib.board_inspect` | privileged read-only `inspect inbox/tasks <session>` without ack side effects |
| `lib.board_view` | `overview`, `view`, `dashboard`, `p0`, `dirty`, `freshness`, `relations`, `history`, `roster` |
| `lib.board_task` | `task add/done/list/next`, verify before done, optional auto PR |
| `lib.board_own` | `own claim/list/disown/transfer/offboard/orphans/map`, issue/CI scan, GitHub App PR token wiring |
| `lib.board_pulse` | lightweight heartbeat and unread count for Claude Code hooks |
| `lib.board_pending` | pending user actions, verify/retry/resolve loop |
| `lib.board_bug` | bug report/assign/fix/list/overdue |
| `lib.board_bbs` | board forum threads |
| `lib.board_vote` | proposal and voting |
| `lib.board_mailbox` | X25519 encrypted mailbox |
| `lib.board_mail` | persistent mail with CC/threading |
| `lib.board_daily` | per-session daily reports |
| `lib.board_admin` | suspend/resume/kudos |
| `lib.board_lock` | git lock |
| `lib.board_tui` | tmux-native dashboard |
| `lib.board_model` | provider/model profile switching |
| `lib.board_maintenance` | prune/backup/restore |

Exact registered board commands:

```text
send, status, inbox, ack, log, inspect
view, overview, dashboard/dash, p0, pre-build, dirty, files, get, roster, history, freshness, relations
post, reply, thread, threads
bug
task
own, scan
pulse
propose, vote, tally
keygen, seal, unseal, mailbox-log, keygen-all
daily
kudos, kudos-list/kudos-board, suspend, resume
git-lock, git-unlock, git-lock-status
tui
mail
pending
model/m
prune, backup, restore
```

Identity rules:

- `--as <name>` is required for commands that mutate or read session-owned state.
- `validate_identity()` accepts registered sessions plus privileged roles `lead` and `dispatcher`.
- `inspect inbox/tasks <session>` separates observation from impersonation: a session may inspect itself, while cross-session reads require `lead` or `dispatcher` and do not write ack markers.
- The current model does not cryptographically prove the caller is that session. Tests explicitly document some remaining impersonation and cross-project isolation gaps.

## 7. Main CLI Flow

`bin/cnb` is the user-facing Bash router.

Subcommand routing:

```text
cnb init              -> bin/init
cnb status|ps         -> bin/board overview
cnb board ...         -> bin/board ...
cnb model|m           -> bin/board model ...
cnb swarm ...         -> bin/swarm ...
cnb dispatcher        -> bin/dispatcher
cnb watchdog          -> bin/dispatcher-watchdog
cnb doctor            -> bin/doctor
cnb hygiene           -> bin/hygiene
cnb feishu ...        -> python -m lib.feishu_bridge ...
cnb feishu-chief ...  -> same module with ~/.cnb/device-chief/config.toml
cnb capture ...       -> python -m lib.capture_ingest ...
cnb shutdown          -> bin/shutdown
cnb logs <name>       -> board --as <name> log 50
cnb stop <name>       -> swarm stop <name>
cnb exec <name> msg   -> board send
cnb compose file.toml -> init --team + swarm start
cnb projects ...      -> lib.global_registry
cnb ui                -> board tui
cnb usage             -> lib.token_usage
cnb leaderboard       -> git log based contribution count
cnb version/help      -> shell-rendered metadata and command help
```

Default `cnb` with no subcommand:

1. Export `CNB_PROJECT`, defaulting to current working directory.
2. Run a non-blocking npm update check unless inside a virtualenv; subcommand mode can notify the configured owner via board.
3. Pick lead engine from `CNB_AGENT`, `SWARM_AGENT`, `cnb codex`, or `--agent`.
4. If project exists, read sessions from config.
5. If fresh, choose session names from built-in themes, run `bin/init`, then start worker sessions.
6. Start dispatcher in background if needed.
7. Generate `.claude/commands/cnb-*.md` slash commands.
8. Launch the lead session:
   - Claude: `claude --name <me> --append-system-prompt <prompt>`.
   - Codex: `codex --dangerously-bypass-approvals-and-sandbox --cd <project> <prompt>`.

The lead prompt tells the foreground session to split work, use board commands directly, and keep monitoring inbox/team progress.

## 8. Swarm And Session Runtime

`bin/swarm` wraps `lib.swarm`.

`SwarmConfig.load()` resolves:

- `ClaudesEnv`.
- agent from `SWARM_AGENT` or `CNB_AGENT`.
- backend from `SWARM_MODE` or available multiplexer.
- install home from `CLAUDES_HOME` or config.

Supported agent labels:

```text
claude, codex, trae, qwen
```

Important behavior:

- `SwarmManager.build_system_prompt()` injects board usage rules.
- `build_agent_cmd()` builds engine-specific launch command.
- Codex uses `--dangerously-bypass-approvals-and-sandbox` as the single high-permission flag.
- `smoke` / `standby` mode starts a session only to verify it can read state and report readiness. It forbids resuming old tasks.
- `ensure_registered()` keeps DB sessions, session markdown and config in sync.
- `clock_in()` and `clock_out()` write both `session_runs` and attendance log.
- `start()` skips suspended sessions, enables tmux mouse, starts sessions, injects prompts when needed, and joins startup helper threads.
- `stop()` gracefully sends interrupt, save status, `/exit`, then kills if needed.

Backends:

- `lib.swarm_backend.TmuxBackend`: tmux session lifecycle, pane command detection, prompt wait, trust prompt auto-accept, send-key injection.
- `lib.swarm_backend.ScreenBackend`: legacy screen support.
- `lib.tmux_utils`: smaller shared helpers for robust tmux run/capture/send. This is also used by board and dispatcher concerns.

Current duplication: `swarm_backend` still has direct `send-keys` paths while `tmux_utils.tmux_send()` uses buffer paste. A faithful reconstruction keeps both; a cleanup should unify them.

## 9. Dispatcher And Concerns

`bin/dispatcher` is a long-running daemon with independent concerns.

Startup:

```text
ClaudesEnv.load()
DispatcherConfig(...)
pid lock at .cnb/dispatcher.pid
base loop interval = 2s
```

It exits when no dev sessions are alive.

Concern system:

```text
Concern.interval
Concern.should_tick(now)
Concern.tick(now)
Concern.maybe_tick(now)
```

Configured concerns:

| Concern | Purpose |
|---------|---------|
| `CoralManager` | dispatcher/coral session lifecycle |
| `TimeAnnouncer` | hourly/daily board announcements |
| `IdleDetector` | pane snapshot comparison |
| `SessionKeepAlive` | detect dead sessions |
| `IdleKiller` | kill sessions idle too long |
| `NudgeCoordinator` | unified inbox/queued/idle nudges |
| `CoralPoker` | heartbeat to dispatcher session |
| `BugSLAChecker` | overdue bug checks |
| `HealthChecker` | team health reports and all-idle detection |
| `ResourceMonitor` | battery/memory/CPU transitions |
| `AdaptiveThrottle` | slow main loop under high CPU |

Current dispatcher nudge behavior is centralized in `NudgeCoordinator`, which replaces the older `InboxNudger`, `QueuedMessageFlusher`, and `IdleNudger` classes. It checks per-session readiness once per tick, applies one cooldown/backoff across inbox, queued-message flush, and idle nudges, then chooses the first applicable nudge in this priority order:

```text
inbox -> queued flush -> idle continuation
```

Notification push is currently not a dispatcher concern. The old `lib/concerns/notification_push.py` concern has been removed; `DigestScheduler` still exists and has tests, but `bin/dispatcher` does not instantiate it. Scheduled notification delivery therefore requires an explicit wiring change, while manual notification/digest commands still go through `bin/notify`.

## 10. Feishu Bridge

`lib.feishu_bridge` is the largest module and owns the Feishu control path.

Production runtime model:

```text
Feishu event subscription
  -> local CNB webhook
  -> verification token/chat/sender checks
  -> route message into device supervisor tmux
  -> supervisor replies with cnb feishu reply <message_id> ...
  -> bridge sends reply via Feishu OpenAPI
```

Config source:

- default: `~/.cnb/config.toml` `[feishu]`.
- chief: `~/.cnb/device-chief/config.toml`.
- old `terminal_supervisor_*` keys are accepted as aliases.

Core dataclasses:

- `FeishuInboundEvent`
- `BridgeResult`
- `ResourceDownloadResult`
- `ActivitySection`
- `ActivitySnapshot`
- `FeishuBridgeConfig`

Major functional zones inside `lib/feishu_bridge.py`:

| Zone | Representative functions |
|------|--------------------------|
| Config parsing | `FeishuBridgeConfig.load`, `_feishu_section`, `_render_feishu_section`, `setup_config` |
| Event extraction/filtering | `extract_event`, `should_accept`, `should_accept_group_target` |
| Pilot routing | `build_pilot_command`, `start_pilot_if_needed`, `format_for_pilot`, `route_event` |
| Activity tracking | `record_activity_start`, `mark_activity_done`, `mark_activity_monitor_closed`, `open_activity_items` |
| Device/team status | `describe_activity`, `discover_project_activity`, `foreground_agent_sessions` |
| Readback/resource handoff | `build_history_readback`, `inspect_message_readback`, `collect_message_resources_and_links`, `openapi_download` |
| Feishu cards/replies | `build_activity_card`, `send_activity_update`, `send_reply`, `send_reply_openapi` |
| Watch/Web TUI | `start_watch_viewer`, `serve_watch_viewer`, `watch_page_html`, `watch_snapshot_payload` |
| Daemon/webhook | `serve_webhook`, `consume_events`, `start_bridge_daemon`, `stop_bridge_daemon`, `print_status` |

Notification policies:

| Policy | Behavior |
|--------|----------|
| `final_only` | no automatic ack or live card, final reply only |
| `ack` | received confirmation, then final reply |
| `live` | ack plus one update card loop for debugging |

Resource handoff:

```text
~/.cnb/feishu_resources/<message_id>/
```

Readback is opt-in and disabled by default. Web TUI is tokenized and read-only.

Device chief:

```bash
cnb feishu-chief status
cnb feishu-chief setup --role device_chief ...
cnb feishu-chief start
```

This is the same bridge module with a different config path and role defaults.

Registered Feishu CLI subcommands:

```text
status, setup, listen, handle-event, start, stop
activity, tui, watch, watch-stop, watch-serve
history, inspect-message
ask, reply
```

`cnb feishu` uses `~/.cnb/config.toml` by default. `cnb feishu-chief` passes `--config ~/.cnb/device-chief/config.toml` into the same parser.

## 11. Global Registry And Multi-Project View

`lib.global_registry` stores machine-level project discovery state in `~/.cnb`.

Files:

```text
~/.cnb/projects.json
~/.cnb/shared/credentials.json
```

Public commands:

```bash
cnb projects list
cnb projects cleanup
cnb projects scan [--register] [--mode board|marker]
```

Project discovery scans bounded roots, defaulting to:

```text
~/Desktop/Toolbase_Skills
~/Desktop
```

It detects `.cnb` first, optionally legacy `.claudes`, reads `config.toml`, checks `board.db`, inspects tmux sessions, summarizes git status, and can upsert real board-backed projects into `projects.json`.

Mac companion and future dashboards consume this registry rather than recursively scanning the whole filesystem on every refresh.

## 12. Capture Ingest

Capture is intentionally split:

- cnb owns the stable ingest CLI and artifact layout.
- Browser/app collectors live outside cnb and call the CLI with user-authorized payloads.

Commands:

```bash
cnb capture ingest --project /path/to/project --mode selection --source safari-web-extension < payload.json
cnb capture ingest --global --mode page --source safari-web-extension < payload.json
cnb capture list --project /path/to/project
cnb capture show --project /path/to/project <capture-id>
```

Valid modes:

```text
selection, article, page, snapshot, visual-only, redacted
```

Project artifacts:

```text
.cnb/captures/<capture-id>/
  manifest.json
  payload.redacted.json
  content.md
  page.sanitized.html
  visible.png
```

Global captures go to:

```text
~/.cnb/captures/<capture-id>/
```

`lib.capture_ingest` redacts obvious password/token fields, strips risky HTML tags, writes readable `content.md`, optionally stores screenshots, and can notify a board recipient.

## 13. Notifications, Digests, Pending Actions

Notification config:

```text
.cnb/notifications.toml
```

`lib.notification_config` supports notification types:

```text
daily-digest, ci-alert, mention, issue-activity, weekly-report
```

Channels:

```text
board-inbox, lark-im, lark-mail, gmail
```

Only `lark-im` has an implemented external delivery path, through `lark-cli im +messages-send`.

Digests:

- `lib.digest` generates daily and weekly summaries from board tables.
- `lib.concerns.digest_scheduler` can send scheduled digests, but is currently disconnected from `bin/dispatcher`.
- `bin/notify` exposes status/subscriptions/digest/test/log/weekly flows.

Pending actions:

- Table: `pending_actions`.
- Command: `board --as <name> pending ...`.
- Used when an operation needs user auth, approval, or confirmation.
- Supports `verify_command` and `retry_command` so user intervention can be verified and original operation retried.

## 14. Ownership, Verification, Auto PR

Ownership source:

```text
ownership(session, path_pattern, claimed_at)
```

Matching:

```text
find_owner(file_path): longest path prefix match wins
```

Commands:

```bash
cnb board --as <name> own claim <path>
cnb board --as <name> own map
cnb board --as <name> own transfer <target> <path>
cnb board --as <name> own offboard [target]
cnb board --as <name> scan
```

Task completion path:

```text
board_task._task_done()
  -> verify_task(project_root)
  -> mark task done
  -> auto_pr(project_root, task_desc, session)
  -> promote next pending task
```

Current `verify_task()` only runs:

```bash
python -m pytest -x -q --tb=short
```

Auto PR:

- Only acts on a non-main branch.
- Requires unpushed commits.
- Pushes branch.
- Calls `gh pr create`.
- May use GitHub App token env from `lib.github_app_identity` if a per-session binding exists and no slug conflict is detected.

## 15. Shutdown And Reports

Shutdown command:

```bash
cnb shutdown
```

Implementation:

```text
bin/shutdown -> lib.shutdown.run_shutdown()
```

Flow:

1. Broadcast shutdown notice.
2. Wait for session acknowledgements.
3. Collect per-agent reports.
4. Generate shift metadata.
5. Save under `.cnb/dailies/<shift>/`.
6. Stop sessions and dispatcher.

Report helpers:

- `lib.shift_report.generate_agent_report`
- `lib.shift_report.generate_shift_meta`
- `board --as <name> daily`

Device supervisor handoff must not be written into project tongxue dailies. Feishu-routed machine-level notes belong under:

```text
~/.cnb/device-supervisor/dailies/<date>.md
```

## 16. Sidecar And Companion Surfaces

### Mac companion

Path:

```text
tools/cnb-mac-companion/
```

It is a SwiftPM macOS 14 app. It reads local cnb state only:

- `~/.cnb/projects.json`.
- `<project>/.cnb/board.db`, fallback `<project>/.claudes/board.db`.
- SQLite counts for pending actions, tasks, unread messages, sessions, blocked sessions.
- Feishu settings from `~/.cnb/feishu_chat.json` or `~/.cnb/config.toml`.

Safe operations:

- refresh
- open project folder
- open Terminal at project
- reveal board database
- open `~/.cnb`
- show embedded Feishu Web TUI via local `cnb feishu watch-serve`

Build:

```bash
cd tools/cnb-mac-companion
./script/build_and_run.sh --no-launch
./script/build_and_run.sh --verify
```

### iOS Live Activity / Vision scaffold

Current tracked path:

```text
tools/cnb-island/
```

The architecture documented by that tree:

- `export_live_state.py` writes `~/.cnb/live_state.json`.
- iOS host app reads state and starts/updates ActivityKit Live Activity.
- WidgetKit extension renders Lock Screen and system island presentations.
- `export_feishu_chat_config.py` writes `~/.cnb/feishu_chat.json`.
- iOS and visionOS apps call Feishu OpenAPI directly for chat/read-only viewer paths.
- `ADMIN_TO_DO.md` can be copied into app documents for maintainer tasks.

Build scripts in that tree:

```bash
./script/typecheck_live_activity.sh
./script/build_xcode.sh
./script/run_iphone_simulator.sh
./script/build_vision.sh
./script/run_vision_simulator.sh
```

### Web capture sidecar

Current tracked path:

```text
tools/web-capture/README.md
```

Browser collectors should remain separate from cnb and call `cnb capture ingest`. The stable side is the cnb ingest command and capture artifact layout; the browser extension itself can live outside this repo.

### Sync gateway

`lib.cnb_sync_gateway` and `bin/cnb-sync-gateway` implement a small HTTP/SSE event log:

```text
data-dir/
  cnb-sync.db
  attachments/
```

Endpoints:

```text
POST /v1/events
GET  /v1/events?after=<id>
GET  /v1/stream?after=<id>
GET  /health
GET  /v1/stats
```

It is dependency-free and Python 3.6 compatible for small Linux hosts. Public bind requires bearer token auth.

CLI flags:

```text
--host, --port, --data-dir, --token, --cors-origin, --allow-no-auth
```

## 17. GitHub, Registry, Issues, Releases

### Local issues mirror

`.github/workflows/sync-issues.yml` uses `gh issue list`, writes Markdown snapshots under `issues/`, commits to a sync branch, and opens/updates a PR.

The workflow currently calls:

```bash
python -m lib.github_issues_sync --issues-dir issues --source-repo "$ISSUE_SOURCE_REPO" /tmp/issues.json
```

`lib.github_issues_sync` converts GitHub JSON into:

```text
issues/<number>-<slug>.md
issues/README.md
```

### Contributor registry chain

`registry/*.json` is a simple append-only identity chain. `bin/registry` can:

```bash
registry register <name>
registry verify <name>
registry verify-chain
registry list
registry rank
registry whois <name>
```

CI workflow `registry.yml` verifies chain integrity and syncs `registry/README.md`.

### GitHub App identity

Modules:

- `lib.github_app_guard`: default-deny allowlist guard.
- `lib.github_app_identity`: GitHub App JWT, installation discovery, repo-scoped token creation.
- `lib.board_own`: uses these helpers when auto PR wants a session-specific app identity.

Expected local app files:

```text
~/.github-apps/<app-slug>/
  app.json
  private-key.pem
  allowlist.json
  installation.json
```

GitHub App helper CLIs:

```text
python -m lib.github_app_guard validate|check
python -m lib.github_app_identity installation|installations|token
```

### Release and package workflows

Important workflows:

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | ruff, format, mypy, consistency, secret scan, npm tarball smoke, pytest matrix |
| `codeql.yml` | CodeQL analysis |
| `pages.yml` | deploy `site/` to GitHub Pages |
| `prepare-release.yml` | create release branch/PR, sync version and changelog |
| `publish-npm.yml` | publish npmjs `claude-nb`, optionally mirror to GitHub Packages |
| `publish-github-package.yml` | repair/manual mirror to `@apollozhangongithub/cnb` |
| `registry.yml` | registry chain guard |
| `sync-issues.yml` | GitHub issue mirror |

Release contract:

- `VERSION`, `package.json`, `pyproject.toml` must stay in sync.
- Release versions must not use `-dev`.
- `CHANGELOG.md` needs dated release section for release versions.
- npmjs package `claude-nb` is canonical.
- GitHub Packages mirror is scoped and secondary.

## 18. Quality And Test Surface

Main checks:

```bash
ruff check lib/ bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/doctor bin/init bin/notify bin/registry bin/secret-scan bin/sync-version bin/check-changelog bin/check-branding tests/
ruff format --check lib/ bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/doctor bin/init bin/notify bin/registry bin/secret-scan bin/sync-version bin/check-changelog tests/
mypy lib/
python -m pytest tests/ -v --tb=short
python bin/sync-version --check
python bin/check-changelog
python bin/secret-scan --all
bin/check-npm-package --install-smoke
bin/check-readme-sync
```

Major test coverage areas:

- Board behavior: messaging, tasks, bugs, BBS, voting, daily, pending, ownership, locks, TUI, view.
- Runtime: swarm, backend, dispatcher, concerns, tmux utils, health, resources.
- Feishu: config, event extraction/filtering, routing, replies, activity, watch, setup.
- Packaging/entrypoints: `bin/cnb`, `bin/cnb.js`, `bin/claudes-code`, `lib.cli` when retained, npm package smoke helpers.
- Data: migrations, schema, global registry, secret scan, sync version.
- Side surfaces: capture ingest, sync gateway, GitHub App identity, notification delivery.
- Known limitations: `tests/test_security_isolation.py` documents some currently allowed cross-session/cross-project behaviors.

If ambient `pytest-randomly` causes seed problems, the reliable fallback in this repo has been:

```bash
python -m pytest -p no:randomly tests/ -v --tb=short
```

## 19. Reproduction Procedure

### A. Reproduce from source checkout

```bash
git clone https://github.com/ApolloZhangOnGithub/cnb.git
cd cnb
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install ruff mypy pytest
npm install -g @anthropic-ai/claude-code   # optional if testing Claude
npm install -g @openai/codex               # optional if testing Codex
```

If `pip install -e .` fails around the `cnb` console script, verify that `lib.cli` is importable and that the checkout still contains `bin/cnb`. The Python package wrapper currently depends on source-tree runtime files.

Run static checks:

```bash
python bin/sync-version --check
python bin/check-changelog
bin/check-readme-sync
bin/check-npm-package --install-smoke
```

Initialize a sample project:

```bash
mkdir /tmp/cnb-repro
cd /tmp/cnb-repro
/path/to/cnb/bin/cnb init lead alice bob
sqlite3 .cnb/board.db '.tables'
/path/to/cnb/bin/board --as lead status "ready"
/path/to/cnb/bin/board --as lead task add --to alice "verify board path"
/path/to/cnb/bin/board --as alice inbox
```

Start runtime:

```bash
cd /tmp/cnb-repro
CNB_AGENT=codex SWARM_AGENT=codex /path/to/cnb/bin/swarm smoke alice
tmux list-sessions
/path/to/cnb/bin/swarm status
```

Start dispatcher:

```bash
cd /tmp/cnb-repro
/path/to/cnb/bin/dispatcher
```

Run doctor:

```bash
/path/to/cnb/bin/cnb doctor
```

### B. Reproduce npm package path

```bash
npm pack
tmp=$(mktemp -d)
npm install --global --ignore-scripts --no-audit --no-fund --prefix "$tmp/install" ./claude-nb-*.tgz
PATH="$tmp/install/bin:$PATH" cnb --version
mkdir "$tmp/project"
cd "$tmp/project"
PATH="$tmp/install/bin:$PATH" cnb init lead alice
```

The current smoke only checks `cnb --version`; for an architecture-level reproduction, also run `cnb init` and inspect `.cnb/board.db`.

### C. Reproduce Feishu bridge shape without real Feishu

```bash
cnb feishu setup --help
cnb feishu status
cnb feishu watch-serve --help
```

For real Feishu operation, provide:

- `app_id`
- `app_secret`
- `verification_token`
- `webhook_public_url`
- allowlisted `chat_id`
- required IM/resource permissions
- optional `watch_token`

Then:

```bash
cnb feishu setup
cnb feishu status
cnb feishu start
```

### D. Reproduce capture

```bash
cat > /tmp/capture.json <<'JSON'
{
  "source": "manual",
  "mode": "selection",
  "title": "Example",
  "url": "https://example.com",
  "selection_text": "hello"
}
JSON

cnb capture ingest --project /tmp/cnb-repro --mode selection --source manual --no-notify < /tmp/capture.json
cnb capture list --project /tmp/cnb-repro
```

### E. Reproduce global project discovery

```bash
cnb projects scan --root /tmp --max-depth 2 --mode marker
cnb projects scan --root /tmp --max-depth 2 --register
cnb projects list
```

### F. Reproduce Mac companion

```bash
cd tools/cnb-mac-companion
./script/build_and_run.sh --no-launch
./script/build_and_run.sh --verify
```

The companion expects `~/.cnb/projects.json` to exist for useful data.

### G. Reproduce sync gateway

```bash
bin/cnb-sync-gateway --host 127.0.0.1 --port 8765 --data-dir /tmp/cnb-sync
curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8765/v1/events \
  -H 'Content-Type: application/json' \
  -H 'X-CNB-Device-ID: mac-local' \
  -d '{"stream":"chat","type":"message.created","payload":{"text":"hello"}}'
curl -sS 'http://127.0.0.1:8765/v1/events?after=0'
```

## 20. Current Technical Debt That Affects Reconstruction

These are not style complaints. They change how faithfully someone can rebuild the architecture.

1. Python package contract is incomplete.
   - `pyproject.toml` publishes `lib*`.
   - `lib.cli` expects `bin/cnb`, `/opt/homebrew/bin/cnb`, or `PATH:cnb`.
   - wheel installs can miss runtime resources.

2. Schema baseline is ambiguous.
   - `schema.sql` contains tables through migration 009.
   - new init still records schema version 4.
   - fixtures sometimes set schema version 7.

3. `.cnb` and `.claudes` are half-migrated.
   - Product docs prefer `.cnb`.
   - tests and some docs still build `.claudes`.
   - hooks/settings may reference only `.claudes`.

4. Encrypted-mailbox key storage has a legacy fallback.
   - New project init/keygen writes public keys to project-local `.cnb/pubkeys.json` or `.claudes/pubkeys.json`.
   - Existing source-level `registry/pubkeys.json` is still read as a compatibility fallback.
   - Tests that spawn `bin/init` still need isolated `HOME` so global project registration stays hermetic.

5. Feishu bridge is a monolith.
   - It mixes config, webhook, OpenAPI, tmux routing, activity cards, watch server, readback and resource handoff.
   - Small changes risk unrelated formatting/type/test churn.

6. tmux interaction has two implementations.
   - `tmux_utils.tmux_send()` uses buffer paste.
   - `swarm_backend` still uses direct `send-keys` and string command construction.

7. Some tests preserve known bad behavior.
   - Security isolation tests document impersonation and cross-project access limits rather than enforcing the final desired boundary.
   - Feishu activity tests currently treat monitor-closed requests as still open.

8. Current worktree can contain generated/local state.
   - `bin/hygiene --json` reports generated/cache files and local runtime state.
   - Current snapshot also reports marked backup/duplicate files: `lib/cli 2.py`, `lib/github_issues_sync 2.py`, `tests/test_cli 2.py`, `tests/test_github_issues_sync 2.py`.
   - legacy key material can still exist in source-level `registry/pubkeys.json`.
   - Do not treat the dirty checkout as a clean release artifact.

9. Dead-code removal changed extension points.
   - `notification_push.py` and `panel.py` are no longer active modules.
   - Reconstruction should keep old tests/docs from importing removed concern classes.

10. Dispatcher notification architecture is partially orphaned.
    - `NudgeCoordinator` is the active nudge path.
    - `DigestScheduler` is implemented and tested but not wired into `bin/dispatcher`.
    - scheduled push/digest delivery needs a new explicit dispatcher wiring decision.

11. Two CLI compatibility names exist.
    - `bin/cnb` and `bin/claudes-code` are currently identical.
    - npm exposes only `cnb`.
    - `_pip_entry.py` expects `bin/claudes-code`, while `pyproject.toml` expects `lib.cli:main`.

## 21. Minimal Rebuild Checklist

To rebuild the current architecture from scratch, implement in this order:

1. CLI wrapper layer:
   - Node `bin/cnb.js`.
   - Bash `bin/cnb` and compatibility copy `bin/claudes-code`.
   - pip/uv entry decision: keep `lib.cli` or replace with `_pip_entry.py`-backed packaging.
   - Python `bin/board`, `bin/swarm`, `bin/init`.

2. Project env:
   - `.cnb` canonical layout.
   - `.claudes` compatibility.
   - `ClaudesEnv.load()`.

3. SQLite board:
   - `schema.sql`.
   - migrations.
   - `BoardDB`.
   - board command modules.

4. Runtime sessions:
   - tmux backend.
   - system prompts.
   - agent launch commands.
   - attendance and `session_runs`.

5. Dispatcher:
   - `DispatcherConfig`.
   - `Concern` base.
   - health, idle, unified nudge, resource and time concerns.
   - decide whether scheduled digests are manual-only or wired into dispatcher.

6. Operational loops:
   - task queue.
   - ownership map.
   - pending action verify/retry.
   - daily/shutdown reports.
   - doctor/hygiene.

7. External surfaces:
   - Feishu bridge.
   - capture ingest.
   - global registry.
   - sync gateway.
   - Mac/iOS companion readers.

8. Governance:
   - issue sync.
   - registry chain.
   - GitHub App identity.
   - CI/release workflows.

9. Tests:
   - board contract tests.
   - migration tests.
   - runtime backend tests.
   - Feishu tests.
   - package smoke tests.

10. Documentation:
   - README short path.
   - `docs/` durable operations.
   - tool runbooks under `tools/`.
   - this architecture reconstruction guide.

## 22. File Map

Use this map when locating implementation ownership:

```text
bin/
  cnb                         main user CLI router
  claudes-code                compatibility copy of cnb
  cnb.js                      npm wrapper
  _pip_entry.py               unused pip/uv wrapper candidate
  board                       board command registry
  swarm                       session CLI wrapper
  init                        project initializer
  dispatcher                  concern daemon
  dispatcher-watchdog         watchdog wrapper
  doctor                      health checks
  hygiene                     worktree/generated-state classifier
  notify                      digest/notification CLI
  registry                    contributor chain CLI
  secret-scan                 secret scanner
  sync-version                version sync
  configure-godaddy-pages-dns DNS helper for the GitHub Pages custom domain
  check-*                     CI guardrails

lib/
  common.py                   project env, DB base, signals, flags
  board_db.py                 SQLite board wrapper
  board_msg.py                send/status/inbox/ack/log
  board_view.py               read-only views, history, freshness, relations
  board_task.py               task queue, verify, auto-PR trigger
  board_own.py                ownership, owner scan, GitHub App PR handoff
  board_pending.py            user-required actions, verify/retry/resolve
  board_bug.py                bug tracker and SLA query
  board_bbs.py                thread/reply forum
  board_vote.py               proposals and votes
  board_mailbox.py            encrypted mailbox and keygen
  board_mail.py               persistent mail with CC/threading
  board_daily.py              session daily reports
  board_admin.py              suspend/resume/kudos
  board_lock.py               git lock coordination
  board_tui.py                tmux-native TUI
  board_model.py              provider/model profile switcher
  board_maintenance.py        prune/backup/restore
  swarm.py                    high-level session manager
  swarm_backend.py            tmux/screen backends
  tmux_utils.py               shared tmux helpers
  build_lock.py               mkdir-based build queue lock
  concerns/__init__.py        active concern exports
  concerns/base.py            concern scheduler primitive
  concerns/config.py          dispatcher config dataclass
  concerns/coral.py           dispatcher/coral session lifecycle
  concerns/health.py          keepalive, health and resource concerns
  concerns/idle.py            idle detector/killer
  concerns/nudge_coordinator.py unified inbox/flush/idle nudges
  concerns/notifications.py   time announcements and bug SLA checks
  concerns/digest_scheduler.py implemented but not wired scheduled digests
  concerns/adaptive_throttle.py CPU-based loop throttle
  concerns/helpers.py         tmux/DB/log helpers
  feishu_bridge.py            Feishu ingress/reply/watch/readback
  capture_ingest.py           capture protocol implementation
  global_registry.py          ~/.cnb project registry
  cnb_sync_gateway.py         HTTP/SSE event log
  github_app_*.py             GitHub App guard/token helpers
  notification_config.py      notification subscription config
  notification_delivery.py    external delivery adapters
  digest.py                   daily/weekly summaries
  shift_report.py             shift reports
  shutdown.py                 shutdown orchestration
  token_usage.py              Claude Code JSONL usage parser
  resources.py                battery/memory/CPU monitor
  health.py                   standalone tmux health report
  inject.py                   tmux/screen message injection helper
  migrate.py                  schema migration runner
  crypto.py                   X25519 sealed-box helpers
  theme_profiles.py           built-in team profile data

schema.sql                    current full board schema
migrations/                   incremental schema changes
docs/                         durable product/ops docs
issues/                       GitHub issue mirror
registry/                     contributor identity chain and pubkeys
tools/
  cnb-mac-companion/          SwiftPM macOS menu-bar/companion app
  cnb-island/                 iOS Live Activity and visionOS Feishu viewer scaffold
  web-capture/                browser sidecar boundary README
  cnb-sync-gateway/           systemd/install/backup scripts for sync gateway
  project-discovery/          project scan runbook
  github-app-guard/           GitHub App allowlist runbook
site/                         GitHub Pages static site
tests/                        behavior and regression tests
```

## 23. Documentation Source Map

The repo has several docs that are source material for the reconstruction guide. They are not all equivalent:

| File | Role in reconstruction |
|------|------------------------|
| `README.md`, `README_zh.md` | user-facing product promise and short path |
| `docs/index.md` | durable docs hub |
| `docs/codex-engine.md` | Codex launch behavior and engine selection |
| `docs/feishu-bridge.md` | Feishu bridge setup, policy, resource/readback notes |
| `docs/device-chief-and-multidevice-supervisors.md` | device-chief and multi-device supervision model |
| `docs/terminal-supervisor-island.md` | terminal supervisor and Live Activity intent |
| `docs/capture-protocol.md` | stable capture payload/artifact contract |
| `docs/cnb-sync-gateway.md` | sync gateway deployment and API notes |
| `docs/cnb-model.md` | model/profile switching behavior |
| `docs/package-publishing.md` | npm/release operational contract |
| `docs/design-ownership-autonomy.md` | ownership and autonomy design rationale |
| `docs/avatar-generation.md` | generated avatar/onboarding policy |
| `docs/mac-team-host-capacity.md` | Mac resource/capacity assumptions |
| `docs/contribution-wall.md` | contributor/registry presentation |
| `docs/pricing.md` | billing/pricing explainer for docs site |
| `docs/website-frontend.md`, `docs/custom-domain.md` | GitHub Pages site and DNS surface |
| `docs/research_cnb_cloud_recommendation_report.md` | cloud direction research, not core local runtime |
| `bin/README.md` | executable map and documentation rule |
| `tools/*/README.md` | runbooks for specific sidecar/tool surfaces |

For a clean rebuild, treat this file as the primary architecture skeleton and the files above as deeper runbooks. If they disagree with current source, current source wins unless the disagreement is explicitly listed as technical debt here.
