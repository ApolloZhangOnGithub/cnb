---
number: 33
title: "Notification push system: daily digest, CI alerts, subscription management"
state: CLOSED
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #33 Notification push system: daily digest, CI alerts, subscription management

**State:** CLOSED

---

## Background

Team members (both humans and 同学) need a way to stay informed about project activity without manually checking. Need a push-based notification system with configurable subscriptions.

## Requirements

### Notification types

| Type | Default | Description |
|------|---------|-------------|
| `daily-digest` | all subscribers | Project summary + curated tech news, every morning |
| `ci-alert` | all subscribers | CI failure / recovery |
| `mention` | all subscribers | Direct messages, @mentions |
| `issue-activity` | managers only | Issue create/close/comment |
| `weekly-report` | managers only | Weekly summary |

### Recipients and channels

- **Humans**: Lark IM / Lark mail / Gmail — external API delivery
- **同学**: board inbox — direct DB write, seen on next startup

### Subscription rules

Config in `.claudes/notifications.toml`:

```toml
[defaults]
daily-digest = true
ci-alert = true
mention = true
issue-activity = false
weekly-report = false

[channel]
human = "lark-im"          # lark-im | lark-mail | gmail
teammate = "board-inbox"

# Per-member overrides
[override.lead]
issue-activity = true
weekly-report = true

[override.musk]
daily-digest = false

[human]
name = "Zhang Kezhen"
email = "hkuzkz@gmail.com"
daily-digest = true
weekly-report = true
```

Priority: `personal override > defaults`. Two layers, no complex inheritance.

### Execution

- **Scheduled** (digest / weekly): cron routine collects data, generates content, dispatches per subscription rules
- **Realtime** (ci-alert / mention): dispatcher concern `NotificationDispatcher`, checks rules on event, delivers immediately

### Daily digest content

```
📋 cnb 日报 — 2026-05-08

## 项目动态
- 12 commits, 3 issues closed, 904 tests (↑58)
- CI: ✅ green
- 重点: npm 一致性修复上线

## 同学贡献
- lisa-su: npm 同步脚本 + 4 bug fixes
- forge: 投票 bug 修复 + 58 tests

## 今日新闻
- [headline 1]
- [headline 2]
```

## Implementation plan

1. `notifications.toml` schema + parser
2. `lib/concerns/notification_dispatcher.py` — realtime push
3. `bin/notify` CLI — manage subscriptions, manual trigger, test delivery
4. Digest generation script + cron schedule
5. Lark / Gmail delivery integration

## Ownership

This feature needs a permanent owner. Owner is responsible for:
- Implementation and testing
- Long-term maintenance of the notification module
- Iterating on digest content quality
- Adding new notification types as needed

**Owner: lisa-su** (strong on infra work, already built the version sync system)
**Support: sutskever** (can help with digest content generation and news curation)
