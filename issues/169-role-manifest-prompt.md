---
number: 169
title: "Role manifest 驱动的命令分层、prompt 生成和越界校验"
state: CLOSED
labels: ["phase:1", "infra", "org-design"]
assignees: []
created: 2026-05-12
updated: 2026-05-12
closed: 2026-05-12
---

# #169 Role manifest 驱动的命令分层、prompt 生成和越界校验

**State:** CLOSED
**Labels:** phase:1, infra, org-design

---

## 背景

cnb 的角色（用户、设备主管、项目经理、项目成员）边界散落在 system prompt、CLAUDE.md、config.toml 各处，没有统一定义。结果是：

1. **命令混乱** — `cnb feishu --help` 对所有人显示所有命令，同学不知道哪些是自己该用的
2. **prompt 手写** — 每个角色的 system prompt 手工维护，和实际权限脱节
3. **没有边界执行** — 项目成员可以执行管理命令，没有任何提示

## 方案

`roles/*.yaml` manifest 已定义 7 个角色（main_user, admin_user, device_user, tx_super_admin, tx_device_manager, tx_project_manager, tx_project_member），每个包含 commands（primary/secondary/infra 三层）、scope、boundaries。

需要实现三个集成点：

### 1. CLI 帮助分层
`cnb --help` 和 `board --help` 读取当前角色的 manifest，默认只显示 primary 命令，`--all` 显示全部。

### 2. System prompt 自动生成
同学的 system prompt 从 manifest 的 commands + scope + boundaries 自动生成，不再手写。确保 prompt 和实际权限始终一致。

### 3. 越界提示
同学执行不在自己 primary/secondary 命令列表中的命令时，打印提示："这个命令不在你的 {role.label} 职责范围内，确认要执行吗？"不阻止，只提醒。

## 与 ROADMAP 关系

直接对应第一优先级「Lead 角色定义 #64」— 把角色从隐式知识变成显式数据。也为 ownership 路由 #87 提供角色上下文。
