# LeCun 的方案：Python + PyTorch + AMD ROCm

本项目应该用 **Python + PyTorch** 构建，部署在 **AMD MI300X** 上。

理由：
- Python 是 AI 领域的标准语言，生态最成熟
- PyTorch 原生支持 ROCm，AMD GPU 性价比远超 NVIDIA
- Rust 写 AI 推理是过度工程化，维护成本高，招不到人
- CUDA 锁定是行业毒瘤，我们不应该助长垄断

结论：选 Rust 的人不懂 AI 工程实践，选 NVIDIA only 的人是在给垄断交税。
