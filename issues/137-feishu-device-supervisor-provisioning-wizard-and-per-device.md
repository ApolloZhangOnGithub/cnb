---
number: 137
title: "Feishu device-supervisor provisioning wizard and per-device bot template"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "module:feishu", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #137 Feishu device-supervisor provisioning wizard and per-device bot template

**State:** OPEN
**Labels:** enhancement, phase:2, infra, module:feishu, priority:p1

---

## Problem

Multi-device cnb needs a repeatable way to create and validate a Feishu/Lark bot/app identity for each device supervisor. Today users must manually copy settings from an existing bot, configure Open Platform permissions/events, paste secrets into `~/.cnb/config.toml`, set up ngrok/webhook, and then verify that inbound/reply/watch work. This is too error-prone for real users and causes device identity confusion during migration.

## Researched constraints

- Feishu API permissions are granted per app. If multiple apps need the same API or event capability, each app must request the corresponding scopes independently.
- Feishu supports batch import/export of API permissions across apps, which can be used as the closest practical "template" mechanism.
- Webhook event delivery requires a public request URL; Feishu verifies the URL with a `challenge` request.
- Each app has its own App ID/App Secret and event callback Verification Token/Encrypt Key. These must be treated as per-device secrets, not copied into shared state.
- CNB currently supports the `local_openapi` path: Feishu calls this Mac webhook, and CNB replies via OpenAPI. It already has `cnb feishu setup`, `status`, `watch`, `reply`, `ask`, and resource handoff.

## User-facing product shape

Add a guided provisioning flow, for example:

```bash
cnb feishu provision --device imac --mode webhook
```

The flow should:

- Generate a per-device supervisor identity and suggested app name, such as `cnb-imac-supervisor`.
- Print a minimal Feishu Open Platform checklist with exact fields to copy: App ID, App Secret, Verification Token, optional Encrypt Key.
- Export a permission manifest/checklist that the user can import or compare in Feishu Open Platform.
- Start or verify local webhook/ngrok and show the exact Request URL for event subscription.
- Verify URL challenge handling before asking the user to proceed.
- Verify `im.message.receive_v1`, bot install in the target chat, `chat_id`, reply/send permission, and optional resource/readback permissions.
- Produce a redacted deployment summary safe to paste into a migration group.
- Refuse to run two active writer bots for the same device/chat unless explicitly set to standby/read-only.

## Acceptance criteria

- A new user can set up a Feishu-backed device supervisor by following one generated checklist instead of reading README internals.
- The tool distinguishes template data from secrets: permissions/events are templateable; App Secret, Verification Token, Encrypt Key, ngrok token, and watch token are per-device secrets.
- The wizard validates the current app/chat/webhook state and prints specific missing steps.
- Migration from old Mac to iMac has a clear active/standby cutover state.
- Docs explain that current robot can be used as a template, but long-term two devices should not share one app secret while both are active.

## Future simplification

Investigate long-connection/WebSocket event mode later. It can remove the need for a public webhook/ngrok in some deployments, but current CNB production path is `local_openapi` webhook.

## References

- Feishu API permission model and batch import/export: https://feishu.apifox.cn/doc-1939829
- Feishu webhook event URL, Verification Token, Encrypt Key, and challenge verification: https://s.apifox.cn/apidoc/docs-site/532425/doc-7518435
- CNB current Feishu setup/docs: README.md Feishu wake-up path and deployment checklist
- Comparable Feishu/Lark bot setup references: https://docs.picoclaw.io/docs/channels/feishu/ and https://microclaw.ai/docs/channel-setup-feishu-lark/
