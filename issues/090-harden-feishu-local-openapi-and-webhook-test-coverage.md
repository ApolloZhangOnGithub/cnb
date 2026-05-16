---
number: 90
title: "Harden Feishu local_openapi and webhook test coverage"
state: CLOSED
labels: ["phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
closed: 2026-05-10
---

# #90 Harden Feishu local_openapi and webhook test coverage

**State:** CLOSED
**Labels:** phase:1, infra, priority:p1

---

## 背景

Feishu bridge 从开发适配器 `hermes_lark_cli` 扩展到 `local_openapi`、webhook、setup、watch viewer 和 reply ack。该模块现在包含外部 HTTP、tmux、配置文件 merge、token 校验和命令路由，多数风险来自边界行为，不是普通 happy path。

## 需要补的测试

- `openapi_post` 的 HTTP error、invalid JSON、timeout/URLError 降级。
- tenant token 获取失败时 `send_reply` 不应继续发消息。
- webhook token 同时覆盖 root token 和 header token。
- `setup_config` 保留其它 TOML section，并验证随机 token/默认端口行为。
- `serve_webhook` 或 handler 层的最小 request/response 测试，避免只测纯函数。
- `start_bridge_daemon`/watch viewer 的 tmux command quoting 和 config path 保真。
- `hermes_lark_cli` legacy path 继续有回归测试，防止兼容性被 local_openapi 改坏。

## Acceptance criteria

- 不访问真实 Feishu，不启动真实 tmux，不需要真实 ngrok。
- 使用 monkeypatch/fakes 覆盖 HTTP 和 subprocess。
- `python -m pytest tests/test_feishu_bridge.py -q` 通过。
- 覆盖失败路径输出 detail，便于用户诊断配置错误。

## Parent

Part of #88.
