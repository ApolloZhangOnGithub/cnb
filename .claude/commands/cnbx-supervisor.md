---
allowed-tools: Bash(cat ~/.cnb/live_state.json *), Bash(ps aux *), Bash(ls *), Bash(cat ~/.cnb/config.toml *)
description: supervisor diagnostics — live_state, processes, dailies
---

!`echo "=== live_state ===" && cat ~/.cnb/live_state.json 2>/dev/null && echo "=== processes ===" && ps aux | grep -i "CNBMacCompanion\|feishu.*bridge" | grep -v grep && echo "=== dailies ===" && ls -lt ~/.cnb/device-supervisor/dailies/ 2>/dev/null | head -5 && echo "=== config ===" && cat ~/.cnb/config.toml 2>/dev/null | head -30`

Reply with only the command output above.
