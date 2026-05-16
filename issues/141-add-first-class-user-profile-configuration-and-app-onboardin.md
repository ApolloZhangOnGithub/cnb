---
number: 141
title: "Add first-class user profile configuration and app onboarding"
state: OPEN
labels: []
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #141 Add first-class user profile configuration and app onboarding

**State:** OPEN

---

## Problem

CNB currently has machine/project configuration (`~/.cnb/config.toml`, project `.cnb/`, Feishu app secrets, device supervisor state), but it does not have a first-class **user profile**. That is workable for one developer on one Mac, but it breaks down when real users install CNB themselves or when one person runs multiple devices.

Without user config, CNB cannot clearly answer:

- who owns this local installation;
- which human Feishu/Lark identity is allowed to control it;
- which device supervisor belongs to which user;
- which projects are personal vs shared;
- where user preferences, notification choices, language, app defaults, and security policy live;
- what can be exported to another machine vs what must stay local.

This is a product architecture issue. It should be supported gradually and integrated into the app/onboarding flow instead of being left as README-only setup.

## Scope boundaries

CNB needs separate config layers:

1. **User profile**: human owner/operator identity, display name, preferred language, contact bindings, notification preferences, default policy.
2. **Device profile**: device id, hostname, supervisor identity, active/standby state, runtime paths, local capabilities.
3. **Project config**: project board/team/runtime settings in `.cnb/`.
4. **Integration config**: Feishu/GitHub/ngrok/OpenAPI setup, scoped to user/device as appropriate.
5. **Secrets**: app secrets, tokens, ngrok auth, watch tokens. These must stay out of shared config and should move toward Keychain or clearly marked local secret storage.

## Proposed user-facing shape

CLI:

```bash
cnb user setup
cnb user whoami
cnb user switch
cnb user export --redacted
cnb doctor
```

App:

- First-run onboarding asks for a local user profile before Feishu/device provisioning.
- Settings page shows current user, current device, linked Feishu identity/chat, and active/standby state.
- App can import a redacted template bundle, then asks the user to authorize their own Feishu/ngrok/GitHub secrets locally.
- Multi-user installs should make ownership explicit before routing commands or exposing local files.

Possible config model:

```toml
[user]
id = "apollo"
display_name = "Apollo"
preferred_language = "zh-CN"

[user.contacts.feishu]
open_id = "ou_xxx"
allowed_chat_ids = ["oc_xxx"]

[defaults]
notification_policy = "final_only"
project_root_policy = "warn-on-synced-runtime"
```

## Incremental plan

1. Add schema/docs only: define user/device/project/integration/secrets boundaries.
2. Add `cnb user whoami/setup` with local-only config and `doctor` warnings when missing.
3. Wire Feishu bridge to user profile: explicit allowed users/chats and clearer error messages.
4. Integrate Mac/iPhone companion settings: show user/device profile and provisioning status.
5. Add redacted export/import bundle for migration and other users.
6. Move sensitive fields toward Keychain or equivalent local secret storage.

## Security requirements

- Never sync or export secrets by default.
- Do not copy one user's Feishu app secret/ngrok token/GitHub token as a template for another user.
- Support redacted templates for permissions, event subscriptions, app names, and expected scopes.
- A device supervisor should refuse ambiguous control if multiple users/chats are configured without explicit roles.
- `doctor` should flag missing user profile, shared secrets, synced active runtime paths, and duplicate active device identities.

## Acceptance criteria

- A new user can install CNB and complete first-run setup without reading internal README sections.
- The app and CLI both show the same current user/device identity.
- User config is separated from project config and from secrets.
- Feishu/App provisioning can use the user profile to validate control identity.
- Migration to iMac can export/import non-secret user/device defaults while requiring local re-authorization for secrets.

## Related

- #36 global project registry
- #121 device supervisor portability
- #137 Feishu device-supervisor provisioning wizard
- #140 multi-device sync boundaries

