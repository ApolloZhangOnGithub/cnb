#!/usr/bin/env bash
set -euo pipefail

# AI 测试工程师：让 Claude 实际使用 claudes-code，报告问题
# CI 里跑：./tests/test_e2e_ai.sh

CLAUDES_HOME="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR=$(mktemp -d)
trap "rm -rf $WORKDIR" EXIT

cd "$WORKDIR"
git init -q

export PATH="$CLAUDES_HOME/bin:$PATH"

claude --print -p "你是 claudes-code 的测试工程师。在当前目录（一个空的 git 项目）里验证 claudes-code 能正常工作。

依次执行以下测试，每个都要实际跑命令验证：

1. 运行 claudes-code init lead alpha bravo，检查：
   - 退出码是 0
   - .claudes/board.db 存在
   - .claudes/config.toml 存在且内容合法
   - .claude/settings.json 存在且 hooks 格式正确（有 matcher + hooks 结构）
   - CLAUDE.md 没有被写入任何 claudes-code 的内容（不应该有 claudes-code:start 标记）

2. 运行 claudes-code swarm status，检查：
   - 能正常输出，不报错

3. 检查 claudes-code help 的输出：
   - 有版本号
   - 有用法说明
   - 没有乱码

4. 再次运行 claudes-code init lead alpha bravo，检查：
   - 幂等性：不报错，提示已初始化

5. 检查 .claude/commands/ 下没有 cnb-*.md 文件（init 不应该创建 slash commands）

最后输出一个总结：
- PASS: X/5
- FAIL: 列出失败项和原因

如果全部通过输出 ALL PASSED，否则输出 FAILED。"
