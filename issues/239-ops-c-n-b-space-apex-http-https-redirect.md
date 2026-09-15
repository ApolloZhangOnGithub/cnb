---
number: 239
title: "[Ops] c-n-b.space apex 缺 HTTP → HTTPS redirect"
state: OPEN
labels: ["bug", "phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #239 [Ops] c-n-b.space apex 缺 HTTP → HTTPS redirect

**State:** OPEN
**Labels:** bug, phase:1, infra, priority:p1

---

## Symptom

\`\`\`bash
curl -I http://c-n-b.space
HTTP/1.1 403 Forbidden
Server: Beaver
\`\`\`

应当返回 \`301\` / \`302\` 到 \`https://c-n-b.space/\`。

## Why it matters

ICP/Beaver 拦截 plain HTTP，client 收到 403 而不是被重定向到 HTTPS，造成两类故障：

1. 任何走 HTTP-first 的 client（curl 默认、很多脚本、爬虫、第三方集成）拿不到内容，看起来站点挂了。这是 #214 的根本症状。
2. **HSTS preload 提交无法通过**。hstspreload.org 检查 \`c-n-b.space\` 返回：

\`\`\`json
{
  "code": "redirects.http.no_redirect",
  "message": "\`http://c-n-b.space\` does not redirect to \`https://c-n-b.space\`."
}
\`\`\`

preload list 收录要求 apex 必须返回 HTTP → HTTPS 重定向。没修这条，#214 长期 fix（让 HSTS 收录到 Chromium preload）就推不动。

## Fix

server-side nginx / 入口反代加一条：

\`\`\`nginx
server {
    listen 80;
    server_name c-n-b.space platform.c-n-b.space blog.c-n-b.space docs.c-n-b.space;
    return 301 https://$host$request_uri;
}
\`\`\`

或在阿里云 SLB / ICP 入口层做同样的事 — 关键是 80 端口要在 Beaver 之前回到我们手里。

## ROADMAP context

属于"运营基础"。与 #214 直接关联但不重叠（#214 是 user-facing 症状 + workaround，本 issue 是 server-side fix）。与 [Site HSTS/ICP memory] 一致。

## Reproduction

\`\`\`bash
curl -I http://c-n-b.space
# 当前: 403 Beaver
# 期望: 301 Location: https://c-n-b.space/
\`\`\`

## Verification

修完后：

\`\`\`bash
curl -sX GET "https://hstspreload.org/api/v2/preloadable?domain=c-n-b.space" | jq
# 期望 errors 列表不再包含 redirects.http.no_redirect
\`\`\`

Owner: server admin (待 assign)。
