---
number: 55
title: "Experiment: spaced review — do tongxue need to revisit cold context?"
state: CLOSED
labels: ["experiment", "org-design"]
assignees: []
created: 2026-05-08
updated: 2026-05-09
closed: 2026-05-09
---

# #55 Experiment: spaced review — do tongxue need to revisit cold context?

**State:** CLOSED
**Labels:** experiment, org-design

---

## Hypothesis

冷文档（旧日报、历史 issue、archive 里的设计决策）中可能藏着当前工作需要的信息。热文档（CLAUDE.md、ROADMAP）需要定期回顾确认是否还准确。

人类学习中，间隔复习（spaced repetition）是已验证有效的方法。高考状元和普通学生的差异往往不在智力，在于复习策略。LLM 同学是否也需要类似机制？

## 关键区别

LLM 同学没有遗忘曲线——但有 **context window 限制**。不是"忘了"，是"没加载"。所以问题不是"要不要复习"，而是"什么时候加载什么"。

这和人类的问题结构不同但本质相似：
- 人类：记忆衰退 → 需要复习
- LLM：context 有限 → 需要选择性加载

## 实验设计

1. **冷文档价值测试**：给同学一个 task，不提供历史日报。再给同类 task，提供相关的旧日报。对比完成质量和速度
2. **热文档准确性审计**：让一个同学专门审查 CLAUDE.md 和 ROADMAP，标记过时内容。衡量过时率
3. **智能加载实验**：task 开始前，根据 task description 自动检索相关历史文档加载到 context。对比盲做

## 与认知科学的交叉

这确实是社会学/认知科学领域：
- Ebbinghaus 遗忘曲线 → LLM 的 context eviction 策略
- 间隔重复 (Anki) → 定期重新加载关键文档
- 专家直觉 (无需复习的"神人") → 某些信息编码在代码/架构中，不需要显式文档

## ROADMAP 关系

与 #54（context health）强相关。#54 侧重裁剪，本 issue 侧重"该保留和复习什么"——是同一个问题的两面。
