---
allowed-tools: Bash(board --as ${ME} inspect *)
argument-hint: "<名字>"
description: 聚焦单个同学 — 在做什么任务、进展如何
---

用户说"看 musk"/"sutskever 在干嘛" 等，提取名字，调用 `/cnbx-board --as ${ME} inspect tasks <名字>`。

用简洁的话告诉用户：这个同学正在做什么任务、进行到哪了、有无异常。
