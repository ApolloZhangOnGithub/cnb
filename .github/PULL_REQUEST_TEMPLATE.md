## Summary

-

## Linked Issue

Closes #

## Verification

- [ ] `ruff check lib/ bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/doctor bin/init bin/notify bin/registry bin/secret-scan bin/sync-version bin/check-changelog tests/`
- [ ] `ruff format --check lib/ bin/board bin/swarm bin/dispatcher bin/dispatcher-watchdog bin/doctor bin/init bin/notify bin/registry bin/secret-scan bin/sync-version bin/check-changelog tests/`
- [ ] `mypy lib/`
- [ ] `python -m pytest tests/ -v --tb=short`
- [ ] `python bin/sync-version --check`
- [ ] `python bin/check-changelog`
- [ ] `python bin/secret-scan --all`
- [ ] `bin/check-readme-sync` if README files changed

## Checklist

- [ ] There is an issue for this change, or this is a documented P0/P1 exception.
- [ ] `VERSION`, `package.json`, and `pyproject.toml` are in sync when the version changed.
- [ ] CHANGELOG.md is updated when user-visible behavior, security, packaging, or release state changed.
- [ ] Documentation and tool README files are updated for changed commands, flags, defaults, or operational assumptions.
- [ ] Security-sensitive changes are called out and do not expose secrets, exploit details, or private logs.
- [ ] Commit messages include the required `Co-Authored-By` trailer.
