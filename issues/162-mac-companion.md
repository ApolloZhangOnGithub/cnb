---
number: 162
title: "Mac Companion 产品升级总纲"
state: OPEN
labels: ["enhancement", "phase:1", "module:mac-companion", "priority:p0"]
assignees: []
created: 2026-05-11
updated: 2026-05-11
---

# #162 Mac Companion 产品升级总纲

**State:** OPEN
**Labels:** enhancement, phase:1, module:mac-companion, priority:p0

---

## 背景

Mac Companion 当初在 board 只有基础消息+任务功能时开发，现在 board.db 已有 20 个表（ownership, bugs, proposals, mail, threads, kudos, git_locks, session_runs 等），app 只查了其中 4 个。产品已远远落后于项目管理能力。

本 issue 是 companion 产品升级的总纲，统领散落的 #127 #139 #146 #147 和后续工作。

## 一、数据覆盖缺失

App 目前只读取：
- [x] pending_actions（计数）
- [x] tasks（active/pending）
- [x] inbox/messages（unread 计数）
- [x] sessions（总数/blocked）

缺失的表（按优先级排序）：
- [ ] **ownership** — 核心产品功能，必须展示
- [ ] **bugs** — OPEN bug 列表和严重度
- [ ] **proposals** — 提案状态
- [ ] **mail/mailbox** — 站内邮件
- [ ] **threads/thread_replies** — 讨论区
- [ ] **session_runs** — session 运行历史，用于健康判断
- [ ] **suspended** — 挂起的 session
- [ ] **git_locks** — 锁状态
- [ ] **kudos** — 表彰
- [ ] **votes** — 投票
- [ ] **notification_log** — 通知记录
- [ ] **files** — 文件管理

## 二、App Icon

项目有 favicon.svg（绿色 C logo），但 Mac Companion 没有 app icon：
- [ ] 从 favicon.svg 生成 AppIcon.icns（多尺寸）
- [ ] 写入 build script 的 Info.plist（CFBundleIconFile）
- [ ] 菜单栏图标也应该用品牌 icon 而不是 SF Symbol

## 三、TUI 双模式

当前 TUI 是只读 Web 视图（`cnb feishu watch-serve`）。提议设计两个模式：

### 只读模式（当前）
- 面板展示 board 状态、消息流、同学状态
- 适合用户快速了解情况

### 交互模式（新增）
- 嵌入真实的 tmux session（通过 `NSTask` + pseudo-terminal）
- 可以直接在 app 内操作 `board --as <name>` 命令
- 可以看到并 attach 到同学的 tmux pane
- 相当于把 Terminal.app 的 cnb 操作内置到 companion 里

技术路线：macOS 的 `openpty()` + `NSTask` 可以创建 pseudo-terminal，用 SwiftTerm 或类似库渲染 VT100。也可以简单地用 `tmux attach` 嵌入 WebSocket terminal（ttyd/gotty 方案）。

## 四、设备主管状态

（关联 #139）
- [ ] 读取 `~/.cnb/live_state.json` 显示设备主管在线状态
- [ ] 显示 Feishu bridge 和 Mac Companion 自身运行状态
- [ ] 显示 `~/.cnb/device-supervisor/dailies/` 最近日报摘要

## 五、版本管理（已实施）

- [x] VERSION 文件作为单一真相源
- [x] build_meta.json 嵌入 app（version, build number, date, git SHA）
- [x] 设置页显示版本信息
- [x] 构建产物外置到 `~/Applications/` 和 `~/.cnb/build-cache/`

## 六、管理方式讨论

Companion 作为独立子产品，零散 issue 不适合管理演进。建议：
- 本 issue 作为总纲 + checklist
- 重大子项（如 TUI 交互模式）可拆独立 issue 并在此交叉引用
- Bug 类（如 #127）保持独立 issue
- 产品决策（如 #147 native vs Electron）保持独立 issue 但在此引用

与 ROADMAP「规模化准备 → #96 终端主管同学 Mac companion（一期）」对齐。
