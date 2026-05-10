---
number: 89
title: "Add capture ingest integration and error-path tests"
state: CLOSED
labels: ["phase:1", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #89 Add capture ingest integration and error-path tests

**State:** CLOSED
**Labels:** phase:1, infra

---

## 背景

`lib/capture_ingest.py` 是近期新增的 public entrypoint，负责从浏览器/外部捕获 payload 写入 `.cnb/captures` 或 `~/.cnb/captures`，同时承担脱敏、HTML 清理、截图写入、manifest/content 生成、board 通知和 CLI `cnb capture` round trip。

当前基础测试覆盖了 artifact 写入、HTML 清理、列表排序和 global store，但还缺少关键集成/错误路径。

## 需要补的测试

- 写入 screenshot base64 时生成 `visible.png` 并更新 manifest。
- 无效 screenshot base64 返回 `CaptureError`，不能留下误导性 manifest。
- 相同 capture id 冲突时稳定写入 `-2` 后缀。
- `notify` 使用真实临时 `board.db` schema 写入 messages/inbox。
- `project` 参数直接指向 `.cnb/` 或 legacy `.claudes/` 时能正确解析。
- CLI `ingest/list/show` 至少有一个 round trip，含 `--no-notify`。
- `list_captures` 忽略坏 manifest，不因一个坏目录破坏整个列表。

## Acceptance criteria

- 新增测试不触碰真实 `~/.cnb`。
- 相关测试可单独通过：`python -m pytest tests/test_capture_ingest.py -q`。
- 全局门禁仍通过：ruff、format、mypy、pytest。

## Parent

Part of #88.
