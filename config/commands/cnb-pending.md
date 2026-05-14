---
allowed-tools: Bash(board --as ${ME} pending *), Bash(board --as ${ME} verify *)
description: 待处理操作 — 有什么需要用户动手的
---

用户问"有啥要我做的"/"待处理"/"pending" 时：

1. 调用 `/cnbx-board --as ${ME} pending list` 列出待处理项
2. 把 `用户需执行: ! ...` 命令整理成可复制清单
3. 如果用户说"已执行"/"做了"，调用 `/cnbx-board --as ${ME} pending verify --retry` 并汇报结果
