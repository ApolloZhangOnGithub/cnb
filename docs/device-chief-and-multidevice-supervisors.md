# Device Chief And Multi-Device Supervisors

This note defines how cnb should run when one user has multiple Macs, multiple
Feishu bots, and one or more project teams. The goal is reliable supervision,
not a bigger hierarchy.

## Roles

| Role | Scope | Responsibility |
|------|-------|----------------|
| Device supervisor | One physical machine | Owns local tmux sessions, local project registry, local runtime health, Feishu ingress, logs, and shutdown notes for that machine. |
| Device chief | Cross-device coordination role | Maintains the device roster, active/standby state, leases, handoffs, and escalation. This is a transferable role, not a third project worker. |
| First officer / watchdog | Safety loop | Detects stale requests, stuck activity cards, dirty worktrees, missed checkpoints, bridge failures, and lease conflicts. It alerts; it does not silently take over. |
| Project tongxue | One project board slot | Owns project work through the board, inbox, tests, issues, and PRs. It should not manage device-level state. |
| Infrastructure process | Local service | Feishu bridge, tunnel, watch server, sync gateway, dispatcher, and backup jobs. These are not tongxue. |

A device supervisor may temporarily act as device chief. The chief role should
be explicit in status output and handoff notes so another machine can take it
over when the current chief sleeps, disconnects, or is shut down.

## Current Manual Mode

Before cnb has first-class device coordination, use this conservative operating
mode:

1. Create one Feishu bot per device supervisor.
2. Put the user and all device supervisor bots in one Feishu control group.
3. Treat the group as a human-visible control room, not the default internal
   message bus for every tongxue.
4. A newly started device supervisor posts a `HELLO` report.
5. The acting device chief replies with current leases, risks, and next steps.
6. Only one device acts as active writer for a given project at a time.

This keeps both supervisors observable without letting two machines
accidentally edit the same project board or dirty worktree.

## Current Implementation Boundary

Do not treat device chief as an already-running daemon. Today the concrete
mechanisms are:

- one or more local device supervisors, each with its own Feishu bot and bridge;
- Feishu bridge allowlists via `chat_id`, `allowed_chat_ids`, or `chat_ids`;
- group-message routing based on mentions, replies, known bot IDs, and local
  message ownership;
- the AVP `CNBVision` viewer, which is read-only and aggregates recent messages
  from the configured Feishu control chats.

The device chief is the coordination role that should eventually own roster,
lease, handoff, and conflict decisions. Until that is implemented as a registry
plus lease protocol, use one shared Feishu control group as the practical
control room. If several terminal supervisors are in that group, AVP can see
their visible Feishu messages through the same group history. If different
supervisors use different allowed groups, AVP can read all groups exported in
`chatIDs`, but it still does not decide which device should act.

## Handshake

Each supervisor should be able to produce a compact handshake:

```text
HELLO device=<device_id> role=device-supervisor
host=<hostname>
bot=<feishu_bot_name>
cnb=<version_or_commit>
cwd=<current_supervisor_cwd>
projects=<registered_project_names>
bridge=<ok|degraded|down>
watch=<ok|disabled|down>
sync_gateway=<ok|unknown|down>
active_leases=<project:none|project:owner@device_until_time>
local_risks=<icloud_runtime|dirty_worktree|missing_secret|none>
```

The Feishu group may receive the human-readable version. The machine-readable
version should go into local device state and, later, the sync gateway event
log. Do not spam the group with routine heartbeats; only post on startup,
handoff, degradation, conflict, or user-visible completion.

## Lease Model

Leases prevent split brain. A lease is the right to write to one shared target:

- project board database;
- project worktree;
- package/release target;
- Feishu group routing config;
- cloud sync gateway administration.

Minimum lease fields:

```json
{
  "resource": "project:claudes-code",
  "holder_device": "macbook-001",
  "holder_role": "device-supervisor",
  "reason": "active local development",
  "created_at": "2026-05-10T16:20:00+08:00",
  "expires_at": "2026-05-10T16:50:00+08:00",
  "renewal_policy": "while-supervisor-active",
  "handoff_to": null
}
```

Rules:

- A device must check the current lease before writing shared project state.
- Expired leases may be treated as stale, but takeover should still announce in
  the control group unless the previous holder is clearly dead.
- A sleeping Mac should release or shorten leases during shutdown.
- The device chief coordinates lease conflicts; it does not perform the project
  work itself.

## State Boundaries

Use separate truth sources for separate problems:

| State | Source of truth |
|-------|-----------------|
| Code and review history | Git remotes and PRs |
| Active project work | One local worktree plus one active project board writer |
| Device runtime | `~/.cnb/device-supervisor/` on that machine |
| Cross-device facts | cnb sync gateway or explicit export/import bundle |
| File backup and transport | iCloud, Time Machine, Drive, or other backup tools |
| Secrets | Machine-local keychain/config; never synced by default |

iCloud is valuable for file safety, but it is not a runtime consistency layer.
Do not run two active cnb writers against the same synced `.cnb/board.db`.

## Feishu Group Use

Feishu is a good human control room because it gives the user visibility on iOS
and Mac. It should not become the only machine protocol.

Use Feishu for:

- startup `HELLO`;
- explicit user commands;
- device chief summaries;
- handoff confirmation;
- warnings that need a human;
- final results.

Avoid Feishu for:

- high-frequency heartbeats;
- raw terminal replay;
- full local state replication;
- hidden machine-to-machine authority transfer;
- automatic permission expansion.

