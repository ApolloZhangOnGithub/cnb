# Codex Engine Notes

cnb can run Claude by default or Codex as the second engine option.

## Operational Workflow

cnb enables Codex goals best-effort before launching Codex sessions:

```bash
codex features enable goals
```

When a Codex tongxue starts a concrete task, set the turn objective first:

```text
/goal <one-sentence task objective>
```

Use the goal as the active contract for the current turn: keep it specific to the
assigned task, update it if the assignment changes, and keep board messages in
sync with the current goal by posting status when work starts, blocks, or
finishes.

Codex does not have Claude's Monitor tool. After assigning work, the device
supervisor should poll the board directly:

```bash
cnb board --as <name> inbox
```

Background Codex tongxue also start by checking their inbox. If there is no
explicit assignment, they should read the session file and roadmap before
choosing autonomous docs or maintenance work.

## Launch Forms

```bash
cnb codex
cnb --agent codex
CNB_AGENT=codex cnb
SWARM_AGENT=codex cnb swarm start
SWARM_AGENT=codex cnb swarm smoke <session>
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

Use standby mode when the goal is to prove the team can clock in without
resuming historical work:

```bash
SWARM_AGENT=codex ./bin/swarm smoke <session>
```

In smoke mode the startup prompt tells the tongxue to read its session/CV and
inbox, report readiness, and then wait. It explicitly forbids continuing the
session file, reading `ROADMAP.md` for autonomous work, editing files, running
tests, or commenting on issues/PRs.

## Board Delivery Nudges

Board delivery is not only passive database state. When `board send` delivers a
message to a running session, cnb tries to nudge that tmux pane:

- Idle recipients receive the direct inbox command, so the pane opens unread
  messages immediately.
- Busy recipients receive a safe-point prompt telling them to run their inbox
  command at the next safe point.
- `board task add --to <session> ...` posts the task notification and uses the
  same nudge path.

This matters for Codex because an active run may be busy editing, testing, or
reasoning when the board message arrives. Do not assume a sent message has been
handled until the recipient reports status, acks the inbox, or updates the task.
