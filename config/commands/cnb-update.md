---
allowed-tools: Bash(pip install --upgrade claude-nb), Bash(pip3 install --upgrade claude-nb)
description: 更新 — cnb 本体或全工具链
---

用户说"更新"/"升级"，判断意图：

- **仅 cnb**: 调用 `/cnbx-update`
- **全更新**: 用户说"全更新"/"update all"/"更新全部"，除了 `/cnbx-update` 外，还要检查并更新 pip、npm 等工具链中有更新的包
- **无明确范围**: 默认仅更新 cnb，但提示"要全工具链更新的话说 '全更新'"

更新成功提醒用户重启 cnb 以生效。
