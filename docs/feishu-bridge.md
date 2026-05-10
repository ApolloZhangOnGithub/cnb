# Feishu Bridge

The Feishu bridge lets an allowlisted Feishu chat wake the Mac-level device
supervisor tongxue. It is an async command channel, not a terminal screen mirror.
Codex or Claude live terminal rendering stays on the Mac; Feishu receives final
results, explicit short questions, and intentionally requested snapshots or
watch links.

## Quick Path

```bash
cnb feishu setup
cnb feishu status
cnb feishu start
```

`setup` writes the local `[feishu]` config, generates missing local tokens,
starts the local webhook when possible, and prepares a tunnel URL if `ngrok` is
already installed and authenticated. Run `status` before `start` so missing app
credentials, chat IDs, webhook URLs, or watch settings are visible before the
bridge receives real messages.

## Runtime Model

The production path is `local_openapi`:

1. Feishu calls this Mac's CNB webhook.
2. CNB validates the verification token, chat, and sender constraints.
3. CNB routes the message into the device supervisor tmux session.
4. CNB replies through Feishu OpenAPI using the configured app credentials.

Hermes / `hermes_lark_cli` is only a development test adapter. Do not put it in
the production path.

The routed prompt includes the Feishu `message_id`. The supervisor should use:

- `cnb feishu reply <message_id> "message"` for final results, blockers, and
  substantive updates.
- `cnb feishu ask <message_id> "short question"` only for concise clarification,
  choices, or authorization requests.
- `cnb feishu watch` when the user wants a live read-only view.
- `cnb feishu tui` when the user explicitly asks for a current snapshot.

`ask` is intentionally short and rejects long summaries or fenced code blocks so
progress reporting does not become chat spam.

## Config Shape

`cnb feishu setup` writes this section to `~/.cnb/config.toml`. Keep secrets
user-owned and per environment.

```toml
[feishu]
transport = "local_openapi"
app_id = "cli_xxxxx"
app_secret = "..."
verification_token = "..."
webhook_host = "127.0.0.1"
webhook_port = 8787
webhook_public_url = "https://your-tunnel.example/cnb/feishu"
chat_id = "oc_xxxxx"
device_supervisor_name = "device-supervisor"
device_supervisor_tmux = "cnb-device-supervisor"
agent = "codex"
ack = true
notification_policy = "final_only"
activity_updates = true
activity_update_seconds = [1]
activity_update_repeat_seconds = 1
tui_capture_lines = 120
watch_port = 8765
watch_public_url = "https://your-tunnel.example/watch"
watch_token = "..."
watch_tool = "builtin"
watch_refresh_ms = 250
readback_enabled = false
resource_handoff_enabled = true
resource_handoff_max_bytes = 26214400
```

Legacy `terminal_supervisor_*` keys are still accepted as aliases, but new
configs should use `device_supervisor_*`.

## Notifications

`notification_policy = "final_only"` is the default mobile-friendly mode:
ordinary Feishu requests are routed to the device supervisor without an ack or
live activity push. iOS receives a notification only when the supervisor sends
the final `cnb feishu reply`.

Other modes are deliberately narrower:

| Policy | Behavior |
|--------|----------|
| `final_only` | No automatic ack or live card; final reply only. |
| `ack` | One received confirmation, then final reply. |
| `live` | Ack plus a single activity card loop for temporary debugging. |

Live mode updates one Feishu activity card with readable terminal tail text.
The full high-frequency screen belongs in the `/watch` Web TUI.

Replies that contain Markdown structure, including lists, emphasis, links,
inline code, or fenced code blocks, are sent as Feishu rich text so final
summaries and code snippets render normally in the client.

## Resource Handoff And Readback

Current-message resource handoff is separate from chat-history readback.

With `resource_handoff_enabled = true`, images, files, audio/video resources,
and rich-text embedded images/files in the current inbound Feishu message are
downloaded through Feishu message-resource APIs into:

```text
~/.cnb/feishu_resources/<message_id>/
```

The supervisor prompt receives the absolute paths. Feishu document links and
ordinary URLs are passed through as links. The bridge does not OCR, parse, or
summarize those resources.

Readback is diagnostic mode, not normal context loading. Keep
`readback_enabled = false` by default. Turn it on only when the user asks why a
Feishu message, history item, thread, or read status looks wrong. With the
required Feishu message-read permissions, the supervisor can run:

```bash
cnb feishu history --limit 12
cnb feishu inspect-message <message_id>
```

CNB does not persist chat history beyond requested resource files.

## Web TUI

`cnb feishu watch` starts the built-in read-only Web TUI and returns a tokenized
URL. The same public tunnel origin can be reused for the Feishu webhook and the
watch route; `watch_token` guards the viewer. Ordinary `cnb feishu status`
redacts the token.

The Web TUI refreshes every `watch_refresh_ms` milliseconds, updates the DOM only
when screen text changes, and keeps the viewport pinned to the bottom unless the
user has scrolled away.

## Deployment Checklist

- In the Feishu developer console, set the event subscription request URL to
  `webhook_public_url`.
- Use the same `verification_token` from `~/.cnb/config.toml` for Feishu URL
  verification.
- Subscribe the bot to `im.message.receive_v1`.
- Grant the IM permissions needed to receive messages, read referenced messages,
  and reply/send messages as the bot.
- Install the bot into the target chat and set `chat_id`, or enable first-chat
  binding deliberately.
- Keep `watch_token` private. Share the full watch URL only through an
  intentional `cnb feishu watch` reply.

`ngrok` is user-owned infrastructure. CNB can start `ngrok http ...` only after
the local machine has installed and authenticated ngrok, for example:

```bash
ngrok config add-authtoken <your-token>
```

CNB does not ship, share, or mint ngrok credentials. Every user or deployment
must authorize its own ngrok account.

## Feishu-Side Shortcuts

Feishu-side commands are optional precise shortcuts:

| Command | Result |
|---------|--------|
| `/cnb_tui` or `/c_tui` | Reply with the current device supervisor TUI snapshot. |
| `/cnb_watch` or `/c_watch` | Start the built-in read-only Web TUI viewer and reply with the link. |
| `/cnb_status` or `/c_status` | Reply with the device, tmux, team, and foreground-session status summary. |

Ordinary natural-language requests do not need these commands. They are routed
to the supervisor with a small capability guide, and the supervisor should infer
the goal before calling local capabilities.

## Related Surfaces

- [Mac companion and Island](terminal-supervisor-island.md) explains the Mac
  companion and optional iPhone Live Activity bridge.
- `tools/cnb-mac-companion/` embeds the same built-in Web TUI locally through
  WebKit.
- `tools/cnb-island/` can export Feishu chat config for simulator and physical
  iPhone checks without committing secrets.
