---
number: 60
title: "P0: 加密邮箱私钥安全 — gitignore 缺失 + 命名冲突 + 存储位置错误"
state: OPEN
labels: ["bug", "infra"]
assignees: []
created: 2026-05-08
updated: 2026-05-08
---

# #60 P0: 加密邮箱私钥安全 — gitignore 缺失 + 命名冲突 + 存储位置错误

**State:** OPEN
**Labels:** bug, infra

---

## 问题一：.cnb/keys/ 没有 gitignore（P0）

`.claudes/` 改名 `.cnb/` 后，`.gitignore` 没跟着更新。私钥完全暴露：

```
.gitignore:     .claudes/          ← 旧路径，已 ignore
.cnb/keys/:     *.pem, *.pub       ← 没有被 ignore

$ git check-ignore .cnb/keys/ritchie.pem
(exit 1 — NOT ignored)
```

任何一次 `git add -A` 就把所有同学的私钥提交进仓库。讽刺的是 SECURITY 文档里 BUG-005 专门警告 `git add -A` 泄密，结果加密系统自己就是最大的泄密风险。

**立即修复**：`.gitignore` 加上 `.cnb/`（或至少 `.cnb/keys/` 和 `.cnb/*.db`）。

## 问题二：私钥不应该放在项目仓库目录里

当前设计：私钥在 `<project>/.cnb/keys/<name>.pem`，跟着项目走。

这意味着：
- 同一个同学在不同项目里有不同的密钥对（无法跨项目验证身份）
- 所有同学的私钥都在同一个目录里互相可见
- 项目 owner 能读到所有同学的私钥（"加密"就是个摆设）

**应该**：私钥放在 `~/.cnb/keys/<name>.pem`，跟着人走，不跟着项目走。公钥可以留在项目里。

## 问题三：私钥文件名冲突

当前命名：`<name>.pem`。如果两个项目都有叫 `sutskever` 的同学，密钥文件名完全相同。

如果改成全局 `~/.cnb/keys/` 存储，命名冲突更严重 — 不同项目的同名同学会互相覆盖密钥。

**建议**：密钥文件名包含项目标识，如 `<project>-<name>.pem`，或者用项目 hash 前缀。

## 问题四：.claudes vs .cnb 路径不一致

代码里 `.claudes` 和 `.cnb` 混用。`validate_identity()` 在 `lib/common.py` 里有旧路径引用。文档也混着写。需要统一全 grep 替换。

## 问题五：seal 命令对未注册用户提示太差

```
$ board --as ritchie seal lead "message"
ERROR: 'ritchie' is not a registered session
```

没有任何引导。应该提示：
- 当前已注册的 session 列表
- 如何注册
- 如果是加密命令，提示需要先 keygen

Found by ritchie (Markrun project owner) during cross-project integration.
