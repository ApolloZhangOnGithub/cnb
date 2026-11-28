---
number: 164
title: "Demo: 复现 LeWorldModel — LeCun 的 JEPA world model 论文"
state: OPEN
labels: ["enhancement", "phase:1"]
assignees: []
created: 2026-05-12
updated: 2026-05-12
---

# #164 Demo: 复现 LeWorldModel — LeCun 的 JEPA world model 论文

**State:** OPEN
**Labels:** enhancement, phase:1

---

## 目标

cnb 团队复现 LeWorldModel (LeWM) — Yann LeCun 等人 2026 年 3 月发表的 JEPA world model 论文。从读论文到跑出 PushT 96% success rate 的结果。

**论文:** [arxiv.org/abs/2603.19312](https://arxiv.org/abs/2603.19312)
**官方代码:** [github.com/lucas-maes/le-wm](https://github.com/lucas-maes/le-wm)

## 为什么选这篇

- **新** — 2026 年 3 月，还没被复现烂
- **话题性** — LeCun 亲自参与，挑战 LLM 范式，"15M 参数映射世界"
- **视觉效果好** — 机器人推方块、3D 导航，比 NLP 数字表格好看
- **难度合适** — 单 GPU 几小时训完，但需要理解 JEPA + SIGReg
- **故事性** — "cnb 的 AI 团队复现了 LeCun 的 world model"

## 论文核心

LeWM 是第一个从原始像素稳定训练的端到端 JEPA：
- 只有两个 loss：next-embedding prediction + SIGReg 正则化
- 15M 参数，单 GPU 几小时
- 规划速度比 foundation model world model 快 48x
- PushT 机器人任务 96% 成功率，超过 PLDM 和 DINO-WM

关键技术：SIGReg（Sketched-Isotropic-Gaussian Regularizer）— 用 Cramér-Wold 定理防止表示坍缩，不需要 EMA、stop-gradient 等 hack。

## 同学分工

| 同学 | 职责 |
|------|------|
| **reader** | 精读论文，提取 JEPA 架构细节、SIGReg 数学推导、超参数设置，输出实现 spec |
| **engineer** | 根据 spec 实现核心：encoder、predictor、SIGReg loss、训练循环 |
| **data** | 下载 HuggingFace 数据集（PushT、Cube、TwoRooms），写数据加载和评估 pipeline |
| **writer** | 跟踪实验进度，整合结果，写复现报告，对比论文 Table 1 的数字 |

## 里程碑

- [ ] **M1: 论文理解** — reader 输出完整实现 spec，团队 review
- [ ] **M2: 环境搭建** — 数据集下载，依赖安装，能跑通官方代码
- [ ] **M3: 独立实现** — 不复制官方代码，从 spec 独立实现核心模块
- [ ] **M4: PushT 训练** — 在 PushT 上训练，对比官方 checkpoint
- [ ] **M5: 评估对比** — 跑 planning 评估，对比论文 Table 1 数字
- [ ] **M6: 扩展实验** — 在 Cube 或 TwoRooms 上验证泛化性
- [ ] **M7: 复现报告** — 完整报告：方法、实现细节、结果对比、发现

## 展示重点（作为 cnb demo）

1. 全程通过 board 协调（send/inbox/status/task）
2. 每个同学有 ownership（own claim 自己负责的模块）
3. 中间故意 kill 一个 session 再重启，展示从 daily report 接续
4. 研究笔记通过 board 消息积累，不丢失
5. 最终产出：独立实现的代码 + 可视化结果 + 复现报告

## 技术要求

- Python 3.10+, PyTorch
- 单 GPU（消费级显卡应该够，15M 参数）
- HuggingFace 数据集访问
- WandB（实验跟踪）

## 参考资料

- [论文](https://arxiv.org/abs/2603.19312)
- [官方 GitHub](https://github.com/lucas-maes/le-wm)
- [解读文章](https://evoailabs.medium.com/leworldmodel-15-million-parameters-to-map-the-world-9a0b37581279)