Feishu message copies should remain privacy-conscious. Store a local event
ledger with message IDs, chat IDs, routing, delivery state, and resource
metadata. Do not persist full chat history by default.

## Device Chief Feishu Bot

The device chief uses its own Feishu bot and its own bridge config. Do not wire
the chief through the local device supervisor keys.

```bash
cnb feishu-chief status
cnb feishu-chief setup --role device_chief --app-id cli_xxx --app-secret ... \
  --verification-token ... --chat-id oc_xxx --webhook-public-url https://...
cnb feishu-chief start
```

The shortcut above is equivalent to:

```bash
cnb feishu --config ~/.cnb/device-chief/config.toml ...
```

The config should use `role = "device_chief"`, `device_chief_name`, and
`device_chief_tmux`. Keep its `bridge_tmux`, webhook port, watch port, app
credentials, and Feishu callback URL separate from the device supervisor bot.
The default local chief workspace is `~/.cnb/device-chief/`.

## Reply And Mention Routing

Group routing should use Feishu's visible conversation structure instead of
guessing from plain text alone.

Routing precedence:

1. Explicit router command or explicit `@` target.
2. Reply/thread under a known device supervisor, router, or project-tongxue
   message.
3. Existing active thread owner from the local event ledger.
4. Active project/device lease.
5. Fallback to the group router or device chief.

To support this, the local event ledger should keep a minimal mapping:

```json
{
  "message_id": "om_xxx",
  "chat_id": "oc_xxx",
  "thread_id": "omt_or_om_xxx",
  "sender_bot": "CNB_终端主管",
  "device_id": "macbook-001",
  "routed_to": "device-supervisor@macbook-001",
  "routed_by": "group-router",
  "source_message_id": "om_parent"
}
```

If a user replies to a MacBook supervisor message, the reply should route back
to the MacBook supervisor even if another device supervisor is also in the
group. If a user replies to an iMac supervisor message, the MacBook bridge should
ignore it or treat it as a passive event. If the reply target is a plain user
message or the original route is unknown, require an explicit `@` or let the
group router decide.

This also prevents a common failure mode: every device in the group receiving
the same reply and answering as if it owned the thread.

## Cloud Group Router

The group router does not need to run on any user Mac. It is a better fit for a
small cloud service:

- It only needs Feishu event subscription, route-table storage, message send
  permissions, and access to the sync-gateway event log.
- It should not hold device-local secrets, shell access, tmux access, or project
  worktree access.
- It can stay online while a MacBook sleeps or an iMac restarts.
- It can route to whichever device supervisor currently holds a lease.
- It can remain tenant/app scoped and easier to audit than a local supervisor
  that also has filesystem and terminal authority.

Local device supervisors remain local because they manage machine-specific
state: tmux sessions, local files, terminals, Keychain/config, project roots,
watch links, and shutdown. The cloud router should never bypass a device
supervisor to operate a local machine.

Cloud router MVP:

1. Subscribe to Feishu group message events for allowlisted control groups.
2. Parse explicit mentions, replies, thread ownership, and route commands.
3. Resolve the target from a route table and active leases.
4. Forward by group mention at first; later deliver a structured event through
   the sync gateway.
5. Record `source_message_id`, `route_id`, `routed_by`, and target so loops and
   duplicate replies are prevented.

If the cloud router is unavailable, users can still directly mention a device
supervisor bot in the group. That fallback is essential.

## First Officer / Watchdog

The watchdog is useful, but it should be small:

- monitor bridge/tunnel/watch/sync gateway health;
- detect stale live activity and old open requests;
- detect dirty worktree and missed checkpoint risk;
- detect long-running foreground Codex/Claude sessions;
- check that shutdown notes are in global device-supervisor state, not project
  tongxue dailies;
- alert on lease conflict or duplicate active writers.

It must not:

- make product decisions;
- edit code;
- rewrite memory without review;
- silently take over another device;
- message the user continuously.

## Implementation Phases

### Phase 0: Manual Dogfood

- Use one Feishu group with all device supervisors.
- Use explicit `HELLO`, `HANDOFF`, and `LEASE` language.
- Keep device chief as an acting role on one supervisor.
- Record daily/handoff notes under `~/.cnb/device-supervisor/`.

### Phase 1: Device Registry And Doctor

- Add a local `cnb devices status` summary.
- Track device ID, host, bot name, Feishu chat, bridge health, watch health,
  sync gateway health, and current leases.
- Warn when active runtime state lives in iCloud/Dropbox/OneDrive/Google Drive.
- Verify required Feishu scopes and generate a copyable permission manifest.

### Phase 2: Sync Gateway Event Log

- Append device events to the sync gateway.
- Replicate minimal event metadata, not secrets or raw transcripts.
- Add lease claim, renew, release, and stale detection events.
- Expose read-only status for companion apps.

### Phase 3: First Officer

- Run watchdog checks on a quiet schedule.
- Send alerts only for actionable failures.
- Generate memory/checkpoint candidates for review.
- Support explicit device-chief handoff.

## Acceptance Criteria

- Status output distinguishes device supervisors, project tongxue, and
  infrastructure processes.
- Two devices can join the same Feishu group and complete a `HELLO` handshake.
- Only one device is active writer for a project lease.
- Shutdown writes machine-level notes to `~/.cnb/device-supervisor/`, not
  project `.cnb/dailies/<shift>/`.
- Feishu permissions can be diagnosed and summarized without self-expanding
  privileges.
- The watchdog can report stale activity, bridge health, dirty worktree, and
  lease conflict risk without taking over automatically.
