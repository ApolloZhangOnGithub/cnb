# Capture Protocol

cnb accepts user-authorized browser and app captures through a small JSON protocol. Browser-specific collectors live outside cnb; cnb only receives payloads, writes local artifacts, and optionally notifies the board.

## Boundary

cnb owns:

- `cnb capture ingest/list/show`
- `.cnb/captures/<capture-id>/`
- artifact redaction and indexing
- board notification after ingest

Sidecar tools own:

- Safari, Chrome, Arc, or app-specific permissions
- extension UI and user gestures
- native messaging or local transport
- browser signing and installation

This keeps cnb stable while allowing multiple capture frontends.

## Modes

The protocol is intentionally mode-based:

- `selection` - only user-selected text.
- `article` - extracted article/main content.
- `page` - visible page text and useful links.
- `snapshot` - text plus sanitized HTML and optional image.
- `visual-only` - image-first capture when DOM text is not meaningful.
- `redacted` - explicitly redacted payload from a collector.

Keep `page`/`selection` semantics strict. Add a new mode when a boundary case appears instead of changing an existing mode.

## Payload

Minimal payload:

```json
{
  "source": "safari-web-extension",
  "mode": "selection",
  "title": "Example",
  "url": "https://example.com",
  "selection_text": "selected text",
  "captured_at": "2026-05-10T06:30:00Z",
  "metadata": {
    "browser": "Safari"
  }
}
```

Optional fields:

- `article_text`
- `page_text` or `visible_text`
- `html` or `sanitized_html`
- `links`: array of `{ "text": "...", "href": "..." }`
- `screenshot_base64` or `visible_png_base64`
- `notes`

Collectors must not send cookies, localStorage, sessionStorage, or raw password fields by default.

## CLI

```bash
cnb capture ingest --project /path/to/project --mode selection --source safari-web-extension < payload.json
cnb capture ingest --global --mode page --source safari-web-extension < payload.json
cnb capture list --project /path/to/project
cnb capture list --global
cnb capture show --project /path/to/project <capture-id>
```

`ingest` notifies `lead` by default when the target project has a board. Use `--no-notify` for tests, archival imports, or privacy-sensitive local saves.

Use `--global` when the collector is launched by a browser and has no project context. Global captures are stored under `~/.cnb/captures` and are not delivered to a project board unless another tool explicitly routes them later.

## Artifacts

Each capture is written to:

```text
.cnb/captures/<capture-id>/
  manifest.json
  payload.redacted.json
  content.md
  page.sanitized.html   # optional
  visible.png           # optional
```

`content.md` is the agent-facing representation. `manifest.json` is the stable index. `payload.redacted.json` preserves collector detail after cnb-side redaction.

Global captures use the same artifact layout under `~/.cnb/captures/<capture-id>/`.
