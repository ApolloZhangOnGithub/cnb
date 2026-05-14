---
allowed-tools: Bash(python3 *)
description: 技能发现 — 列出 cnb 生态所有可用技能，按分类展示
---

用户想了解 cnb 生态有哪些技能可用。从 `registry/skills.yaml` 读取技能目录，按分类展示：

```bash
python3 -c "
import yaml
with open('registry/skills.yaml') as f:
    data = yaml.safe_load(f)

cats = {}
for s in data['skills']:
    cats.setdefault(s['category'], []).append(s)

labels = {
    'cnb': 'CNB 核心',
    'lark': '飞书 (Lark)',
    'media': '媒体工具',
    'dev': '开发工具',
    'infra': '基础设施',
    'builtin': 'Claude Code 内置',
}

for cat, slist in cats.items():
    print(f'## {labels.get(cat, cat)}')
    for s in slist:
        if s.get('builtin'):
            tag = '内置'
        elif s.get('install'):
            tag = '需安装'
        else:
            tag = '源码'
        cmds = ', '.join(s.get('cmds', ['-']))
        print(f'  [{tag}] {s[\"display\"]} — {s[\"desc\"]}')
        print(f'         调用: {cmds}')
    print()
print('安装飞书技能: npm install -g @lark-ai/lark-cli')
"
```

如果用户想了解更多关于某个技能，引导他们查看对应 repo 的文档。

Reply with only the command output above. Do not explain it unless the user asks.
