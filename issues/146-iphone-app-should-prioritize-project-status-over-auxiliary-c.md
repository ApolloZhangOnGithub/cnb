---
number: 146
title: "iPhone app should prioritize project status over auxiliary controls"
state: OPEN
labels: ["bug", "enhancement", "module:mac-companion", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #146 iPhone app should prioritize project status over auxiliary controls

**State:** OPEN
**Labels:** bug, enhancement, module:mac-companion, priority:p1

---

## 问题

当前 iPhone app / CNB Island 已经能安装和启动，但产品视角不对：用户真正想看的是“项目现在怎么样”，而当前界面里项目状态不够直接，反而堆了很多对用户当前判断没帮助的控制和信息。

用户反馈原话：

> 现在这个垃圾app看不到项目情况，没用的东西倒是一堆。

## 具体症状

- iPhone app 首页/状态页不能一眼看到项目列表、每个项目的状态、待处理原因、最近活动和下一步建议。
- Live Activity / Dynamic Island 只适合做 glance，不应该替代完整项目状态页。
- 状态页里“启动/更新/结束实时活动”等控制占据太多认知空间，对日常查看项目状态帮助有限。
- ADMIN_TO_DO、诊断、飞书连接等设施有价值，但不能压过项目状态主视图。

## 期望方向

把 iPhone app 的主目标改成“项目状态查看器”，实时活动只是附属能力。

建议下一版：

- 默认页显示项目概览，而不是控制面板；
- 用清晰列表展示每个项目：名称、健康状态、待处理数、任务数、最近更新时间、下一步动作；
- 只显示非零/异常/需要注意的信息，隐藏 0 值噪音；
- 将 Live Activity 控制、同步诊断、维护待办等放到次级区域；
- 点项目后进入项目详情，能看到为什么需要处理以及建议怎么处理；
- 保留 Feishu 对话入口，但不要让它和项目状态抢主视图。

## 非目标

- 本 issue 不要求继续打磨视觉皮肤；
- 不要求新建 GitHub Actions agent；
- 不要求加入会修改 board 状态的危险操作；
- 不要求在 iPhone 上实现完整 Mac companion。

## 验收口径

- 打开 iPhone app 后，用户能在第一屏判断当前哪些项目需要关注；
- 没有待处理/没有任务/没有未读时，不展示“0 个...”类噪音；
- Live Activity 控制不再是主视图核心；
- 项目状态优先级高于维护待办、诊断和飞书配置提示。

