"""Web capture ingest protocol for cnb.

The browser-specific collector is intentionally out of process. This module only
accepts an already user-authorized capture payload, writes local artifacts, and
optionally notifies the board.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from lib.board_db import BoardDB
from lib.common import find_claudes_dir

VALID_CAPTURE_MODES = frozenset({"selection", "article", "page", "snapshot", "visual-only", "redacted"})
PROJECT_MARKERS = (".cnb", ".claudes")


class CaptureError(RuntimeError):
    """Raised when a capture payload or project target is invalid."""


@dataclass(frozen=True)
class CaptureStore:
    project_root: Path
    config_dir: Path
    captures_dir: Path
    scope: str


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str, *, fallback: str = "capture") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._").lower()
    return (slug or fallback)[:64]


def _redact_text(text: str) -> str:
    text = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}", r"\1[REDACTED]", text)
    return text


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if re.search(r"(?i)(password|secret|token|api[_-]?key|cookie)", str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = _redact_json(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _sanitize_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|iframe)\b.*?</\1>", "", html)
    html = re.sub(r'(?is)\svalue=(["\']).*?\1', ' value="[REDACTED]"', html)
    html = re.sub(r"(?is)<input\b([^>]*type=(['\"]?)password\2[^>]*)>", r"<input\1 value=\"[REDACTED]\">", html)
    return _redact_text(html)


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _global_store() -> CaptureStore:
    cnb_home = Path.home() / ".cnb"
    return CaptureStore(Path.home(), cnb_home, cnb_home / "captures", "global")


def _resolve_store(project: str | Path | None = None, *, global_store: bool = False) -> CaptureStore:
    if global_store:
        return _global_store()
    if project is None:
        try:
            default_config_dir = find_claudes_dir().resolve()
        except FileNotFoundError:
            return _global_store()
        return CaptureStore(default_config_dir.parent, default_config_dir, default_config_dir / "captures", "project")

    root = Path(project).expanduser().resolve()
    config_dir: Path | None = None
    if root.name in PROJECT_MARKERS:
        config_dir = root
        project_root = root.parent
    else:
        config_dir = next((root / marker for marker in PROJECT_MARKERS if (root / marker).is_dir()), None)
        project_root = root
    if config_dir is None:
        raise CaptureError(f"找不到项目配置目录: {root}/.cnb 或 {root}/.claudes")
    return CaptureStore(project_root, config_dir, config_dir / "captures", "project")


def _capture_id(payload: dict[str, Any], received_at: str) -> str:
    title = _first_string(payload, ("title", "name"))
    url = _first_string(payload, ("url", "canonical_url"))
    host = urlparse(url).netloc if url else ""
    label = title or host or str(payload.get("source") or "capture")
    digest = hashlib.sha256(
        json.dumps(_redact_json(payload), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:10]
    compact_time = received_at.replace("-", "").replace(":", "").replace("+00:00", "Z")
    return f"{compact_time}-{_slugify(label)}-{digest}"


def _new_capture_dir(captures_dir: Path, capture_id: str) -> Path:
    candidate = captures_dir / capture_id
    if not candidate.exists():
        candidate.mkdir(mode=0o700)
        return candidate
    for index in range(2, 100):
        candidate = captures_dir / f"{capture_id}-{index}"
        if not candidate.exists():
            candidate.mkdir(mode=0o700)
            return candidate
    raise CaptureError(f"capture id 冲突过多: {capture_id}")


def _content_markdown(payload: dict[str, Any], manifest: dict[str, Any]) -> str:
    title = str(manifest["title"] or "Untitled Capture")
    lines = [
        f"# {title}",
        "",
        f"- URL: {manifest['url'] or '(none)'}",
        f"- Source: {manifest['source']}",
        f"- Mode: {manifest['mode']}",
        f"- Captured at: {manifest['captured_at'] or '(unknown)'}",
        f"- Received at: {manifest['received_at']}",
        "",
    ]

    sections = (
        ("Selection", ("selection_text", "selection")),
        ("Article", ("article_text", "article")),
        ("Page Text", ("page_text", "visible_text", "text")),
        ("Notes", ("notes", "summary")),
    )
    wrote_section = False
    for heading, keys in sections:
        text = _first_string(payload, keys)
        if not text:
            continue
        wrote_section = True
        lines.extend([f"## {heading}", "", _redact_text(text).strip(), ""])

    links = payload.get("links")
    if isinstance(links, list) and links:
        wrote_section = True
        lines.extend(["## Links", ""])
        for item in links[:100]:
            if isinstance(item, dict):
                label = _redact_text(str(item.get("text") or item.get("label") or item.get("href") or "link"))
                href = _redact_text(str(item.get("href") or ""))
                lines.append(f"- [{label}]({href})" if href else f"- {label}")
            elif isinstance(item, str):
                lines.append(f"- {_redact_text(item)}")
        lines.append("")

    if not wrote_section:
        lines.extend(["## Capture", "", "(No text content was included in this capture payload.)", ""])
    return "\n".join(lines).rstrip() + "\n"


def _write_screenshot(capture_dir: Path, payload: dict[str, Any]) -> str:
    encoded = _first_string(payload, ("screenshot_base64", "visible_png_base64", "image_base64"))
    if not encoded:
        return ""
    if "," in encoded and encoded.split(",", 1)[0].startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise CaptureError("截图不是有效的 base64") from exc
    path = capture_dir / "visible.png"
    path.write_bytes(data)
    return path.name


def ingest_capture(
    payload: dict[str, Any],
    *,
    project: str | Path | None = None,
    global_store: bool = False,
    source: str | None = None,
    mode: str | None = None,
    notify: str | None = None,
    sender: str = "dispatcher",
) -> dict[str, Any]:
    """Write a capture payload into .cnb/captures and optionally notify the board."""
    if not isinstance(payload, dict):
        raise CaptureError("capture payload must be a JSON object")
    capture_mode = mode or str(payload.get("mode") or "page")
    if capture_mode not in VALID_CAPTURE_MODES:
        raise CaptureError(f"无效 capture mode: {capture_mode}")

    store = _resolve_store(project, global_store=global_store)
    store.captures_dir.mkdir(parents=True, exist_ok=True)
    received_at = _now_iso()
    payload = _redact_json({**payload, "mode": capture_mode, "source": source or payload.get("source") or "unknown"})
    capture_id = _capture_id(payload, received_at)
    capture_dir = _new_capture_dir(store.captures_dir, capture_id)
    capture_id = capture_dir.name

    html_file = ""
    html = _first_string(payload, ("sanitized_html", "html", "page_html"))
    if html:
        html_file = "page.sanitized.html"
        (capture_dir / html_file).write_text(_sanitize_html(html), encoding="utf-8")

    image_file = _write_screenshot(capture_dir, payload)
    title = _first_string(payload, ("title", "name"))
    url = _first_string(payload, ("url", "canonical_url"))
    manifest = {
        "id": capture_id,
        "source": str(payload["source"]),
        "mode": capture_mode,
        "title": title,
        "url": url,
        "captured_at": _first_string(payload, ("captured_at", "created_at")),
        "received_at": received_at,
        "scope": store.scope,
        "project_root": str(store.project_root),
        "files": {
            "manifest": "manifest.json",
            "payload": "payload.redacted.json",
            "content": "content.md",
            "html": html_file,
            "image": image_file,
        },
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }
    (capture_dir / "content.md").write_text(_content_markdown(payload, manifest), encoding="utf-8")
    (capture_dir / "payload.redacted.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    (capture_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if notify:
        _notify_board(store, manifest, capture_dir, recipient=notify, sender=sender)
    return {"manifest": manifest, "path": str(capture_dir)}


def _notify_board(
    store: CaptureStore, manifest: dict[str, Any], capture_dir: Path, *, recipient: str, sender: str
) -> None:
    board_db = store.config_dir / "board.db"
    if not board_db.exists():
        return
    db = BoardDB(board_db)
    title = manifest["title"] or manifest["url"] or manifest["id"]
    body = (
        f"[capture] 用户分享了当前网页: {title}\n"
        f"mode={manifest['mode']} source={manifest['source']}\n"
        f"url={manifest['url'] or '(none)'}\n"
        f"artifact={capture_dir}"
    )
    db.post_message(sender, recipient, body, deliver=True)


def list_captures(*, project: str | Path | None = None, global_store: bool = False) -> list[dict[str, Any]]:
    store = _resolve_store(project, global_store=global_store)
    if not store.captures_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for manifest_path in store.captures_dir.glob("*/manifest.json"):
        try:
            data = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        data["_path"] = str(manifest_path.parent)
        rows.append(data)
    rows.sort(key=lambda item: (str(item.get("received_at") or ""), str(item.get("id") or "")), reverse=True)
    return rows


def _find_capture(
    capture_id: str, *, project: str | Path | None = None, global_store: bool = False
) -> tuple[dict[str, Any], Path]:
    for item in list_captures(project=project, global_store=global_store):
        if item.get("id") == capture_id or str(item.get("id", "")).startswith(capture_id):
            return item, Path(item["_path"])
    raise CaptureError(f"找不到 capture: {capture_id}")


def _read_payload(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CaptureError(f"capture payload 不是有效 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CaptureError("capture payload must be a JSON object")
    return data


def cmd_capture(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cnb capture")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="ingest a user-authorized web capture JSON payload")
    ingest.add_argument("--project", help="target cnb project root or .cnb/.claudes directory")
    ingest.add_argument("--global", dest="global_store", action="store_true", help="write to ~/.cnb/captures")
    ingest.add_argument("--file", default="-", help="JSON payload file, or '-' for stdin")
    ingest.add_argument("--source", help="override capture source")
    ingest.add_argument("--mode", choices=sorted(VALID_CAPTURE_MODES), help="override capture mode")
    ingest.add_argument("--notify", default="lead", help="board recipient to notify; default: lead")
    ingest.add_argument("--no-notify", action="store_true", help="write artifacts without sending a board message")
    ingest.add_argument("--sender", default="dispatcher", help="board sender identity")

    list_cmd = sub.add_parser("list", help="list local captures")
    list_cmd.add_argument("--project", help="target cnb project root or .cnb/.claudes directory")
    list_cmd.add_argument("--global", dest="global_store", action="store_true", help="read from ~/.cnb/captures")
    list_cmd.add_argument("--json", action="store_true", help="print machine-readable JSON")

    show = sub.add_parser("show", help="show a capture")
    show.add_argument("capture_id")
    show.add_argument("--project", help="target cnb project root or .cnb/.claudes directory")
    show.add_argument("--global", dest="global_store", action="store_true", help="read from ~/.cnb/captures")
    show.add_argument("--json", action="store_true", help="print manifest JSON")
    show.add_argument("--path", action="store_true", help="print capture directory path")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "ingest":
            result = ingest_capture(
                _read_payload(args.file),
                project=args.project,
                global_store=args.global_store,
                source=args.source,
                mode=args.mode,
                notify=None if args.no_notify else args.notify,
                sender=args.sender,
            )
            print(f"OK capture 已保存: {result['path']}")
            print(f"   id: {result['manifest']['id']}")
            return
        if args.cmd == "list":
            captures = list_captures(project=args.project, global_store=args.global_store)
            if args.json:
                print(json.dumps({"captures": captures}, indent=2, ensure_ascii=False))
                return
            if not captures:
                print("没有 capture")
                return
            for item in captures:
                print(
                    f"  {item['id']}  {item.get('mode', ''):11s} {item.get('title') or item.get('url') or '(untitled)'}"
                )
            return
        if args.cmd == "show":
            item, path = _find_capture(args.capture_id, project=args.project, global_store=args.global_store)
            if args.json:
                print(json.dumps(item, indent=2, ensure_ascii=False))
                return
            if args.path:
                print(path)
                return
            print((path / "content.md").read_text())
    except CaptureError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    cmd_capture(sys.argv[1:])
