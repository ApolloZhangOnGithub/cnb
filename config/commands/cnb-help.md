---
allowed-tools: Bash(python3 *)
description: 列出所有 cnb/cnbx 命令（自动扫描）
---

Run this:

```bash
python3 -c "
import os, glob
for prefix, label in [('cnb-', '用户命令'), ('cnbx-', '程序接口')]:
    print(f'## {label} ({prefix}*)')
    for f in sorted(glob.glob(f'.claude/commands/{prefix}*.md')):
        name = os.path.basename(f)[:-3]
        desc = ''
        in_fm = False
        for line in open(f):
            line = line.strip()
            if line == '---':
                in_fm = not in_fm and True or not in_fm
            elif in_fm and line.startswith('description:'):
                desc = line.split(':', 1)[1].strip()
        if not desc:
            desc = '(no description)'
        print(f'  /{name} — {desc}')
    print()
"
```

Reply with only the command output above.
