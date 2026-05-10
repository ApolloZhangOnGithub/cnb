# cnb 云化与 Claude Code / Codex 集成建议

日期：2026-05-10  
用途：可转发给 cnb 开发者，作为 roadmap / issue proposal 讨论稿。

## 结论

推荐路线不是完整 SaaS 化，而是 **Remote Workspace Mode**：

> cnb 保持组织层 / 调度层 / 记忆层；Claude Code 和 Codex 继续做执行引擎。第一阶段只把执行环境搬到远端 dev container、Codespaces、SSH remote 或 GitHub runner，让 Mac 只当控制台。

这条路能最大程度保留现有 Claude Code / Codex 性能，同时释放 Mac 资源，并且几乎不增加额外 token。

## 为什么这是当前最可行路线

- 保留性能：核心仍是 Claude Code / Codex 本体，不重写弱版 coding agent。
- 节省 token：不新增 lead agent 复述、总结、监督另一个 agent；cnb 只传最小任务包。
- 释放 Mac：测试、构建、语言服务器、终端、agent 执行都可以放在云端容器或 runner。
- 工程风险低：先用官方已有接入面：Claude devcontainer / GitHub Action / Agent SDK，Codex remote app-server / exec / GitHub Action / Cloud。
- 符合 cnb 现有定位：cnb 自己强调组织层、ownership、handoff，而不是替代 Claude Code/Codex 执行代码。

## 方案排序

| 优先级 | 方案 | 保留现有能力 | 额外 token | 释放 Mac | 综合判断 |
|---:|---|---:|---:|---:|---|
| 1 | Claude Code in devcontainer / Codespaces | 很高 | 极低 | 高 | Claude Code 主线首选 |
| 2 | Codex remote app-server / SSH remote | 高 | 极低 | 高 | Codex 交互式远端首选 |
| 3 | Claude/Codex GitHub Actions | 中高 | 低 | 最高 | 适合 issue→PR、CI 修复、review、迁移 |
| 4 | Codex Cloud | 高 | 低 | 最高 | 适合后台并行 worker |
| 5 | Claude Agent SDK / Codex SDK 自建 worker | 潜在很高 | 可控 | 高 | 长期正确，但不应第一阶段主线 |
| 6 | MCP / cnb board 工具层 | 辅助 | 低到中 | 低 | 适合状态查询和回写，不适合主执行 |

## 建议他们现在做的最小可行功能

### Feature proposal：Remote Workspace Mode

让 cnb 支持把一个项目绑定到远端 workspace，并在远端运行 Claude Code / Codex / cnb board commands。Mac 只保留控制台、状态查看和少量本地命令。cnb 不新增 AI 管理 agent，不复制 Claude/Codex 的 agent loop。

### MVP 范围

1. 新增 `cnb remote doctor`：检查远端是否具备 Python、tmux、git、gh、Claude Code、Codex、cnb、repo、secrets。
2. 新增 `.devcontainer` / Codespaces 模板：安装 cnb、Claude Code CLI、Codex CLI，并保留 `.cnb/` 状态目录和认证方式。
3. 新增 `remote target` 概念：local、ssh、codespaces、github-action。先实现配置与健康检查，不急着做复杂调度。
4. Claude Code 路线：优先在远端 devcontainer / Codespaces 中运行原生 Claude Code，必要时通过 hooks 把 SessionEnd、PostToolUse、StopFailure 等事件写回 cnb ledger。
5. Codex 路线：交互式优先 remote app-server；非交互式任务优先 `codex exec --json` 或 Codex GitHub Action。
6. board 保持低 token：cnb 只向 Claude/Codex 注入任务 ID、owner、相关文件、验收标准、短摘要；不要注入完整消息历史。

### 非目标

- 不要第一阶段做完整 Web dashboard + 托管 SaaS。
- 不要第一阶段重写 Claude Code / Codex 的编码 agent loop。
- 不要第一阶段让一个额外 lead LLM 监督所有 worker。
- 不要把云化等同于“云上开很多 tmux session”。tmux 可以作为临时兼容层，但不应该成为终局。

## 推荐架构

Issue / 用户任务 → cnb 判断 owner 和执行后端 → 远端 workspace 启动 Claude Code 或 Codex → agent 执行并跑测试 → 结果通过 hooks / CLI / action output 写回 cnb ledger → 人类 review PR 或接管异常。

| 组件 | 应该负责 | 不应该负责 |
|---|---|---|
| cnb | owner 路由、任务账本、上下文压缩、健康检查、handoff | 直接生成大量代码、替代 Claude/Codex、额外长链推理 |
| Claude Code | 复杂代码理解、重构、跨文件修改、测试执行、交互式 coding | 管理所有 agent 状态、保存长期组织记忆 |
| Codex | CI/PR review、codex exec、后台 patch、批量任务、Codex Cloud 并行任务 | 替代 cnb 的 ownership / handoff 系统 |
| GitHub Actions | 异步任务、PR review、CI failure 修复、迁移脚本 | 承担强交互式结对编程体验 |
| MCP / hooks | 按需查状态、记录事件、压缩上下文、阻断危险操作 | 全量同步聊天记录、作为主要执行环境 |

## 可直接发给开发者的推荐文本

**Issue title:** Add Remote Workspace Mode: keep Claude Code/Codex as execution engines while moving agent work off the local Mac

**Body:**

The most practical cloud path for cnb is not a full hosted SaaS yet. I suggest a Remote Workspace Mode: cnb remains the ownership / routing / handoff / ledger layer, while Claude Code and Codex remain the execution engines. The goal is to move the workspace, shell, build/test commands, and agent runtime to a remote dev container, Codespaces, SSH host, GitHub runner, or Codex Cloud, while keeping cnb token overhead almost unchanged.

MVP: provide a `.devcontainer` / Codespaces template, `cnb remote doctor`, and a `remote target` config for local / ssh / codespaces / github-action. For Claude Code, prioritize running the native Claude Code CLI in the remote container and use hooks to write session/tool/test summaries back to cnb. For Codex, support remote app-server for interactive work and `codex exec --json` / Codex GitHub Action for background tasks.

Non-goals: do not build a full SaaS runtime first, do not replace Claude Code/Codex with a custom coding agent, and do not add another LLM lead that summarizes or supervises every worker. The point is to preserve current coding-agent capability, reduce Mac load, and avoid additional token burn.

## 参考资料

- cnb README / GitHub repository: https://github.com/ApolloZhangOnGithub/cnb
- cnb ROADMAP: https://github.com/ApolloZhangOnGithub/cnb/blob/master/ROADMAP.md
- Claude Code Development Containers: https://code.claude.com/docs/en/devcontainer
- Claude Code GitHub Actions: https://code.claude.com/docs/en/github-actions
- Claude Agent SDK Overview: https://code.claude.com/docs/en/agent-sdk/overview
- Claude Code Hooks Reference: https://code.claude.com/docs/en/hooks
- Claude Code Costs: https://code.claude.com/docs/en/costs
- Codex CLI Reference: https://developers.openai.com/codex/cli/reference
- Codex CLI Features - Remote app-server: https://developers.openai.com/codex/cli/features
- Codex GitHub Action: https://developers.openai.com/codex/github-action
- Codex Web / Cloud: https://developers.openai.com/codex/cloud
