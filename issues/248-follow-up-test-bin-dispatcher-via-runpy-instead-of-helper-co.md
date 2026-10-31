---
number: 248
title: "follow-up: test bin/dispatcher via runpy instead of helper copies (per #243 review)"
state: OPEN
labels: ["phase:2", "infra", "priority:p2"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #248 follow-up: test bin/dispatcher via runpy instead of helper copies (per #243 review)

**State:** OPEN
**Labels:** phase:2, infra, priority:p2

---

## ROADMAP check

Per ROADMAP.md, 这属于运营基础 / 测试质量 — 与 #88 testing roadmap 同 sprint 但 scope 单独。

## Context

PR #243 (dispatcher auto-reload, #235) 跟之前的 `_acquire_pidlock` 测试沿用了 "测试文件本地拷贝被测函数" 的 pattern。bezos 在 peer review 指出：

> tests mirror dispatcher 的 `_max_mtime` 而不是执行真实 script，regression 抓不到

这是真问题。bin/dispatcher 是 script (无 .py)，不能直接 import，所以测试 file 里复制了一份 `_max_mtime` / `_code_changed`。这意味着：

- production 函数和 test 函数可能 drift 后 test 仍 pass（false-negative）
- script-level 改动（imports, side effects, main() 逻辑）测试覆盖不到

## Desired

用 `runpy.run_path("bin/dispatcher", run_name="__main__")` 或 `importlib.util.spec_from_file_location` 直接 import script 模块，然后从模块取 `_max_mtime` / `_code_changed` / `_acquire_pidlock`。

## Scope

替换 `tests/test_dispatcher.py` 现有 3 个 class 的本地函数引用。如果同 pattern 在其他 `tests/test_*.py` 也有，一并修。

## Acceptance

- [ ] 不再有本地 helper 拷贝
- [ ] 测试 import 真 script
- [ ] 现有 15 测试仍 pass
- [ ] 增 1 测试验证 'production drift 会被 catch'

## Owner

待指定。建议 follow #243 land 之后做。
