---
allowed-tools: Edit(.*settings.json)
argument-hint: "<key> <value>"
description: settings.json edit primitives — key-value patching
---

!`python3 -c "
import json, sys
path = '.claude/settings.json'
with open(path) as f:
    data = json.load(f)
args = '$ARGUMENTS'.split()
if len(args) >= 2:
    key, val = args[0], ' '.join(args[1:])
    if val in ('true','false'): val = val == 'true'
    data[key] = val
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    print(f'OK set {key} = {val}')
else:
    key = args[0] if args else None
    if key:
        print(json.dumps(data.get(key), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))
"`

Reply with only the command output above.
