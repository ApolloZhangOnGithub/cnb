# cnb model (别名 `m`)

切换 Claude Code 的 LLM provider / model。

## 使用

```bash
cnb m d              # 切到 deepseek（d 是 deepseek 的别名）
cnb m deepseek       # 同上，完整名
cnb m a              # 切回 Anthropic 原生（a 是 default 的别名）
cnb m d -s project   # 只对当前项目生效
cnb m d -s global    # 全局生效
cnb m current        # 查看当前配置
cnb m list           # 列出可用 profiles
cnb m                # 帮助
```

`-s` = `--scope`。切换后重启 Claude Code 生效。

## Slash 命令

在 Claude Code 里直接用：

```
/cnb-model d               切到 deepseek
/cnb-model deepseek -s project
/cnb-model current         查看当前
/cnb-model list            列出可用
```

## Profile 结构

`~/.cnb/model-profiles.json`：

```json
{
  "deepseek": {
    "name": "Deepseek 官方",
    "aliases": ["d", "ds"],
    "env": {
      "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
      "ANTHROPIC_AUTH_TOKEN": "$DEEPSEEK_API_KEY",
      "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]"
    },
    "permissions": {
      "allow": ["*"],
      "deny": []
    }
  }
}
```

- `aliases` — 短名，`cnb m d` 等同于 `cnb m deepseek`
- `env` — 写入 `settings.json`，值以 `$` 开头从环境变量读取
- `env: {}` — 清空所有 provider 变量，恢复 Anthropic 原生
- `permissions` — 可选，合并写入 `settings.json`（deepseek 需要 bypass）

## Scope

| scope | 写入位置 |
|-------|----------|
| `global` | `~/.claude/settings.json` |
| `project` | `<cwd>/.claude/settings.json` |

默认 scope 由 `~/.cnb/config.toml` 中 `model_scope` 控制（未设置默认 `global`）。

## 环境变量

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_BASE_URL` | Provider API 地址 |
| `ANTHROPIC_AUTH_TOKEN` | 认证 token |
| `ANTHROPIC_API_KEY` | API key |
| `ANTHROPIC_MODEL` | 默认模型 |
| `ANTHROPIC_SMALL_FAST_MODEL` | 小模型 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus 模型 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet 模型 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku 模型 |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 禁用非必要网络请求 |
| `CLAUDE_CODE_EFFORT_LEVEL` | effort level |
