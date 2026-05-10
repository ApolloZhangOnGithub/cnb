# Codex Engine Notes

cnb can run Claude by default or Codex as the second engine option.

## Launch Forms

```bash
cnb codex
cnb --agent codex
CNB_AGENT=codex cnb
SWARM_AGENT=codex cnb swarm start
```

## Permission Mode

Use this Codex flag by itself:

```bash
--dangerously-bypass-approvals-and-sandbox
```

This is Codex's top local permission mode. It skips approval prompts and runs without sandboxing.

Do not combine it with either of these flags:

```bash
--ask-for-approval never
--sandbox danger-full-access
```

Codex CLI 0.130.0 rejects that combination with:

```text
error: the argument '--dangerously-bypass-approvals-and-sandbox' cannot be used with '--ask-for-approval <APPROVAL_POLICY>'
```

## Smoke Test

When changing Codex launch code, do not stop at command construction tests. Start a real temporary tmux session and confirm the pane stays in Codex instead of returning to the shell.

Codex may show a workspace trust prompt:

```text
Do you trust the contents of this directory?
Press enter to continue
```

The tmux backend auto-confirms this prompt. If a smoke test stalls there, update `TmuxBackend.auto_accept_trust()` before treating the engine launch as done.

Minimum check:

```bash
CNB_AGENT=codex SWARM_AGENT=codex ./bin/swarm start <session>
tmux list-panes -t <prefix>-<session> -F '#{pane_current_command}'
tmux capture-pane -t <prefix>-<session> -p -S -80
```

Clean up the temporary session after the check:

```bash
tmux kill-session -t <prefix>-<session>
```
