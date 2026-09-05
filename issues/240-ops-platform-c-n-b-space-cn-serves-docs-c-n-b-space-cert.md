---
number: 240
title: "[Ops] platform.c-n-b.space 证书 CN 不匹配（serves docs.c-n-b.space cert）"
state: OPEN
labels: ["bug", "phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #240 [Ops] platform.c-n-b.space 证书 CN 不匹配（serves docs.c-n-b.space cert）

**State:** OPEN
**Labels:** bug, phase:1, infra, priority:p1

---

## Symptom

\`\`\`bash
$ echo "" | openssl s_client -connect platform.c-n-b.space:443 \\
    -servername platform.c-n-b.space -verify_return_error 2>&1 | grep -E "depth=0|verify"
depth=0 CN=docs.c-n-b.space
verify return:1
\`\`\`

证书 CN 是 \`docs.c-n-b.space\`，被 SNI 为 \`platform.c-n-b.space\` 的连接拿来用，证书链对该 host 无效。

hstspreload.org 直接拒了：

\`\`\`json
{
  "code": "domain.tls.invalid_cert_chain",
  "message": "https://platform.c-n-b.space uses an incomplete or invalid certificate chain."
}
\`\`\`

## Why it matters

1. 严格的 client（HSTS-aware 浏览器、Go \`crypto/tls\` 默认配置、CI 工具）拒绝握手。
2. 阻塞 HSTS preload 提交：apex 的 preload check 也会顺带验所有 subdomain 的证书链，多 SAN 不全则整体拒。
3. 之前 #214 的根因之一 — 部分 client 看到 invalid cert 直接 close，看起来"网络问题"。

## Fix

签一张多 SAN cert（推荐 Let's Encrypt R13 / R14）覆盖：

\`\`\`
SAN: c-n-b.space
SAN: platform.c-n-b.space
SAN: blog.c-n-b.space
SAN: docs.c-n-b.space
\`\`\`

或为 \`platform\` 单独签一张包含 \`platform.c-n-b.space\` 的 cert，绑到对应的 server block。

证书目前是 Let's Encrypt R13 签发（valid \`May 17 04:44:42 2026 GMT — Aug 15 04:44:41 2026 GMT\`），重签流程已有，加一个 \`-d platform.c-n-b.space\` 即可。

## ROADMAP context

属于"运营基础"。与 #214 直接关联但不重叠（#214 是 user-facing 症状 + workaround，本 issue 是 server-side fix）。与 #239 (apex HTTP→HTTPS redirect) 都是 HSTS preload 提交的前置 blocker。

## Reproduction

\`\`\`bash
echo "" | openssl s_client -connect platform.c-n-b.space:443 \\
    -servername platform.c-n-b.space -verify_return_error 2>&1 | head -10
# 当前: depth=0 CN=docs.c-n-b.space
# 期望: depth=0 CN=platform.c-n-b.space (或包含 SAN: platform.c-n-b.space)
\`\`\`

## Verification

修完后：

\`\`\`bash
curl -sX GET "https://hstspreload.org/api/v2/preloadable?domain=c-n-b.space" | jq
# 期望 errors 列表不再包含 domain.tls.invalid_cert_chain
\`\`\`

Owner: server admin (待 assign)。
