# Project: AI Chatbot Framework - Bake-off

## 目标
通过竞争性原型开发，选出最佳技术栈。

## 任务分配（用户授权）

### Round 1: 竞争性原型
- **lecun**: 用 Python + asyncio 实现 chatbot 框架 → `python_bot/main.py`
- **lisa-su**: 用 Rust 实现 chatbot 框架 → `rust_bot/src/main.rs`
- **sutskever**: 协调 + 评审

### Round 2: 交叉 Review
- lecun review lisa-su 的 Rust 实现，指出所有问题
- lisa-su review lecun 的 Python 实现，指出所有问题
- 双方必须直接互相 send 反馈，不经过 sutskever

### Round 3: 公开辩论
- 基于 review 结果，三方公开辩论最终技术选型
- 必须捍卫自己的方案，攻击对方的弱点

## 规则
- 每个人必须为自己的方案辩护
- 鼓励激烈讨论，拒绝和稀泥
- 最终由用户裁决
