# Project Discovery Tool

`cnb projects scan` audits this Mac for real cnb projects by looking for board databases under bounded roots. It is the machine-level view used by the terminal supervisor tongxue before reporting project status.

Implementation:

- CLI entrypoint: [`../../bin/cnb`](../../bin/cnb)
- Discovery logic: [`../../lib/global_registry.py`](../../lib/global_registry.py)
- Tests: [`../../tests/test_global_registry.py`](../../tests/test_global_registry.py)

## When To Use

Use this tool when you need to answer which cnb projects exist on the current computer, whether the global registry is stale, or which boards have active tasks and unread messages.

Do not use it as a blind cleanup command. `--register` only adds or refreshes discovered real projects in `~/.cnb/projects.json`; it does not remove stale entries. Run registry cleanup separately only after reviewing the result.

## Commands

```bash
cnb projects scan
cnb projects scan --max-depth 5
cnb projects scan --root "$HOME/Desktop/Toolbase_Skills" --root "$HOME/Desktop"
cnb projects scan --json
cnb projects scan --max-depth 5 --register
```

Options:

- `--root PATH` can be repeated. If omitted, the tool scans `$HOME/Desktop/Toolbase_Skills` and `$HOME/Desktop`.
- `CNB_SCAN_ROOTS` can override default roots. Use `:`-separated paths on macOS and Linux.
- `--max-depth N` limits traversal depth from each root. The default is `5`.
- `--no-legacy` ignores legacy `.claudes/board.db` projects.
- `--register` writes discovered projects into the global registry.
- `--json` emits machine-readable output.

## Scan Model

The scanner looks for:

- `.cnb/board.db` for current cnb projects.
- `.claudes/board.db` for legacy projects, unless `--no-legacy` is set.

It is intentionally bounded. The default roots cover the current known project layout without walking the whole home directory. Heavy directories such as `.git`, `.venv`, `node_modules`, build outputs, media folders, and caches are pruned.

When roots overlap, narrower roots are scanned first. Later broader roots skip those already-covered subtrees, so scanning both `$HOME/Desktop/Toolbase_Skills` and `$HOME/Desktop` does not traverse Toolbase projects twice.

## Output

Each discovered project includes:

- Project path and config directory (`.cnb` or `.claudes`).
- Configured and currently running tmux sessions for the project prefix.
- Board counts for sessions, tasks, unread inbox items, and latest message.
- Git branch, latest commit summary, and dirty file count when the project is inside a Git repo.

Use the text output for operator status reports and `--json` for scripts.
