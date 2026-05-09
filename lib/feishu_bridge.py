"""Feishu inbound bridge for waking the machine-level terminal supervisor tongxue."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import tomllib
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from lib.swarm import CODEX_PERMISSION_FLAGS
from lib.tmux_utils import has_session, tmux_send

DEFAULT_EVENT_KEY = "im.message.receive_v1"
DEFAULT_PILOT_NAME = "terminal-supervisor"
DEFAULT_PILOT_TMUX = "cnb-terminal-supervisor"
DEFAULT_BRIDGE_TMUX = "cnb-feishu-bridge"
DEFAULT_WATCH_TMUX = "cnb-feishu-watch"
DEFAULT_WATCH_HOST = "127.0.0.1"
DEFAULT_WATCH_PORT = 8765
DEFAULT_TRANSPORT = "hermes_lark_cli"
SUPPORTED_PILOT_AGENTS = frozenset({"codex"})
SUPPORTED_TRANSPORTS = frozenset({DEFAULT_TRANSPORT})
ACK_PREFIX = "已转给这台 Mac 的终端主管同学"
TUI_COMMANDS = frozenset({"/cnb_tui", "/c_tui"})
WATCH_COMMANDS = frozenset({"/cnb_watch", "/c_watch"})
HELP_COMMANDS = frozenset({"/cnb_help", "/c_help"})
SNAPSHOT_MAX_CHARS = 3500


@dataclass(frozen=True)
class FeishuInboundEvent:
    text: str
    message_id: str = ""
    chat_id: str = ""
    sender_id: str = ""
    chat_type: str = ""
    message_type: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BridgeResult:
    handled: bool
    detail: str


@dataclass(frozen=True)
class FeishuBridgeConfig:
    config_path: Path
    project_root: Path
    enabled: bool = True
    transport: str = DEFAULT_TRANSPORT
    event_key: str = DEFAULT_EVENT_KEY
    identity: str = "bot"
    allowed_chat_ids: frozenset[str] = frozenset()
    allowed_sender_ids: frozenset[str] = frozenset()
    ignored_sender_ids: frozenset[str] = frozenset()
    pilot_name: str = DEFAULT_PILOT_NAME
    pilot_tmux: str = DEFAULT_PILOT_TMUX
    bridge_tmux: str = DEFAULT_BRIDGE_TMUX
    agent: str = "codex"
    auto_start: bool = True
    startup_wait_seconds: float = 2.0
    ack: bool = True
    tui_capture_lines: int = 120
    watch_tmux: str = DEFAULT_WATCH_TMUX
    watch_host: str = DEFAULT_WATCH_HOST
    watch_port: int = DEFAULT_WATCH_PORT
    watch_public_url: str = ""
    watch_tool: str = "builtin"

    @classmethod
    def load(cls, config_path: Path | None = None, project_root: Path | None = None) -> FeishuBridgeConfig:
        path = config_path or Path.home() / ".cnb" / "config.toml"
        data = _read_toml(path)
        section = _feishu_section(data)

        root_raw = section.get("project") or section.get("project_root") or os.environ.get("CNB_PROJECT")
        root = Path(root_raw).expanduser() if isinstance(root_raw, str) and root_raw else (project_root or Path.cwd())
        root = root.resolve()

        agent = str(section.get("agent") or os.environ.get("CNB_AGENT") or "codex")
        if agent not in SUPPORTED_PILOT_AGENTS:
            agent = "codex"

        return cls(
            config_path=path,
            project_root=root,
            enabled=_bool(section.get("enabled"), True),
            transport=str(section.get("transport") or DEFAULT_TRANSPORT),
            event_key=str(section.get("event_key") or section.get("event-key") or DEFAULT_EVENT_KEY),
            identity=str(section.get("identity") or "bot"),
            allowed_chat_ids=frozenset(_strings(section, "allowed_chat_ids", "allowed-chat-ids", "chat_ids", "chat_id")),
            allowed_sender_ids=frozenset(
                _strings(section, "allowed_sender_ids", "allowed-sender-ids", "sender_ids", "sender_id")
            ),
            ignored_sender_ids=frozenset(_strings(section, "ignored_sender_ids", "ignored-sender-ids")),
            pilot_name=str(
                section.get("terminal_supervisor_name")
                or section.get("supervisor_name")
                or section.get("pilot_name")
                or section.get("on_duty_name")
                or section.get("session")
                or DEFAULT_PILOT_NAME
            ),
            pilot_tmux=str(
                section.get("terminal_supervisor_tmux")
                or section.get("supervisor_tmux")
                or section.get("pilot_tmux")
                or section.get("tmux_session")
                or DEFAULT_PILOT_TMUX
            ),
            bridge_tmux=str(section.get("bridge_tmux") or section.get("bridge_tmux_session") or DEFAULT_BRIDGE_TMUX),
            agent=agent,
            auto_start=_bool(section.get("auto_start"), True),
            startup_wait_seconds=_float(section.get("startup_wait_seconds"), 2.0),
            ack=_bool(section.get("ack"), True),
            tui_capture_lines=_int(section.get("tui_capture_lines"), 120),
            watch_tmux=str(section.get("watch_tmux") or section.get("watch_tmux_session") or DEFAULT_WATCH_TMUX),
            watch_host=str(section.get("watch_host") or DEFAULT_WATCH_HOST),
            watch_port=_int(section.get("watch_port"), DEFAULT_WATCH_PORT),
            watch_public_url=str(section.get("watch_public_url") or ""),
            watch_tool=str(section.get("watch_tool") or "builtin"),
        )


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _feishu_section(data: dict[str, Any]) -> dict[str, Any]:
    direct = data.get("feishu")
    if isinstance(direct, dict):
        return direct
    notification = data.get("notification")
    if isinstance(notification, dict):
        nested = notification.get("feishu")
        if isinstance(nested, dict):
            return nested
    return {}


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _strings(section: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = section.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, list):
            values.extend(str(item).strip() for item in value if str(item).strip())
    return values


def _id_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("open_id", "user_id", "union_id", "id"):
            item = value.get(key)
            if isinstance(item, str) and item:
                return item
    return ""


def _decode_content(content: Any) -> str:
    if isinstance(content, dict):
        for key in ("text", "content", "title"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(content, ensure_ascii=False)

    if not isinstance(content, str):
        return "" if content is None else str(content)

    text = content.strip()
    if not text:
        return ""
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(decoded, dict):
        return _decode_content(decoded)
    return text


def extract_event(payload: dict[str, Any]) -> FeishuInboundEvent:
    root = payload.get("event")
    if not isinstance(root, dict):
        root = payload
    message = root.get("message") if isinstance(root.get("message"), dict) else {}
    sender = root.get("sender") if isinstance(root.get("sender"), dict) else {}

    chat_id = str(root.get("chat_id") or message.get("chat_id") or payload.get("chat_id") or "")
    sender_id = _id_value(root.get("sender_id")) or _id_value(sender.get("sender_id")) or _id_value(payload.get("sender_id"))
    message_id = str(root.get("message_id") or message.get("message_id") or payload.get("message_id") or "")
    chat_type = str(root.get("chat_type") or message.get("chat_type") or payload.get("chat_type") or "")
    message_type = str(root.get("message_type") or message.get("message_type") or payload.get("message_type") or "")
    text = _decode_content(root.get("content") if "content" in root else message.get("content"))
    return FeishuInboundEvent(
        text=text,
        message_id=message_id,
        chat_id=chat_id,
        sender_id=sender_id,
        chat_type=chat_type,
        message_type=message_type,
        raw=payload,
    )


def should_accept(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, allow_any_chat: bool = False) -> tuple[bool, str]:
    if not cfg.enabled:
        return False, "feishu bridge disabled"
    if not event.text:
        return False, "empty message"
    if event.text.startswith(ACK_PREFIX):
        return False, "bridge ack message"
    if event.sender_id and event.sender_id in cfg.ignored_sender_ids:
        return False, "ignored sender"
    if cfg.allowed_chat_ids:
        if event.chat_id not in cfg.allowed_chat_ids:
            return False, f"chat {event.chat_id or '(missing)'} not allowed"
    elif not allow_any_chat:
        return False, "no allowed_chat_ids configured; pass --allow-any-chat for development"
    if cfg.allowed_sender_ids and event.sender_id not in cfg.allowed_sender_ids:
        return False, f"sender {event.sender_id or '(missing)'} not allowed"
    return True, "accepted"


def build_pilot_system_prompt(cfg: FeishuBridgeConfig) -> str:
    projects = _project_lines()
    project_block = "\n".join(projects) if projects else "(~/.cnb/projects.json 里还没有注册项目)"
    return (
        f"你是这台 Mac 的终端主管同学，身份名是 {cfg.pilot_name}。\n"
        "用户会通过飞书把消息发给你。你需要读懂用户意图，必要时选择本机项目，"
        "再用 cnb/board/swarm 命令协调项目里的负责同学。\n\n"
        f"当前启动目录: {cfg.project_root}\n"
        f"本机已注册项目:\n{project_block}\n\n"
        "飞书消息进入后会以 [Feishu inbound] 开头，并带有 message_id。Claude Code 的实时 TUI "
        "渲染不会同步到飞书；不要把终端画面当成飞书回复。接手后先处理任务，处理完成或需要用户确认时，"
        "必须在 shell 中执行 `cnb feishu reply <message_id> \"回复内容\"` 把结果回到飞书。"
        "用户如果想看终端，可在飞书发送 /cnb_tui 或 /c_tui 获取快照，发送 /cnb_watch 或 /c_watch "
        "获取只读 Web TUI 链接。"
    )


def _project_lines(limit: int = 20) -> list[str]:
    try:
        from lib.global_registry import list_projects

        projects = list_projects()
    except Exception:
        return []
    lines: list[str] = []
    for item in projects[:limit]:
        name = item.get("name", "(unnamed)")
        path = item.get("path", "")
        lines.append(f"- {name}: {path}")
    return lines


def build_pilot_command(cfg: FeishuBridgeConfig) -> list[str]:
    prompt = build_pilot_system_prompt(cfg)
    return ["codex", *CODEX_PERMISSION_FLAGS, "--cd", str(cfg.project_root), prompt]


def start_pilot_if_needed(cfg: FeishuBridgeConfig) -> BridgeResult:
    if has_session(cfg.pilot_tmux):
        return BridgeResult(True, f"{cfg.pilot_tmux} already running")
    if not cfg.auto_start:
        return BridgeResult(False, f"{cfg.pilot_tmux} is not running and auto_start=false")

    if not cfg.project_root.exists():
        return BridgeResult(False, f"project root does not exist: {cfg.project_root}")
    command = shlex.join(build_pilot_command(cfg))
    try:
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", cfg.pilot_tmux, "-c", str(cfg.project_root), command],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to start {cfg.pilot_tmux}: {exc}")
    if result.returncode != 0:
        detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
        return BridgeResult(False, f"failed to start {cfg.pilot_tmux}: {detail}")
    if cfg.startup_wait_seconds > 0:
        time.sleep(cfg.startup_wait_seconds)
    return BridgeResult(True, f"started {cfg.pilot_tmux}")


def format_for_pilot(event: FeishuInboundEvent) -> str:
    parts = [
        "[Feishu inbound]",
        f"message_id: {event.message_id or '(unknown)'}",
        f"chat_id: {event.chat_id or '(unknown)'}",
        f"sender_id: {event.sender_id or '(unknown)'}",
    ]
    if event.message_type:
        parts.append(f"message_type: {event.message_type}")
    parts.extend(["", event.text])
    return "\n".join(parts)


def command_name(text: str) -> str:
    head = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    return head.lower()


def is_bridge_command(text: str) -> bool:
    name = command_name(text)
    return name in TUI_COMMANDS or name in WATCH_COMMANDS or name in HELP_COMMANDS


def route_event(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, dry_run: bool = False) -> BridgeResult:
    message = format_for_pilot(event)
    if dry_run:
        print(message)
        return BridgeResult(True, "dry-run")

    started = start_pilot_if_needed(cfg)
    if not started.handled:
        return started
    if not tmux_send(cfg.pilot_tmux, message):
        return BridgeResult(False, f"failed to send message to {cfg.pilot_tmux}")
    return BridgeResult(True, f"delivered to {cfg.pilot_tmux}")


def reply_ack(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, detail: str) -> BridgeResult:
    if not cfg.ack:
        return BridgeResult(False, "ack disabled")
    if not event.message_id:
        return BridgeResult(False, "message_id missing")
    text = f"{ACK_PREFIX}。{detail}"
    return send_reply(cfg, event.message_id, text, idempotency_key=_ack_key(event.message_id))


def send_reply(cfg: FeishuBridgeConfig, message_id: str, text: str, *, idempotency_key: str = "") -> BridgeResult:
    if cfg.transport not in SUPPORTED_TRANSPORTS:
        return BridgeResult(False, f"unsupported Feishu transport: {cfg.transport}")
    if not message_id:
        return BridgeResult(False, "message_id missing")
    if not text.strip():
        return BridgeResult(False, "reply text is empty")
    cmd = [
        "lark-cli",
        "im",
        "+messages-reply",
        "--as",
        cfg.identity,
        "--message-id",
        message_id,
        "--text",
        text.strip(),
    ]
    if idempotency_key:
        cmd.extend(["--idempotency-key", idempotency_key])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return BridgeResult(False, "Hermes lark-cli not found")
    except subprocess.TimeoutExpired:
        return BridgeResult(False, "Hermes lark-cli reply timed out")
    except OSError as exc:
        return BridgeResult(False, f"Hermes lark-cli reply failed: {exc}")
    if result.returncode == 0:
        return BridgeResult(True, "reply sent")
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"Hermes lark-cli reply failed: {detail}")


def handle_bridge_command(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, dry_run: bool = False) -> BridgeResult | None:
    name = command_name(event.text)
    if name in TUI_COMMANDS:
        reply = build_tui_snapshot_reply(cfg)
        return reply_to_command(event, cfg, reply, dry_run=dry_run)
    if name in WATCH_COMMANDS:
        started = start_watch_viewer(cfg)
        reply = started.detail if started.handled else f"无法启动只读 Web TUI：{started.detail}"
        return reply_to_command(event, cfg, reply, dry_run=dry_run)
    if name in HELP_COMMANDS:
        return reply_to_command(event, cfg, command_help_text(), dry_run=dry_run)
    return None


def reply_to_command(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, text: str, *, dry_run: bool = False) -> BridgeResult:
    if dry_run:
        print(text)
        return BridgeResult(True, "dry-run command")
    result = send_reply(cfg, event.message_id, text)
    if result.handled:
        return BridgeResult(True, "command reply sent")
    return BridgeResult(False, result.detail)


def command_help_text() -> str:
    return (
        "CNB 飞书命令：\n"
        "- /cnb_tui 或 /c_tui：查看终端主管同学当前 TUI 快照\n"
        "- /cnb_watch 或 /c_watch：启动只读 Web TUI 观看链接\n"
        "- /cnb_help 或 /c_help：显示这段帮助\n\n"
        "普通消息会转给这台 Mac 的终端主管同学处理。"
    )


def build_tui_snapshot_reply(cfg: FeishuBridgeConfig) -> str:
    captured = capture_tui_snapshot(cfg)
    if not captured.handled:
        return f"无法获取终端主管 TUI：{captured.detail}"
    body = _truncate_text(captured.detail.strip() or "(tmux pane has no visible content)", SNAPSHOT_MAX_CHARS)
    return f"终端主管 TUI 快照（最近 {cfg.tui_capture_lines} 行）：\n\n```text\n{body}\n```"


def capture_tui_snapshot(cfg: FeishuBridgeConfig) -> BridgeResult:
    started = start_pilot_if_needed(cfg)
    if not started.handled:
        return started
    lines = max(10, min(cfg.tui_capture_lines, 500))
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", cfg.pilot_tmux, "-p", "-J", "-S", f"-{lines}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"tmux capture failed: {exc}")
    if result.returncode != 0:
        detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
        return BridgeResult(False, f"tmux capture failed: {detail}")
    return BridgeResult(True, result.stdout.rstrip())


def start_watch_viewer(cfg: FeishuBridgeConfig) -> BridgeResult:
    started = start_pilot_if_needed(cfg)
    if not started.handled:
        return started

    tool = choose_watch_tool(cfg.watch_tool)
    if not tool:
        return BridgeResult(False, f"不支持的 watch_tool：{cfg.watch_tool}")

    port = cfg.watch_port if cfg.watch_port > 0 else DEFAULT_WATCH_PORT
    if has_session(cfg.watch_tmux):
        return BridgeResult(True, f"只读 Web TUI 已在运行：{watch_url(cfg, port)}")

    if not _port_available(cfg.watch_host, port):
        port = _find_available_port(cfg.watch_host, port + 1)

    url = watch_url(cfg, port)
    command = shlex.join(build_watch_command(tool, cfg, port))
    try:
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", cfg.watch_tmux, "-c", str(cfg.project_root), command],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to start {cfg.watch_tmux}: {exc}")
    if result.returncode != 0:
        detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
        return BridgeResult(False, f"failed to start {cfg.watch_tmux}: {detail}")
    scope = "公网/隧道" if cfg.watch_public_url else "本机"
    return BridgeResult(True, f"只读 Web TUI 已启动（{scope}，{tool}）：{url}")


def choose_watch_tool(preferred: str) -> str:
    if preferred in {"", "auto", "builtin"}:
        return "builtin"
    if preferred:
        return preferred if shutil.which(preferred) else ""
    return "builtin"


def build_watch_command(tool: str, cfg: FeishuBridgeConfig, port: int) -> list[str]:
    install_home = Path(__file__).resolve().parent.parent
    cnb = install_home / "bin" / "cnb"
    if tool == "builtin":
        return [
            str(cnb),
            "feishu",
            "--config",
            str(cfg.config_path),
            "watch-serve",
            "--host",
            cfg.watch_host,
            "--port",
            str(port),
        ]
    attach = ["tmux", "attach-session", "-t", cfg.pilot_tmux]
    if tool == "ttyd":
        return ["ttyd", "-R", "-i", cfg.watch_host, "-p", str(port), *attach]
    if tool == "gotty":
        return ["gotty", "--address", cfg.watch_host, "--port", str(port), *attach]
    return [tool, *attach]


def watch_url(cfg: FeishuBridgeConfig, port: int) -> str:
    if cfg.watch_public_url:
        return cfg.watch_public_url
    host = "127.0.0.1" if cfg.watch_host in {"", "0.0.0.0", "::"} else cfg.watch_host
    return f"http://{host}:{port}"


def _port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host or DEFAULT_WATCH_HOST, port))
            return True
    except OSError:
        return False


def _find_available_port(host: str, start: int) -> int:
    for port in range(start, start + 100):
        if _port_available(host, port):
            return port
    return start


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def serve_watch_viewer(cfg: FeishuBridgeConfig, host: str, port: int) -> int:
    class WatchHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self._send_html(watch_page_html(cfg))
                return
            if self.path.startswith("/snapshot"):
                captured = capture_tui_snapshot(cfg)
                payload = {
                    "ok": captured.handled,
                    "text": captured.detail if captured.handled else f"ERROR: {captured.detail}",
                    "session": cfg.pilot_tmux,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self._send_json(payload)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[cnb-feishu-watch] {self.address_string()} {fmt % args}", file=sys.stderr)

        def _send_html(self, body: str) -> None:
            encoded = body.encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer((host, port), WatchHandler)
    print(f"[cnb-feishu-watch] serving {cfg.pilot_tmux} at http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def watch_page_html(cfg: FeishuBridgeConfig) -> str:
    title = f"CNB TUI - {cfg.pilot_tmux}"
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; background: #0c0d0e; color: #e7e7e7; font: 14px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    header {{ display: flex; justify-content: space-between; gap: 16px; padding: 10px 14px; background: #17191b; border-bottom: 1px solid #30343a; }}
    #screen {{ white-space: pre-wrap; padding: 14px; line-height: 1.4; overflow-wrap: anywhere; }}
    #meta {{ color: #9aa0a6; }}
  </style>
</head>
<body>
  <header><strong>{safe_title}</strong><span id="meta">connecting...</span></header>
  <pre id="screen"></pre>
  <script>
    async function refresh() {{
      try {{
        const res = await fetch('/snapshot', {{ cache: 'no-store' }});
        const data = await res.json();
        document.getElementById('screen').textContent = data.text || '';
        document.getElementById('meta').textContent = data.updated_at || '';
      }} catch (err) {{
        document.getElementById('meta').textContent = String(err);
      }}
    }}
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


def _ack_key(message_id: str) -> str:
    digest = hashlib.sha256(message_id.encode()).hexdigest()[:16]
    return f"cnb-feishu-ack-{digest}"


def _snippet(text: str) -> str:
    return " ".join(text.strip().split())[:240]


def handle_payload(
    payload: dict[str, Any],
    cfg: FeishuBridgeConfig,
    *,
    allow_any_chat: bool = False,
    dry_run: bool = False,
    send_ack: bool = True,
) -> BridgeResult:
    event = extract_event(payload)
    accepted, reason = should_accept(event, cfg, allow_any_chat=allow_any_chat)
    if not accepted:
        return BridgeResult(False, f"skipped: {reason}")

    command_result = handle_bridge_command(event, cfg, dry_run=dry_run)
    if command_result is not None:
        return command_result

    routed = route_event(event, cfg, dry_run=dry_run)
    if routed.handled and send_ack and not dry_run:
        ack = reply_ack(event, cfg, routed.detail)
        if not ack.handled:
            return BridgeResult(True, f"{routed.detail}; ack skipped: {ack.detail}")
    return routed


def handle_event_line(
    line: str,
    cfg: FeishuBridgeConfig,
    *,
    allow_any_chat: bool = False,
    dry_run: bool = False,
    send_ack: bool = True,
) -> BridgeResult:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        return BridgeResult(False, f"invalid json: {exc}")
    if not isinstance(payload, dict):
        return BridgeResult(False, "invalid event payload")
    return handle_payload(payload, cfg, allow_any_chat=allow_any_chat, dry_run=dry_run, send_ack=send_ack)


def _stderr_ready_pump(stream: Any, ready: threading.Event) -> None:
    for line in stream:
        if "[event] ready" in line:
            ready.set()
        print(line, end="", file=sys.stderr)


def consume_events(cfg: FeishuBridgeConfig, *, allow_any_chat: bool = False, dry_run: bool = False, max_events: int = 0, timeout: str = "") -> int:
    if not cfg.enabled:
        print("ERROR: feishu bridge disabled", file=sys.stderr)
        return 1
    if cfg.transport not in SUPPORTED_TRANSPORTS:
        print(f"ERROR: unsupported Feishu transport: {cfg.transport}", file=sys.stderr)
        return 1
    if not cfg.allowed_chat_ids and not allow_any_chat:
        print("ERROR: no allowed_chat_ids configured in ~/.cnb/config.toml [feishu]", file=sys.stderr)
        print("For development only, pass --allow-any-chat.", file=sys.stderr)
        return 1

    cmd = ["lark-cli", "event", "consume", cfg.event_key, "--as", cfg.identity]
    if max_events > 0:
        cmd.extend(["--max-events", str(max_events)])
    if timeout:
        cmd.extend(["--timeout", timeout])

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print("ERROR: Hermes lark-cli not found", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: failed to start lark-cli event consumer: {exc}", file=sys.stderr)
        return 1

    assert proc.stdout is not None
    assert proc.stderr is not None
    ready = threading.Event()
    threading.Thread(target=_stderr_ready_pump, args=(proc.stderr, ready), daemon=True).start()
    if not ready.wait(timeout=20) and proc.poll() is not None:
        return proc.returncode or 1

    handled = 0
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        result = handle_event_line(line, cfg, allow_any_chat=allow_any_chat, dry_run=dry_run)
        print(result.detail)
        if result.handled:
            handled += 1

    if proc.stdin:
        try:
            proc.stdin.close()
        except OSError:
            pass
    code = proc.wait()
    print(f"feishu bridge handled {handled} event(s)")
    return code


def start_bridge_daemon(cfg: FeishuBridgeConfig) -> BridgeResult:
    if has_session(cfg.bridge_tmux):
        return BridgeResult(True, f"{cfg.bridge_tmux} already running")
    install_home = Path(__file__).resolve().parent.parent
    cnb = install_home / "bin" / "cnb"
    command = (
        f"CNB_PROJECT={shlex.quote(str(cfg.project_root))} "
        f"{shlex.quote(str(cnb))} feishu --config {shlex.quote(str(cfg.config_path))} listen"
    )
    try:
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", cfg.bridge_tmux, "-c", str(cfg.project_root), command],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to start {cfg.bridge_tmux}: {exc}")
    if result.returncode == 0:
        return BridgeResult(True, f"started {cfg.bridge_tmux}")
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"failed to start {cfg.bridge_tmux}: {detail}")


def stop_bridge_daemon(cfg: FeishuBridgeConfig) -> BridgeResult:
    if not has_session(cfg.bridge_tmux):
        return BridgeResult(True, f"{cfg.bridge_tmux} is not running")
    try:
        result = subprocess.run(["tmux", "kill-session", "-t", cfg.bridge_tmux], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to stop {cfg.bridge_tmux}: {exc}")
    if result.returncode == 0:
        return BridgeResult(True, f"stopped {cfg.bridge_tmux}")
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"failed to stop {cfg.bridge_tmux}: {detail}")


def stop_watch_viewer(cfg: FeishuBridgeConfig) -> BridgeResult:
    if not has_session(cfg.watch_tmux):
        return BridgeResult(True, f"{cfg.watch_tmux} is not running")
    try:
        result = subprocess.run(["tmux", "kill-session", "-t", cfg.watch_tmux], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to stop {cfg.watch_tmux}: {exc}")
    if result.returncode == 0:
        return BridgeResult(True, f"stopped {cfg.watch_tmux}")
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"failed to stop {cfg.watch_tmux}: {detail}")


def print_status(cfg: FeishuBridgeConfig) -> None:
    print(f"配置文件: {cfg.config_path}")
    print(f"启用: {'是' if cfg.enabled else '否'}")
    print(f"通道: {cfg.transport}（Hermes 飞书 CLI 开发测试通道，不是 CNB 生产身份源）")
    print(f"事件: {cfg.event_key} ({cfg.identity})")
    print(f"允许 chat: {', '.join(sorted(cfg.allowed_chat_ids)) if cfg.allowed_chat_ids else '(未配置)'}")
    print(f"允许 sender: {', '.join(sorted(cfg.allowed_sender_ids)) if cfg.allowed_sender_ids else '(全部)'}")
    print(f"终端主管同学: {cfg.pilot_name}")
    print(f"终端主管 tmux: {cfg.pilot_tmux} ({'running' if has_session(cfg.pilot_tmux) else 'stopped'})")
    print(f"bridge tmux: {cfg.bridge_tmux} ({'running' if has_session(cfg.bridge_tmux) else 'stopped'})")
    print(f"watch tmux: {cfg.watch_tmux} ({'running' if has_session(cfg.watch_tmux) else 'stopped'})")
    print("飞书命令: /cnb_tui, /c_tui, /cnb_watch, /c_watch")
    print(f"Web TUI: {watch_url(cfg, cfg.watch_port)} ({cfg.watch_tool})")
    print(f"引擎: {cfg.agent}")
    print(f"项目目录: {cfg.project_root}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cnb feishu", description="Feishu inbound bridge for the Mac terminal supervisor tongxue")
    parser.add_argument("--config", type=Path, default=None, help="path to global cnb config (default: ~/.cnb/config.toml)")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="show bridge config and tmux status")

    listen = sub.add_parser("listen", help="consume Feishu IM events and route them to the terminal supervisor tongxue")
    listen.add_argument("--allow-any-chat", action="store_true", help="development only: accept events without chat allowlist")
    listen.add_argument("--dry-run", action="store_true", help="print routed messages without touching tmux or Feishu")
    listen.add_argument("--once", action="store_true", help="handle one event and exit")
    listen.add_argument("--max-events", type=int, default=0)
    listen.add_argument("--timeout", default="")

    handle = sub.add_parser("handle-event", help="route one NDJSON event from an argument or stdin")
    handle.add_argument("event_json", nargs="?")
    handle.add_argument("--allow-any-chat", action="store_true")
    handle.add_argument("--dry-run", action="store_true")
    handle.add_argument("--no-ack", action="store_true")

    sub.add_parser("start", help="start the bridge listener in tmux")
    sub.add_parser("stop", help="stop the bridge listener tmux session")
    sub.add_parser("tui", help="print the terminal supervisor TUI snapshot")
    sub.add_parser("watch", help="start the read-only Web TUI viewer")
    sub.add_parser("watch-stop", help="stop the read-only Web TUI viewer")
    watch_serve = sub.add_parser("watch-serve", help="serve the built-in read-only Web TUI viewer")
    watch_serve.add_argument("--host", default=None)
    watch_serve.add_argument("--port", type=int, default=None)

    reply = sub.add_parser("reply", help="reply to a Feishu message by message_id")
    reply.add_argument("message_id")
    reply.add_argument("text", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = FeishuBridgeConfig.load(config_path=args.config)

    if args.cmd in (None, "status"):
        print_status(cfg)
        return 0
    if args.cmd == "listen":
        max_events = 1 if args.once and args.max_events == 0 else args.max_events
        return consume_events(
            cfg,
            allow_any_chat=args.allow_any_chat,
            dry_run=args.dry_run,
            max_events=max_events,
            timeout=args.timeout,
        )
    if args.cmd == "handle-event":
        line = args.event_json or sys.stdin.read()
        result = handle_event_line(
            line,
            cfg,
            allow_any_chat=args.allow_any_chat,
            dry_run=args.dry_run,
            send_ack=not args.no_ack,
        )
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "start":
        result = start_bridge_daemon(cfg)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "stop":
        result = stop_bridge_daemon(cfg)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "tui":
        result = capture_tui_snapshot(cfg)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "watch":
        result = start_watch_viewer(cfg)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "watch-stop":
        result = stop_watch_viewer(cfg)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "watch-serve":
        return serve_watch_viewer(cfg, args.host or cfg.watch_host, args.port or cfg.watch_port)
    if args.cmd == "reply":
        result = send_reply(cfg, args.message_id, " ".join(args.text))
        print(result.detail)
        return 0 if result.handled else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
