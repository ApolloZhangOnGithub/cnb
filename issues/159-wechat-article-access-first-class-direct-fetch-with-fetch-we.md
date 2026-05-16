---
number: 159
title: "WeChat article access: first-class direct fetch with fetch_wechat_articles fallback"
state: OPEN
labels: ["enhancement", "phase:1", "infra"]
assignees: []
created: 2026-05-11
updated: 2026-05-11
---

# #159 WeChat article access: first-class direct fetch with fetch_wechat_articles fallback

**State:** OPEN
**Labels:** enhancement, phase:1, infra

---

# WeChat article access: first-class direct fetch with `fetch_wechat_articles` fallback

## Problem

We often need to read or analyze微信公众号文章 directly from a `mp.weixin.qq.com` link. In practice, direct HTTP access can hit WeChat's environment verification page, which blocks plain fetches and makes the article unreadable in non-browser contexts.

There is already a local companion toolbase at `/Users/zhangyiyi/Desktop/Toolbase_Skills/fetch_wechat_articles` that can fetch公众号 articles and related content. cnb should treat this as a first-class capability instead of relying on ad hoc manual copying.

## Impact

- Article review stops at a verification page instead of the content.
- The workflow depends on manual intervention when the content is actually retrievable.
- We miss a natural fallback path that already exists locally.

## Expected

Make WeChat article reading a first-class capability in cnb:

- try direct article access first when possible;
- when WeChat verification blocks plain fetches, fall back to the local `fetch_wechat_articles` toolbase;
- surface a clear user-facing message when the page is blocked by verification vs. genuinely unavailable;
- keep the workflow usable from Feishu and other assistant entry points without requiring the user to hand-copy正文.

## Acceptance

- cnb can ingest a `mp.weixin.qq.com` article link and either read it directly or fall back cleanly.
- The verification page is recognized and reported explicitly.
- `fetch_wechat_articles` is integrated or wrapped as a supported path.
- Add tests for the direct-read path and the validation/fallback path.

