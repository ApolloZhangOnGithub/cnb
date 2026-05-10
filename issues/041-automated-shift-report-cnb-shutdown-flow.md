---
number: 41
title: "Automated shift report: cnb shutdown flow"
state: OPEN
labels: ["phase:2", "infra"]
assignees: []
created: 2026-05-07
updated: 2026-05-09
---

# #41 Automated shift report: cnb shutdown flow

**State:** OPEN
**Labels:** phase:2, infra

---

## Problem

当前下班流程全靠手动：lead 广播收工 → 等 ack → 手写日报 → 手建轮次目录。容易遗漏，格式不统一。

## 实际案例

Shift 001（2026-05-08）手动操作：
1. `board send all "下班通知..."` — 手动广播
2. Monitor 等 ack — 手动盯
3. 手动创建 `.claudes/dailies/001/` 目录
4. 手动写 `_meta.md`（轮次汇总）和 `lead.md`（个人日报）
5. 同学们的日报没有自动收集

## Expected behavior

`cnb shutdown` 一条命令完成整个流程：

1. **广播收工** — 通知所有同学保存状态
2. **等待 ack** — 轮询直到所有活跃同学 ack，超时强制（可配置）
3. **自动收集日报** — 每个同学的 status + 最近 commits + task 完成情况，自动生成 `{name}.md`
4. **生成 `_meta.md`** — 轮次号自增，自动汇总：参与同学、ack 时间、commits 数、issues 关闭/推进/新增、已知问题
5. **个人日报补充** — 同学可以在 ack 时附带自由文本（手写部分），追加到自动生成的日报里
6. **关停** — 确认全部保存后停掉 tmux sessions

## 目录结构

```
.claudes/dailies/
  001/
    _meta.md        ← 自动生成的轮次汇总
    lead.md         ← 自动 + 手写
    forge.md
    lisa-su.md
  002/
    ...
```

## 轮次编号

自增整数，存在 `.claudes/dailies/.next_shift`（简单文件，内容就是下一个编号）。

## 规范

- 每次下班必须走 `cnb shutdown`，不能 sleep 60 就杀
- 每个同学下班前写日报（自动部分 + 可选手写部分）
- `_meta.md` 由系统自动生成，不手动编辑
