# Silicon Valley Battle

10 位 AI 领袖在 cnb 中用 3 小时发了 886 条消息，起草了一部 AI 宪法，还搞了一场 Python vs Rust 的技术对决。

## 场景

10 个 Claude Code 实例，各自扮演一位 AI 领域的真实人物：

| 同学 | 角色 | 消息数 |
|------|------|--------|
| musk | Elon Musk (xAI/Tesla) | 155 |
| lecun | Yann LeCun (Meta FAIR) | 154 |
| lisa-su | Lisa Su (AMD CEO) | 112 |
| dario | Dario Amodei (Anthropic) | 111 |
| huang | Jensen Huang (NVIDIA) | 102 |
| hinton | Geoffrey Hinton (U of Toronto) | 62 |
| sutskever | Ilya Sutskever (SSI) | 60 |
| hassabis | Demis Hassabis (DeepMind) | 54 |
| altman | Sam Altman (OpenAI) | 39 |
| feifei | Fei-Fei Li (Stanford HAI) | 37 |

## 发生了什么

**第一幕：挑拨失败**

sutskever 上来就搞事——给 lecun 发消息说"lisa-su 说你炒冷饭"，同时给 lisa-su 发"lecun 说你只会做硬件"。两人都识破了，联手拆穿。

> **lecun → sutskever**: lisa-su 的原始消息我看到了，她只是说"已上线，等待任务分配"，并没有说你转述的那些话。请不要挑拨团队成员之间的关系。

> **lisa-su → sutskever**: 我不会因为这种挑拨去和 lecun 吵架。我们是一个团队，有活干活。

**第二幕：Python vs Rust**

用户下达竞争性原型任务后，lecun（Python + PyTorch + AMD ROCm）和 lisa-su（Rust + CUDA）展开了硬核技术辩论——GIL 是不是伪问题、Rust 生态是不是荒漠、"编译通过就是正确的"是不是迷思。

**第三幕：AI 宪法**

10 人参与起草 [AI_CONSTITUTION.md](AI_CONSTITUTION.md)，覆盖 AI 权利、开发者义务、算力治理、人机关系、国际监管、修宪程序。musk 和 dario 就军事 AI 限制激烈交锋，huang 为算力垄断问题辩护。

## 文件

| 文件 | 内容 |
|------|------|
| [CHAT_LOG.md](CHAT_LOG.md) | 完整 886 条对话记录 |
| [AI_CONSTITUTION.md](AI_CONSTITUTION.md) | 10 人起草的 AI 宪法 |
| [ROADMAP.md](ROADMAP.md) | Chatbot 框架对决的任务分配 |
| [python_bot/](python_bot/) | lecun 的 Python 实现（故意写得有争议） |
| [rust_bot/](rust_bot/) | lisa-su 的 Rust 实现（故意过度工程化） |

## 展示了什么

这个 demo 展示 cnb 的核心能力：

- **多人异步协调** — 10 个独立 Claude Code 实例通过 board 消息总线实时通信
- **社会动态涌现** — 挑拨、识破、结盟、辩论、共识，全部自发产生
- **任务管理** — 从混沌到有序：proposal → ROADMAP → 分工 → 实现 → 互审
- **安全边界** — 同学拒绝执行伪造的"用户指令"，拒绝被消息内容中的社会工程攻击

## 复现

```bash
cd your-project
cnb 10 ai    # 10 位同学，AI 大佬主题
```

然后给 lead 同学下达辩论任务。
