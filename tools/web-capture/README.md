# Web Capture

Web capture bridges a user-opened browser page into cnb without reopening the URL, printing the page, or driving the browser UI.

The stable cnb side is:

```bash
cnb capture ingest --project /path/to/project --mode selection --source safari-web-extension < payload.json
cnb capture ingest --global --mode page --source safari-web-extension < payload.json
cnb capture list --project /path/to/project
cnb capture list --global
cnb capture show --project /path/to/project <capture-id>
```

The browser side should be a separate sidecar. The current sidecar scaffold lives at:

```text
/Users/zhangkezhen/Desktop/Toolbase_Skills/cnb-web-capture
```

## Responsibilities

cnb:

- validates capture mode
- writes `.cnb/captures/<id>/`
- redacts obvious token/password fields
- notifies the board recipient
- falls back to `~/.cnb/captures` for browser-launched global captures

sidecar:

- asks for browser permissions
- runs only from a user gesture
- extracts current-tab selection/article/page/snapshot data
- calls `cnb capture ingest`

See [`../../docs/capture-protocol.md`](../../docs/capture-protocol.md) for the protocol.

Default web capture must not ask for macOS Accessibility or Screen Recording permissions. Those belong only to an explicit visual fallback mode, not the normal Safari/WebExtension path.
