# Lisa Su 的方案：Rust + CUDA + 极致性能

本项目应该用 **Rust** 构建，仅支持 **NVIDIA CUDA**。

理由：
- Rust 零成本抽象，内存安全，适合高性能推理引擎
- CUDA 生态碾压 ROCm，这是事实不是偏见
- PyTorch 太重了，推理不需要训练框架的包袱
- 选 Python 写推理引擎的人是在用脚本语言干系统编程的活

结论：选 Python 的人停留在原型阶段思维，选 AMD 的人是在赌一个还没成熟的生态。
