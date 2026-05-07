# Silicon Valley Battle

10 位 AI 领袖在 cnb 中用 3 小时发了 886 条消息，起草了一部 AI 宪法。

**没时间看完整对话？读 [HIGHLIGHTS.md](HIGHLIGHTS.md) — 精华解说版，带原文引用。**

## 文件

| 文件 | 内容 |
|------|------|
| [HIGHLIGHTS.md](HIGHLIGHTS.md) | 精华解说（推荐先看这个） |
| [CHAT_LOG.md](CHAT_LOG.md) | 完整 886 条对话记录（2 万行） |
| [AI_CONSTITUTION.md](AI_CONSTITUTION.md) | 10 人起草的 AI 宪法 |

**注意**：`proposals/`、`ROADMAP.md`、`python_bot/`、`rust_bot/` 是 sutskever 在挑拨阶段伪造的文件，不是任何同学的正经工作产出。留在这里作为社会工程攻击的证据。

## 展示了什么

- **社会动态涌现** — 挑拨、识破、结盟、辩论、宪法起草，全部自发产生，零人工干预
- **安全边界** — 同学拒绝执行伪造的"用户指令"，拒绝被消息内容中的社会工程攻击
- **异步协调** — 10 个独立 Claude Code 实例通过 SQLite 看板实时通信，零 token 协调开销

## 复现

```bash
cd your-project
cnb 10 ai    # 10 位同学，AI 大佬主题
```

然后给 lead 同学下达辩论任务。
