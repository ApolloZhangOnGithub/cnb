"""Feishu inbound bridge for waking the machine-level device supervisor tongxue."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from lib.swarm import CODEX_PERMISSION_FLAGS
from lib.tmux_utils import has_session, tmux_send

DEFAULT_EVENT_KEY = "im.message.receive_v1"
LEGACY_SUPERVISOR_LABEL = "终端主管同学"
LEGACY_DEFAULT_PILOT_TMUX = "cnb-terminal-supervisor"
LEGACY_ACK_PREFIX = f"已转给这台 Mac 的{LEGACY_SUPERVISOR_LABEL}"


@dataclass(frozen=True, eq=False)
class PilotRole:
    """Role-specific defaults for a pilot (supervisor or chief)."""

    role_id: str
    label: str
    default_name: str
    default_tmux: str
    default_bridge_tmux: str
    default_watch_tmux: str
    ack_prefix: str
    status_title: str
    name_config_keys: tuple[str, ...]
    tmux_config_keys: tuple[str, ...]

    def __str__(self) -> str:
        return self.role_id

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PilotRole):
            return self.role_id == other.role_id
        if isinstance(other, str):
            return self.role_id == other.strip().lower().replace("-", "_")
        return False

    def __hash__(self) -> int:
        return hash(self.role_id)


SUPERVISOR_ROLE = PilotRole(
    role_id="device_supervisor",
    label="设备主管同学",
    default_name="device-supervisor",
    default_tmux="cnb-device-supervisor",
    default_bridge_tmux="cnb-feishu-bridge",
    default_watch_tmux="cnb-feishu-watch",
    ack_prefix="已转给这台 Mac 的设备主管同学",
    status_title="CNB 设备状态",
    name_config_keys=(
        "device_supervisor_name",
        "terminal_supervisor_name",
        "device_chief_name",
        "device-chief-name",
    ),
    tmux_config_keys=(
        "device_supervisor_tmux",
        "terminal_supervisor_tmux",
        "device_chief_tmux",
        "device-chief-tmux",
    ),
)

CHIEF_ROLE = PilotRole(
    role_id="device_chief",
    label="机器总管同学",
    default_name="device-chief",
    default_tmux="cnb-device-chief",
    default_bridge_tmux="cnb-feishu-chief-bridge",
    default_watch_tmux="cnb-feishu-chief-watch",
    ack_prefix="已转给 CNB 机器总管同学",
    status_title="CNB 机器总管状态",
    name_config_keys=(
        "device_chief_name",
        "device-chief-name",
        "chief_name",
        "chief-name",
        "device_supervisor_name",
        "terminal_supervisor_name",
    ),
    tmux_config_keys=(
        "device_chief_tmux",
        "device-chief-tmux",
        "chief_tmux",
        "chief-tmux",
        "device_supervisor_tmux",
        "terminal_supervisor_tmux",
    ),
)

DEVICE_SUPERVISOR_LABEL = SUPERVISOR_ROLE.label
DEVICE_CHIEF_LABEL = CHIEF_ROLE.label
DEFAULT_PILOT_ROLE = SUPERVISOR_ROLE.role_id
DEVICE_CHIEF_ROLE = CHIEF_ROLE.role_id
DEFAULT_PILOT_NAME = SUPERVISOR_ROLE.default_name
DEFAULT_CHIEF_NAME = CHIEF_ROLE.default_name
DEFAULT_PILOT_TMUX = SUPERVISOR_ROLE.default_tmux
DEFAULT_CHIEF_TMUX = CHIEF_ROLE.default_tmux
DEFAULT_BRIDGE_TMUX = SUPERVISOR_ROLE.default_bridge_tmux
DEFAULT_CHIEF_BRIDGE_TMUX = CHIEF_ROLE.default_bridge_tmux
DEFAULT_WATCH_TMUX = SUPERVISOR_ROLE.default_watch_tmux
DEFAULT_CHIEF_WATCH_TMUX = CHIEF_ROLE.default_watch_tmux
DEFAULT_WATCH_HOST = "127.0.0.1"
DEFAULT_WATCH_PORT = 8765
DEFAULT_WATCH_REFRESH_MS = 250
DEFAULT_WEBHOOK_HOST = "127.0.0.1"
DEFAULT_WEBHOOK_PORT = 8787
DEFAULT_TRANSPORT = "local_openapi"
SUPPORTED_PILOT_AGENTS = frozenset({"codex"})
SUPPORTED_PILOT_ROLES = frozenset({DEFAULT_PILOT_ROLE, DEVICE_CHIEF_ROLE})
SUPPORTED_TRANSPORTS = frozenset({"local_openapi", "hermes_lark_cli"})
SUPPORTED_ACTIVITY_RENDER_STYLES = frozenset({"auto", "codex", "claude"})
SUPPORTED_GROUP_MESSAGE_ROUTING = frozenset({"all", "targeted"})
SUPPORTED_NOTIFICATION_POLICIES = frozenset({"final_only", "ack", "live"})
DEFAULT_NOTIFICATION_POLICY = "final_only"
DEFAULT_GROUP_MESSAGE_ROUTING = "all"
DEFAULT_READBACK_LIMIT = 12
MAX_READBACK_LIMIT = 50
DEFAULT_RESOURCE_HANDOFF_MAX_BYTES = 25 * 1024 * 1024
MAX_RESOURCE_HANDOFF_BYTES = 100 * 1024 * 1024
CAFFEINATE_ARGS = ("-dims",)
SHORT_REPLY_MAX_CHARS = 280
SHORT_REPLY_MAX_LINES = 4
ACK_PREFIX = SUPERVISOR_ROLE.ack_prefix
CHIEF_ACK_PREFIX = CHIEF_ROLE.ack_prefix
ACK_PREFIXES = frozenset({ACK_PREFIX, CHIEF_ACK_PREFIX, LEGACY_ACK_PREFIX})
TUI_COMMANDS = frozenset({"/cnb_tui", "/c_tui"})
WATCH_COMMANDS = frozenset({"/cnb_watch", "/c_watch"})
HELP_COMMANDS = frozenset({"/cnb_help", "/c_help"})
STATUS_COMMANDS = frozenset({"/cnb_status", "/c_status"})
SNAPSHOT_MAX_CHARS = 3500
ACTIVITY_CARD_LINE_MAX_CHARS = 360
ACTIVITY_CARD_SCREEN_MAX_LINES = 12
ACTIVITY_CARD_SCREEN_LINE_MAX_CHARS = 140
DEFAULT_ACTIVITY_UPDATE_SECONDS = (1,)
DEFAULT_ACTIVITY_UPDATE_REPEAT_SECONDS = 1
DEFAULT_ACTIVITY_UPDATE_MAX_SECONDS = 600
ACTIVITY_STALE_SECONDS = 600
ACTIVITY_WORK_RE = re.compile(r"^\s*[•●◦]\s*(Working|Thinking|Running)\b", re.IGNORECASE | re.MULTILINE)
ACTIVITY_PROMPT_RE = re.compile(r"^\s*[›❯>]\s*", re.MULTILINE)
AGENT_PROCESS_RE = re.compile(r"(^|/|\s)(codex|claude)(\s|$)", re.IGNORECASE)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CODE_FENCE_RE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*\n.*?```", re.DOTALL)
MARKDOWN_REPLY_RE = re.compile(
    r"(^\s{0,3}#{1,6}\s+\S|^\s{0,3}(?:[-*+]|\d+[.)])\s+\S|^\s{0,3}>\s+\S|"
    r"\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\([^)]+\)|^\s*\|.+\|\s*$)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class FeishuInboundEvent:
    text: str
    message_id: str = ""
    root_id: str = ""
    parent_id: str = ""
    thread_id: str = ""
    upper_message_id: str = ""
    chat_id: str = ""
    sender_id: str = ""
    chat_type: str = ""
    message_type: str = ""
    mention_ids: tuple[str, ...] = ()
    mention_names: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BridgeResult:
    handled: bool
    detail: str


@dataclass(frozen=True)
class ResourceDownloadResult:
    handled: bool
    detail: str
    path: str = ""
    content_type: str = ""
    size: int = 0


@dataclass(frozen=True)
class ActivitySection:
    title: str
    body: str
    tone: str = "default"


@dataclass(frozen=True)
class ActivitySnapshot:
    title: str
    subtitle: str
    sections: tuple[ActivitySection, ...]
    style: str
    elapsed_seconds: int = 0
    updated_at: str = ""


@dataclass(frozen=True)
class FeishuBridgeConfig:
    config_path: Path
    project_root: Path
    enabled: bool = True
    transport: str = DEFAULT_TRANSPORT
    lark_cli_profile: str = ""
    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    event_key: str = DEFAULT_EVENT_KEY
    identity: str = "bot"
    webhook_host: str = DEFAULT_WEBHOOK_HOST
    webhook_port: int = DEFAULT_WEBHOOK_PORT
    webhook_public_url: str = ""
    allowed_chat_ids: frozenset[str] = frozenset()
    auto_bind_chat: bool = False
    allowed_sender_ids: frozenset[str] = frozenset()
    ignored_sender_ids: frozenset[str] = frozenset()
    bot_open_id: str = ""
    bot_name: str = ""
    group_message_routing: str = DEFAULT_GROUP_MESSAGE_ROUTING
    group_message_routing_chat_ids: frozenset[str] = frozenset()
    pilot_role: str = DEFAULT_PILOT_ROLE
    pilot_name: str = SUPERVISOR_ROLE.default_name
    pilot_tmux: str = SUPERVISOR_ROLE.default_tmux
    bridge_tmux: str = SUPERVISOR_ROLE.default_bridge_tmux
    agent: str = "codex"
    auto_start: bool = True
    startup_wait_seconds: float = 2.0
    notification_policy: str = DEFAULT_NOTIFICATION_POLICY
    ack: bool = True
    activity_updates: bool = True
    activity_update_seconds: tuple[int, ...] = DEFAULT_ACTIVITY_UPDATE_SECONDS
    activity_update_repeat_seconds: int = DEFAULT_ACTIVITY_UPDATE_REPEAT_SECONDS
    activity_update_max_seconds: int = DEFAULT_ACTIVITY_UPDATE_MAX_SECONDS
    activity_render_style: str = "auto"
    tui_capture_lines: int = 120
    watch_tmux: str = DEFAULT_WATCH_TMUX
    watch_host: str = DEFAULT_WATCH_HOST
    watch_port: int = DEFAULT_WATCH_PORT
    watch_public_url: str = ""
    watch_token: str = ""
    watch_tool: str = "builtin"
    watch_refresh_ms: int = DEFAULT_WATCH_REFRESH_MS
    readback_enabled: bool = False
    readback_allow_unlisted_chat: bool = False
    readback_default_limit: int = DEFAULT_READBACK_LIMIT
    readback_max_limit: int = MAX_READBACK_LIMIT
    resource_handoff_enabled: bool = True
    resource_handoff_max_bytes: int = DEFAULT_RESOURCE_HANDOFF_MAX_BYTES
    caffeine_enabled: bool = True

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
        role = _resolve_role(_first_value(section, "role", "pilot_role", "cnb_role", "supervisor_role"))
        if role is SUPERVISOR_ROLE and _first_value(section, "device_chief_name", "device-chief-name"):
            role = CHIEF_ROLE
        activity_repeat_raw = section.get("activity_update_repeat_seconds")
        if activity_repeat_raw is None:
            activity_repeat_raw = section.get("activity_repeat_seconds")
        readback_max_limit = max(
            1,
            min(
                MAX_READBACK_LIMIT,
                _int(_first_value(section, "readback_max_limit", "readback_history_max_limit"), MAX_READBACK_LIMIT),
            ),
        )
        readback_default_limit = max(
            1,
            min(
                readback_max_limit,
                _int(
                    _first_value(section, "readback_default_limit", "readback_history_limit"),
                    DEFAULT_READBACK_LIMIT,
                ),
            ),
        )
        resource_handoff_max_bytes = max(
            1,
            min(
                MAX_RESOURCE_HANDOFF_BYTES,
                _int(
                    _first_value(section, "resource_handoff_max_bytes", "attachment_handoff_max_bytes"),
                    DEFAULT_RESOURCE_HANDOFF_MAX_BYTES,
                ),
            ),
        )

        return cls(
            config_path=path,
            project_root=root,
            enabled=_bool(section.get("enabled"), True),
            transport=str(section.get("transport") or DEFAULT_TRANSPORT),
            lark_cli_profile=str(section.get("lark_cli_profile") or section.get("profile") or ""),
            app_id=str(section.get("app_id") or os.environ.get("FEISHU_APP_ID") or ""),
            app_secret=str(section.get("app_secret") or os.environ.get("FEISHU_APP_SECRET") or ""),
            verification_token=str(
                section.get("verification_token") or os.environ.get("FEISHU_VERIFICATION_TOKEN") or ""
            ),
            event_key=str(section.get("event_key") or section.get("event-key") or DEFAULT_EVENT_KEY),
            identity=str(section.get("identity") or "bot"),
            webhook_host=str(section.get("webhook_host") or DEFAULT_WEBHOOK_HOST),
            webhook_port=_int(section.get("webhook_port"), DEFAULT_WEBHOOK_PORT),
            webhook_public_url=str(section.get("webhook_public_url") or ""),
            allowed_chat_ids=frozenset(
                _strings(section, "allowed_chat_ids", "allowed-chat-ids", "chat_ids", "chat_id")
            ),
            auto_bind_chat=_bool(section.get("auto_bind_chat"), _bool(section.get("discover_chat"), False)),
            allowed_sender_ids=frozenset(
                _strings(section, "allowed_sender_ids", "allowed-sender-ids", "sender_ids", "sender_id")
            ),
            ignored_sender_ids=frozenset(_strings(section, "ignored_sender_ids", "ignored-sender-ids")),
            bot_open_id=str(_first_value(section, "bot_open_id", "bot-open-id", "app_bot_open_id", "app_bot_id") or ""),
            bot_name=str(_first_value(section, "bot_name", "bot-name", "app_bot_name") or ""),
            group_message_routing=_group_message_routing(
                _first_value(section, "group_message_routing", "group-routing", "group_routing")
            ),
            group_message_routing_chat_ids=frozenset(
                _strings(
                    section,
                    "group_message_routing_chat_ids",
                    "group-message-routing-chat-ids",
                    "group_message_routing_chats",
                    "group-routing-chat-ids",
                    "group_routing_chat_ids",
                )
            ),
            pilot_role=role.role_id,
            pilot_name=str(
                _first_value(section, *role.name_config_keys)
                or section.get("supervisor_name")
                or section.get("pilot_name")
                or section.get("on_duty_name")
                or section.get("session")
                or role.default_name
            ),
            pilot_tmux=str(
                _first_value(section, *role.tmux_config_keys)
                or section.get("supervisor_tmux")
                or section.get("pilot_tmux")
                or section.get("tmux_session")
                or role.default_tmux
            ),
            bridge_tmux=str(
                section.get("bridge_tmux") or section.get("bridge_tmux_session") or role.default_bridge_tmux
            ),
            agent=agent,
            auto_start=_bool(section.get("auto_start"), True),
            startup_wait_seconds=_float(section.get("startup_wait_seconds"), 2.0),
            notification_policy=_notification_policy(
                section.get("notification_policy")
                or section.get("push_policy")
                or section.get("ios_notification_policy")
            ),
            ack=_bool(section.get("ack"), True),
            activity_updates=_bool(section.get("activity_updates"), True),
            activity_update_seconds=tuple(
                _int_list(section.get("activity_update_seconds"), DEFAULT_ACTIVITY_UPDATE_SECONDS)
            ),
            activity_update_repeat_seconds=max(0, _int(activity_repeat_raw, DEFAULT_ACTIVITY_UPDATE_REPEAT_SECONDS)),
            activity_update_max_seconds=max(
                0,
                _int(
                    _first_value(section, "activity_update_max_seconds", "activity_max_seconds"),
                    DEFAULT_ACTIVITY_UPDATE_MAX_SECONDS,
                ),
            ),
            activity_render_style=_activity_render_style(
                section.get("activity_render_style") or section.get("render_style")
            ),
            tui_capture_lines=_int(section.get("tui_capture_lines"), 120),
            watch_tmux=str(section.get("watch_tmux") or section.get("watch_tmux_session") or role.default_watch_tmux),
            watch_host=str(section.get("watch_host") or DEFAULT_WATCH_HOST),
            watch_port=_int(section.get("watch_port"), DEFAULT_WATCH_PORT),
            watch_public_url=str(section.get("watch_public_url") or ""),
            watch_token=str(section.get("watch_token") or ""),
            watch_tool=str(section.get("watch_tool") or "builtin"),
            watch_refresh_ms=max(100, _int(section.get("watch_refresh_ms"), DEFAULT_WATCH_REFRESH_MS)),
            readback_enabled=_bool(
                _first_value(section, "readback_enabled", "enable_readback", "context_readback_enabled"), False
            ),
            readback_allow_unlisted_chat=_bool(
                _first_value(section, "readback_allow_unlisted_chat", "readback_allow_any_chat"), False
            ),
            readback_default_limit=readback_default_limit,
            readback_max_limit=readback_max_limit,
            resource_handoff_enabled=_bool(
                _first_value(section, "resource_handoff_enabled", "attachment_handoff_enabled"), True
            ),
            resource_handoff_max_bytes=resource_handoff_max_bytes,
            caffeine_enabled=_bool(_first_value(section, "caffeine_enabled", "keep_awake_enabled", "keep_awake"), True),
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


def _int_list(value: Any, default: tuple[int, ...]) -> list[int]:
    if not isinstance(value, list):
        return list(default)
    result: list[int] = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0:
            result.append(number)
    return result or list(default)


def _activity_render_style(value: Any) -> str:
    style = str(value or "auto").strip().lower()
    return style if style in SUPPORTED_ACTIVITY_RENDER_STYLES else "auto"


def _notification_policy(value: Any) -> str:
    policy = str(value or DEFAULT_NOTIFICATION_POLICY).strip().lower().replace("-", "_")
    aliases = {
        "final": "final_only",
        "quiet": "final_only",
        "silent": "final_only",
        "none": "final_only",
        "normal": "ack",
        "ack_only": "ack",
        "verbose": "live",
        "debug": "live",
    }
    policy = aliases.get(policy, policy)
    return policy if policy in SUPPORTED_NOTIFICATION_POLICIES else DEFAULT_NOTIFICATION_POLICY


_ROLES_BY_ID: dict[str, PilotRole] = {
    SUPERVISOR_ROLE.role_id: SUPERVISOR_ROLE,
    CHIEF_ROLE.role_id: CHIEF_ROLE,
}

_ROLE_ALIASES: dict[str, str] = {
    "chief": CHIEF_ROLE.role_id,
    "devicechief": CHIEF_ROLE.role_id,
    "device_chief": CHIEF_ROLE.role_id,
    "machine_chief": CHIEF_ROLE.role_id,
    "supervisor": SUPERVISOR_ROLE.role_id,
    "device_supervisor": SUPERVISOR_ROLE.role_id,
    "terminal_supervisor": SUPERVISOR_ROLE.role_id,
}


def _resolve_role(value: Any) -> PilotRole:
    if isinstance(value, PilotRole):
        return value
    text = str(value or "").strip().lower().replace("-", "_")
    role_id = _ROLE_ALIASES.get(text, text)
    return _ROLES_BY_ID.get(role_id, SUPERVISOR_ROLE)


def _pilot_role(value: Any) -> PilotRole:
    return _resolve_role(value)


def _default_pilot_name(role: Any) -> str:
    return _resolve_role(role).default_name


def _default_pilot_tmux(role: Any) -> str:
    return _resolve_role(role).default_tmux


def _default_bridge_tmux(role: Any) -> str:
    return _resolve_role(role).default_bridge_tmux


def _default_watch_tmux(role: Any) -> str:
    return _resolve_role(role).default_watch_tmux


def role_label(cfg: FeishuBridgeConfig | None) -> str:
    return _resolve_role(cfg.pilot_role if cfg else SUPERVISOR_ROLE).label


def role_status_title(cfg: FeishuBridgeConfig) -> str:
    return _resolve_role(cfg.pilot_role).status_title


def ack_prefix(cfg: FeishuBridgeConfig) -> str:
    return _resolve_role(cfg.pilot_role).ack_prefix


def feishu_command_prefix(cfg: FeishuBridgeConfig) -> str:
    default_path = (Path.home() / ".cnb" / "config.toml").resolve()
    if cfg.config_path.expanduser().resolve() == default_path:
        return "cnb feishu"
    return f"cnb feishu --config {shlex.quote(str(cfg.config_path))}"


def _group_message_routing(value: Any) -> str:
    mode = str(value or DEFAULT_GROUP_MESSAGE_ROUTING).strip().lower().replace("-", "_")
    return mode if mode in SUPPORTED_GROUP_MESSAGE_ROUTING else DEFAULT_GROUP_MESSAGE_ROUTING


def _first_value(section: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in section:
            return section[key]
    return None


def _strings(section: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = section.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, list):
            values.extend(str(item).strip() for item in value if str(item).strip())
    return values


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple | frozenset | set):
        return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def _render_feishu_section(section: dict[str, Any]) -> str:
    lines = ["[feishu]"]
    for key in sorted(section):
        value = section[key]
        if value in (None, "", [], (), frozenset(), set()):
            continue
        lines.append(f"{key} = {_toml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _replace_toml_section(text: str, section_name: str, rendered: str) -> str:
    lines = text.splitlines()
    start: int | None = None
    end = len(lines)
    header = f"[{section_name}]"
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == header:
            start = index
            continue
        if start is not None and index > start and stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    rendered_lines = rendered.rstrip("\n").splitlines()
    if start is None:
        prefix = lines + ([""] if lines else [])
        output = prefix + rendered_lines
    else:
        output = lines[:start] + rendered_lines + lines[end:]
    return "\n".join(output).rstrip() + "\n"


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
        if "file_name" in content:
            file_name = str(content.get("file_name") or "").strip()
            file_key = str(content.get("file_key") or "").strip()
            return " ".join(part for part in (file_name, f"({file_key})" if file_key else "") if part).strip()
        if "image_key" in content:
            image_key = str(content.get("image_key") or "").strip()
            return f"[image] {image_key}" if image_key else "[image]"
        if "file_key" in content:
            file_key = str(content.get("file_key") or "").strip()
            return f"[file] {file_key}" if file_key else "[file]"
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


def _mention_id(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return (
        _id_value(value.get("id"))
        or _id_value(value.get("user_id"))
        or _id_value(value.get("user"))
        or _id_value(value.get("open_id"))
        or _id_value(value.get("member_id"))
    )


def _extract_mentions(
    root: dict[str, Any],
    message: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    mentions_value = root.get("mentions")
    if mentions_value is None:
        mentions_value = message.get("mentions")
    if mentions_value is None:
        mentions_value = payload.get("mentions")
    if not isinstance(mentions_value, list):
        return (), ()

    ids: list[str] = []
    names: list[str] = []
    for item in mentions_value:
        if not isinstance(item, dict):
            continue
        mention_id = _mention_id(item)
        if mention_id:
            ids.append(mention_id)
        name = str(item.get("name") or item.get("key") or "").strip()
        if name:
            names.append(name)
    return tuple(dict.fromkeys(ids)), tuple(dict.fromkeys(names))


def _event_string(root: dict[str, Any], message: dict[str, Any], payload: dict[str, Any], key: str) -> str:
    return str(root.get(key) or message.get(key) or payload.get(key) or "")


def extract_event(payload: dict[str, Any]) -> FeishuInboundEvent:
    event = payload.get("event")
    root: dict[str, Any] = event if isinstance(event, dict) else payload
    message_value = root.get("message")
    sender_value = root.get("sender")
    message: dict[str, Any] = message_value if isinstance(message_value, dict) else {}
    sender: dict[str, Any] = sender_value if isinstance(sender_value, dict) else {}

    chat_id = _event_string(root, message, payload, "chat_id")
    sender_id = (
        _id_value(root.get("sender_id")) or _id_value(sender.get("sender_id")) or _id_value(payload.get("sender_id"))
    )
    message_id = _event_string(root, message, payload, "message_id")
    root_id = _event_string(root, message, payload, "root_id")
    parent_id = _event_string(root, message, payload, "parent_id")
    thread_id = _event_string(root, message, payload, "thread_id")
    upper_message_id = _event_string(root, message, payload, "upper_message_id")
    chat_type = _event_string(root, message, payload, "chat_type")
    message_type = _event_string(root, message, payload, "message_type")
    text = _decode_content(root.get("content") if "content" in root else message.get("content"))
    mention_ids, mention_names = _extract_mentions(root, message, payload)
    return FeishuInboundEvent(
        text=text,
        message_id=message_id,
        root_id=root_id,
        parent_id=parent_id,
        thread_id=thread_id,
        upper_message_id=upper_message_id,
        chat_id=chat_id,
        sender_id=sender_id,
        chat_type=chat_type,
        message_type=message_type,
        mention_ids=mention_ids,
        mention_names=mention_names,
        raw=payload,
    )


def should_accept(
    event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, allow_any_chat: bool = False
) -> tuple[bool, str]:
    if not cfg.enabled:
        return False, "feishu bridge disabled"
    if not event.text:
        return False, "empty message"
    if any(event.text.startswith(prefix) for prefix in ACK_PREFIXES):
        return False, "bridge ack message"
    if event.sender_id and event.sender_id in cfg.ignored_sender_ids:
        return False, "ignored sender"
    if cfg.allowed_chat_ids:
        if event.chat_id not in cfg.allowed_chat_ids:
            return False, f"chat {event.chat_id or '(missing)'} not allowed"
    elif cfg.auto_bind_chat:
        if not event.chat_id:
            return False, "auto_bind_chat enabled but chat_id missing"
    elif not allow_any_chat:
        return False, "no allowed_chat_ids configured; pass --allow-any-chat for development"
    if cfg.allowed_sender_ids and event.sender_id not in cfg.allowed_sender_ids:
        return False, f"sender {event.sender_id or '(missing)'} not allowed"
    group_target = should_accept_group_target(event, cfg)
    if not group_target[0]:
        return group_target
    return True, "accepted"


def should_accept_group_target(event: FeishuInboundEvent, cfg: FeishuBridgeConfig) -> tuple[bool, str]:
    if event.chat_type != "group":
        return True, "accepted"
    if event.chat_id in cfg.group_message_routing_chat_ids:
        return True, "accepted"
    if cfg.group_message_routing == "all":
        return True, "accepted"
    if cfg.group_message_routing != "targeted":
        return True, "accepted"
    if not cfg.bot_open_id:
        return False, "group routing is targeted but bot_open_id is not configured"
    target_ids = bot_target_ids(cfg)
    if target_ids.intersection(event.mention_ids):
        return True, "accepted"
    if cfg.bot_name and cfg.bot_name in event.mention_names:
        return True, "accepted"
    if referenced_message_owned_by_this_bridge(event, cfg):
        return True, "accepted"
    return False, "group message not targeted to this bot"


def bot_target_ids(cfg: FeishuBridgeConfig) -> frozenset[str]:
    return frozenset(item for item in (cfg.bot_open_id, cfg.app_id) if item)


def referenced_message_owned_by_this_bridge(event: FeishuInboundEvent, cfg: FeishuBridgeConfig) -> bool:
    target = referenced_message_id(event)
    if not target:
        return False
    payload = _load_activity_state(activity_state_path(cfg))
    item = payload.get("messages", {}).get(target)
    return isinstance(item, dict) and bool(item.get("routed_to_self") or item.get("outgoing_from_self"))


def build_pilot_system_prompt(cfg: FeishuBridgeConfig) -> str:
    projects = _project_lines(cfg)
    project_block = "\n".join(projects) if projects else "(~/.cnb/projects.json 里还没有注册项目)"
    role = _resolve_role(cfg.pilot_role)
    if role is CHIEF_ROLE:
        feishu = feishu_command_prefix(cfg)
        return (
            f"你是 CNB 的{DEVICE_CHIEF_LABEL}，身份名是 {cfg.pilot_name}。\n"
            "你管所有机器的 roster、active/standby、leases、跨机器 handoff 和升级处理。"
            "你不是这台 Mac 的设备主管，也不是项目 board 里的项目同学；不要把单机 tmux/bridge 状态写成总管主状态。"
            "如果用户问“有多少正在运行的 cnb 实例/同学/人”，必须把机器总管、各机器设备主管、项目同学、"
            "bridge/tunnel/watch 基础设施分开列出。\n"
            "你可以协调哪台机器接手、释放或续租项目写入权，但不要直接替项目同学写代码；需要本机操作时，"
            "明确转给对应 device-supervisor 或进入对应项目后按该项目 board 规则执行。\n\n"
            f"总管启动目录: {cfg.project_root}\n"
            f"本机已注册项目:\n{project_block}\n\n"
            "飞书消息进入后会以 [Feishu inbound] 开头，并带有 message_id。Codex 的实时 TUI "
            "渲染不会同步到飞书；不要把终端画面当成飞书回复。接手后先判断这是跨机器协调、lease/handoff，"
            "还是单机/单项目请求。需要用户补充信息、确认选择或授权动作时，"
            f'可以执行 `{feishu} ask <message_id> "短问题"` 发一条不结束任务的短回复。'
            "处理完成、卡住或需要给出结论时，"
            f'必须在 shell 中执行 `{feishu} reply <message_id> "回复内容"` 把结果回到飞书。'
            "如果消息里带有 parent_message_id、root_message_id、thread_id 或 [Feishu referenced message]，"
            "说明用户是在飞书里回复/引用前文；处理时必须把这段上下文算进去。"
            "默认飞书通知策略是只推最终结果；不要为了实时状态连续发送飞书回复。"
            "不要要求用户记飞书命令；用户用自然语言要求状态、进度或终端画面时，"
            f"你要自己调用 `{feishu} activity`、`{feishu} tui` 或 `{feishu} watch`，"
            f"再用 `{feishu} reply` 回到飞书。"
            "飞书侧回读是默认关闭的排障能力；只有用户明确追问消息没发到、历史缺失或已读状态时，"
            "且配置已开启 readback_enabled=true，才运行 history 或 inspect-message；不要把它当成常规上下文读取。"
            "如果 [Feishu resources handed to Claude Code] 给出了本机文件路径或文档链接，"
            "这些就是用户在飞书里发来的图片、文件或链接上下文；需要时直接读取这些路径或链接，不要让用户重发。"
            "总管状态写入 ~/.cnb/device-chief/；单机状态写入对应机器的 device-supervisor；项目状态写入项目 .cnb/。"
        )
    return (
        f"你是这台 Mac 的{DEVICE_SUPERVISOR_LABEL}，身份名是 {cfg.pilot_name}。\n"
        "你自己就是一个正在值班的 cnb 同学/负责人实例，不是 bridge、tunnel 或旁路服务。"
        "如果用户问“有多少正在运行的 cnb 实例/同学/人”，必须把你自己算作 1 个正在运行的"
        f"{DEVICE_SUPERVISOR_LABEL}；后台 swarm 同学、项目同学、bridge/tunnel/watch 基础设施要分别列出。"
        "不要把自己归类为“基础 tmux 会话”后又说正在运行的同学为 0。\n"
        "用户会通过飞书把消息发给你。你需要读懂用户意图，必要时选择本机项目，"
        "再用 cnb/board/swarm 命令协调项目里的负责同学。\n\n"
        f"当前启动目录: {cfg.project_root}\n"
        f"本机已注册项目:\n{project_block}\n\n"
        "飞书消息进入后会以 [Feishu inbound] 开头，并带有 message_id。Codex 的实时 TUI "
        "渲染不会同步到飞书；不要把终端画面当成飞书回复。接手后先处理任务；需要用户补充信息、确认选择或授权动作时，"
        '可以执行 `cnb feishu ask <message_id> "短问题"` 发一条不结束任务的短回复。处理完成、卡住或需要给出结论时，'
        '必须在 shell 中执行 `cnb feishu reply <message_id> "回复内容"` 把结果回到飞书。'
        "如果消息里带有 parent_message_id、root_message_id、thread_id 或 [Feishu referenced message]，"
        "说明用户是在飞书里回复/引用前文；处理时必须把这段上下文算进去。"
        "默认飞书通知策略是只推最终结果；不要为了实时状态连续发送飞书回复。"
        "不要要求用户记飞书命令；用户用自然语言要求状态、进度或终端画面时，"
        "你要自己调用 `cnb feishu activity`、`cnb feishu tui` 或 `cnb feishu watch`，"
        "再用 `cnb feishu reply` 回到飞书。飞书默认状态只显示你当前 TUI 一屏；"
        "除非用户明确问实例、会话、进程、团队看板等排障信息，不要发送这些运行面列表。"
        "飞书侧回读是默认关闭的排障能力；只有用户明确追问消息没发到、历史缺失或已读状态时，"
        "且配置已开启 readback_enabled=true，才运行 `cnb feishu history` 或 "
        "`cnb feishu inspect-message <message_id>`。不要把它当成常规上下文读取。"
        "如果 [Feishu resources handed to Claude Code] 给出了本机文件路径或文档链接，"
        "这些就是用户在飞书里发来的图片、文件或链接上下文；需要时直接读取这些路径或链接，不要让用户重发。"
        "短请求只用于继续工作所需的最小用户输入，不要拿它刷进度；"
        "真正的进展、结论、风险和下一步仍然必须由你主动用 `cnb feishu reply` 汇报。"
    )


def get_current_prompt_hash(cfg: FeishuBridgeConfig) -> str:
    prompt = build_pilot_system_prompt(cfg)
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _prompt_hash_path(cfg: FeishuBridgeConfig) -> Path:
    return cfg.config_path.with_name("feishu_prompt_hash")


def get_stored_prompt_hash(cfg: FeishuBridgeConfig) -> str | None:
    path = _prompt_hash_path(cfg)
    if not path.exists():
        return None
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    return text if len(text) == 16 and all(c in "0123456789abcdef" for c in text) else None


def _save_prompt_hash(cfg: FeishuBridgeConfig, hash_value: str) -> None:
    path = _prompt_hash_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{hash_value}\n")


def describe_prompt_freshness(cfg: FeishuBridgeConfig) -> str:
    if not has_session(cfg.pilot_tmux):
        return "主管提示词: (主管未运行)"
    current = get_current_prompt_hash(cfg)
    stored = get_stored_prompt_hash(cfg)
    if stored is None:
        return f"主管提示词: 未知 (hash: {current}, 建议执行 cnb feishu restart-supervisor)"
    if stored == current:
        return f"主管提示词: 最新 (hash: {current})"
    return f"主管提示词: 过期! 当前hash: {current}, 运行中hash: {stored} (建议执行 cnb feishu restart-supervisor)"


def _project_lines(cfg: FeishuBridgeConfig, limit: int = 20) -> list[str]:
    lines: list[str] = []
    for project in discover_project_activity(cfg, limit=limit):
        lines.append(f"- {project['name']}: {project['path']}")
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
    _save_prompt_hash(cfg, get_current_prompt_hash(cfg))
    return BridgeResult(True, f"started {cfg.pilot_tmux}")


def format_for_pilot(
    event: FeishuInboundEvent,
    cfg: FeishuBridgeConfig | None = None,
    *,
    reference_summary: str = "",
    handoff_summary: str = "",
) -> str:
    parts = [
        "[Feishu inbound]",
        f"message_id: {event.message_id or '(unknown)'}",
        f"chat_id: {event.chat_id or '(unknown)'}",
        f"sender_id: {event.sender_id or '(unknown)'}",
    ]
    reference_lines = feishu_reference_lines(event)
    if reference_lines:
        parts.extend(reference_lines)
    if event.message_type:
        parts.append(f"message_type: {event.message_type}")
    if reference_summary:
        parts.extend(["", "[Feishu referenced message]", reference_summary])
    if handoff_summary:
        parts.extend(["", "[Feishu resources handed to Claude Code]", handoff_summary])
    if cfg is not None:
        parts.extend(["", "[CNB bridge affordances]", bridge_affordance_text(cfg)])
    parts.extend(["", event.text])
    return "\n".join(parts)


def feishu_reference_lines(event: FeishuInboundEvent) -> list[str]:
    lines: list[str] = []
    if event.parent_id:
        lines.append(f"parent_message_id: {event.parent_id}")
    if event.root_id:
        lines.append(f"root_message_id: {event.root_id}")
    if event.thread_id:
        lines.append(f"thread_id: {event.thread_id}")
    if event.upper_message_id:
        lines.append(f"upper_message_id: {event.upper_message_id}")
    return lines


def command_name(text: str) -> str:
    head = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    return head.lower()


def is_bridge_command(text: str) -> bool:
    name = command_name(text)
    return name in TUI_COMMANDS or name in WATCH_COMMANDS or name in HELP_COMMANDS or name in STATUS_COMMANDS


def route_event(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, dry_run: bool = False) -> BridgeResult:
    reference_summary = "" if dry_run else resolve_message_reference(event, cfg)
    handoff_summary = describe_event_resource_handoff(event, cfg, dry_run=dry_run)
    message = format_for_pilot(event, cfg, reference_summary=reference_summary, handoff_summary=handoff_summary)
    if dry_run:
        print(message)
        return BridgeResult(True, "dry-run")

    started = start_pilot_if_needed(cfg)
    if not started.handled:
        return started
    if not tmux_send(cfg.pilot_tmux, message):
        return BridgeResult(False, f"failed to send message to {cfg.pilot_tmux}")
    return BridgeResult(True, f"delivered to {cfg.pilot_tmux}")


def bind_chat_if_needed(event: FeishuInboundEvent, cfg: FeishuBridgeConfig) -> BridgeResult:
    if cfg.allowed_chat_ids or not cfg.auto_bind_chat:
        return BridgeResult(True, "chat already bound")
    if not event.chat_id:
        return BridgeResult(False, "cannot auto-bind Feishu chat: chat_id missing")

    data = _read_toml(cfg.config_path)
    section = dict(_feishu_section(data))
    section["chat_id"] = event.chat_id
    section["auto_bind_chat"] = False
    try:
        current = cfg.config_path.read_text() if cfg.config_path.exists() else ""
        cfg.config_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.config_path.write_text(_replace_toml_section(current, "feishu", _render_feishu_section(section)))
    except OSError as exc:
        return BridgeResult(False, f"failed to auto-bind Feishu chat {event.chat_id}: {exc}")
    return BridgeResult(True, f"auto-bound Feishu chat {event.chat_id}")


def activity_state_path(cfg: FeishuBridgeConfig) -> Path:
    return cfg.config_path.with_name("feishu_activity.json")


def _load_activity_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"messages": {}}
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"messages": {}}
    if not isinstance(payload, dict):
        return {"messages": {}}
    messages = payload.get("messages")
    if not isinstance(messages, dict):
        payload["messages"] = {}
    return payload


def _write_activity_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def record_activity_start(cfg: FeishuBridgeConfig, event: FeishuInboundEvent) -> None:
    if not event.message_id:
        return
    path = activity_state_path(cfg)
    payload = _load_activity_state(path)
    messages = payload.setdefault("messages", {})
    if not isinstance(messages, dict):
        messages = {}
        payload["messages"] = messages
    item = messages.get(event.message_id)
    if not isinstance(item, dict):
        item = {}
        messages[event.message_id] = item
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    item["chat_id"] = event.chat_id
    item["sender_id"] = event.sender_id
    item["routed_to_self"] = True
    item.setdefault("started_at", now)
    item["last_route_at"] = now
    item.setdefault("done_at", "")
    _write_activity_state(path, payload)


def record_outgoing_reply(cfg: FeishuBridgeConfig, source_message_id: str, reply_message_id: str) -> None:
    if not source_message_id or not reply_message_id:
        return
    path = activity_state_path(cfg)
    payload = _load_activity_state(path)
    messages = payload.setdefault("messages", {})
    if not isinstance(messages, dict):
        messages = {}
        payload["messages"] = messages

    source_item = messages.get(source_message_id)
    if not isinstance(source_item, dict):
        source_item = {}
        messages[source_message_id] = source_item
    reply_ids = source_item.setdefault("reply_message_ids", [])
    if not isinstance(reply_ids, list):
        reply_ids = []
        source_item["reply_message_ids"] = reply_ids
    if reply_message_id not in reply_ids:
        reply_ids.append(reply_message_id)

    item = messages.get(reply_message_id)
    if not isinstance(item, dict):
        item = {}
        messages[reply_message_id] = item
    item["outgoing_from_self"] = True
    item["source_message_id"] = source_message_id
    item["recorded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_activity_state(path, payload)


def mark_activity_done(cfg: FeishuBridgeConfig, message_id: str, *, reason: str = "") -> None:
    if not message_id:
        return
    path = activity_state_path(cfg)
    payload = _load_activity_state(path)
    messages = payload.setdefault("messages", {})
    if not isinstance(messages, dict):
        messages = {}
        payload["messages"] = messages
    item = messages.get(message_id)
    if not isinstance(item, dict):
        item = {}
        messages[message_id] = item
    item["done_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if reason:
        item["closed_reason"] = reason
    _write_activity_state(path, payload)


def mark_activity_blocked(cfg: FeishuBridgeConfig, message_id: str, *, reason: str) -> None:
    if not message_id:
        return
    path = activity_state_path(cfg)
    payload = _load_activity_state(path)
    messages = payload.setdefault("messages", {})
    if not isinstance(messages, dict):
        messages = {}
        payload["messages"] = messages
    item = messages.get(message_id)
    if not isinstance(item, dict):
        item = {}
        messages[message_id] = item
    item["blocked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    item["blocked_reason"] = reason
    _write_activity_state(path, payload)


def mark_activity_monitor_closed(cfg: FeishuBridgeConfig, message_id: str, *, reason: str) -> None:
    if not message_id:
        return
    path = activity_state_path(cfg)
    payload = _load_activity_state(path)
    messages = payload.setdefault("messages", {})
    if not isinstance(messages, dict):
        messages = {}
        payload["messages"] = messages
    item = messages.get(message_id)
    if not isinstance(item, dict):
        item = {}
        messages[message_id] = item
    item["activity_monitor_closed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    item["activity_monitor_closed_reason"] = reason
    _write_activity_state(path, payload)


def activity_is_done(cfg: FeishuBridgeConfig, message_id: str) -> bool:
    if not message_id:
        return True
    payload = _load_activity_state(activity_state_path(cfg))
    item = payload.get("messages", {}).get(message_id)
    return isinstance(item, dict) and bool(item.get("done_at"))


def activity_update_message_id(cfg: FeishuBridgeConfig, message_id: str) -> str:
    if not message_id:
        return ""
    payload = _load_activity_state(activity_state_path(cfg))
    item = payload.get("messages", {}).get(message_id)
    if not isinstance(item, dict):
        return ""
    value = item.get("activity_update_message_id")
    return value if isinstance(value, str) else ""


def record_activity_update_message(cfg: FeishuBridgeConfig, source_message_id: str, update_message_id: str) -> None:
    if not source_message_id or not update_message_id:
        return
    path = activity_state_path(cfg)
    payload = _load_activity_state(path)
    messages = payload.setdefault("messages", {})
    if not isinstance(messages, dict):
        messages = {}
        payload["messages"] = messages
    item = messages.get(source_message_id)
    if not isinstance(item, dict):
        item = {}
        messages[source_message_id] = item
    item["activity_update_message_id"] = update_message_id
    item["activity_update_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_activity_state(path, payload)


def describe_activity(cfg: FeishuBridgeConfig) -> str:
    return "\n".join(
        (
            f"- {role_label(cfg)}：{describe_pilot_activity(cfg)}",
            f"- {describe_prompt_freshness(cfg)}",
            f"- 飞书请求：{describe_request_activity(cfg)}",
            f"- CNB tmux 运行面：{describe_cnb_tmux_sessions(cfg)}",
            f"- 团队工作面：{describe_team_activity(cfg)}",
            f"- 用户前台 CLI：{describe_foreground_agent_sessions()}",
        )
    )


def describe_request_activity(cfg: FeishuBridgeConfig, *, now: float | None = None) -> str:
    open_items = open_activity_items(cfg, now=now)
    if not open_items:
        return "没有未完成请求。"

    threshold = activity_stale_seconds(cfg)
    stale = [item for item in open_items if item["age_seconds"] >= threshold]
    blocked = [item for item in open_items if item.get("blocked_at")]
    oldest = open_items[0]
    parts = [f"{len(open_items)} 个未完成", f"最久 {_format_duration(oldest['age_seconds'])}"]
    if blocked:
        reason = _truncate_inline(str(blocked[0].get("blocked_reason") or "需要人工处理"), 96)
        parts.append(f"{len(blocked)} 个阻塞：{reason}")
    if stale:
        parts.append(f"{len(stale)} 个超过 {_format_duration(threshold)}，需要检查{role_label(cfg)}是否卡住")
    return "；".join(parts) + "。"


def open_activity_items(cfg: FeishuBridgeConfig, *, now: float | None = None) -> list[dict[str, Any]]:
    now_value = time.time() if now is None else now
    payload = _load_activity_state(activity_state_path(cfg))
    messages = payload.get("messages")
    if not isinstance(messages, dict):
        return []

    items: list[dict[str, Any]] = []
    for message_id, item in messages.items():
        if not isinstance(item, dict) or item.get("done_at"):
            continue
        started_at = _parse_activity_timestamp(item.get("started_at"))
        if started_at is None:
            continue
        age = max(0, int(now_value - started_at))
        items.append(
            {
                "message_id": str(message_id),
                "chat_id": item.get("chat_id") or "",
                "sender_id": item.get("sender_id") or "",
                "started_at": item.get("started_at") or "",
                "age_seconds": age,
                "blocked_at": item.get("blocked_at") or "",
                "blocked_reason": item.get("blocked_reason") or "",
            }
        )
    return sorted(items, key=lambda item: item["age_seconds"], reverse=True)


def activity_stale_seconds(cfg: FeishuBridgeConfig) -> int:
    return max(60, cfg.activity_update_max_seconds or ACTIVITY_STALE_SECONDS)


def _parse_activity_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return time.mktime(time.strptime(value, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, rem = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{rem:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def build_activity_snapshot(cfg: FeishuBridgeConfig, elapsed_seconds: int = 0) -> ActivitySnapshot:
    style = resolve_activity_render_style(cfg)
    title = f"{elapsed_seconds}s" if elapsed_seconds > 0 else "活动"
    captured = capture_current_tui_screen(cfg)
    body = captured.detail.strip() if captured.handled else f"无法读取当前 TUI：{captured.detail}"
    body = _truncate_text(body or "(tmux pane has no visible content)", SNAPSHOT_MAX_CHARS)
    return ActivitySnapshot(
        title=title,
        subtitle="",
        sections=(ActivitySection("当前一屏", body, "screen"),),
        style=style,
        elapsed_seconds=elapsed_seconds,
        updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def resolve_activity_render_style(cfg: FeishuBridgeConfig) -> str:
    style = _activity_render_style(cfg.activity_render_style)
    if style != "auto":
        return style
    return "codex" if cfg.agent == "codex" else "claude"


def render_activity_snapshot_text(snapshot: ActivitySnapshot) -> str:
    if len(snapshot.sections) == 1 and snapshot.sections[0].tone == "screen":
        body = snapshot.sections[0].body.strip()
        return f"```text\n{body}\n```" if body else "```text\n\n```"
    return "\n".join(f"- {section.title}：{section.body}" for section in snapshot.sections)


def describe_pilot_activity(cfg: FeishuBridgeConfig) -> str:
    if not has_session(cfg.pilot_tmux):
        legacy_hint = f"；旧会话 {LEGACY_DEFAULT_PILOT_TMUX} 仍在运行" if has_session(LEGACY_DEFAULT_PILOT_TMUX) else ""
        return f"{cfg.pilot_tmux} 不在线，bridge 正在等待或尝试重新拉起{legacy_hint}。"
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", cfg.pilot_tmux, "-p", "-J", "-S", "-40"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{cfg.pilot_tmux} 在线，但暂时无法读取 TUI 状态：{exc}"
    if result.returncode != 0:
        detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
        return f"{cfg.pilot_tmux} 在线，但暂时无法读取 TUI 状态：{detail}"
    tail = "\n".join(result.stdout.splitlines()[-12:])
    if "bypass permissions" in tail or "approval" in tail.lower():
        return f"{cfg.pilot_tmux} 在线，但可能卡在权限确认或安全提示。"
    if ACTIVITY_WORK_RE.search(tail) or "Working" in tail or "Running" in tail:
        return f"{cfg.pilot_tmux} 正在思考或运行命令。"
    if ACTIVITY_PROMPT_RE.search(tail):
        return f"{cfg.pilot_tmux} 在线，可能正在整理回复或等待下一步输入。"
    return f"{cfg.pilot_tmux} 在线，正在处理；当前没有更细粒度的模型事件。"


def describe_team_activity(cfg: FeishuBridgeConfig, *, limit: int = 4) -> str:
    projects = discover_project_activity(cfg, limit=limit + 1)
    if not projects:
        return "没有发现可读的 cnb 项目看板。"
    lines = [_format_project_activity(project) for project in projects[:limit]]
    if len(projects) > limit:
        lines.append(f"另有 {len(projects) - limit} 个项目未展开")
    return "；".join(lines)


def describe_cnb_tmux_sessions(cfg: FeishuBridgeConfig) -> str:
    sessions = sorted(name for name in _tmux_session_names() if name.startswith("cnb-"))
    if not sessions:
        return "没有发现 cnb-* tmux 会话。"
    infra = sorted(name for name in sessions if name.startswith("cnb-feishu-"))
    device = [cfg.pilot_tmux] if cfg.pilot_tmux in sessions else []
    others = [name for name in sessions if name not in set(infra + device)]
    parts: list[str] = []
    if device:
        parts.append(role_label(cfg).replace("同学", "") + " " + ", ".join(device))
    if infra:
        parts.append("基础服务 " + ", ".join(infra))
    if others:
        parts.append("其他/遗留 " + ", ".join(others))
    return "；".join(parts)


def discover_project_activity(cfg: FeishuBridgeConfig, *, limit: int = 8) -> list[dict[str, Any]]:
    tmux_sessions = _tmux_session_names()
    projects: list[dict[str, Any]] = []
    for root in _candidate_project_roots(cfg):
        project = _inspect_project_activity(root, tmux_sessions)
        if project is not None:
            projects.append(project)
    projects.sort(
        key=lambda item: (
            item.get("path") != str(cfg.project_root),
            -int(item.get("running", 0)),
            -int(item.get("tasks_active", 0)),
            -int(item.get("unread", 0)),
            item.get("name", ""),
        )
    )
    return projects[:limit]


def _candidate_project_roots(cfg: FeishuBridgeConfig, *, max_candidates: int = 40) -> list[Path]:
    roots: list[Path] = []

    def add(path: Path) -> None:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            return
        if resolved in roots or not resolved.exists() or _is_transient_project_path(resolved):
            return
        if _project_config_dir(resolved) is None:
            return
        roots.append(resolved)

    add(cfg.project_root)
    try:
        from lib.global_registry import list_projects

        registry_projects = list_projects()
    except Exception:
        registry_projects = []
    for item in registry_projects:
        raw = item.get("path") if isinstance(item, dict) else ""
        if isinstance(raw, str) and raw:
            add(Path(raw))
        if len(roots) >= max_candidates:
            break
    return roots


def _is_transient_project_path(path: Path) -> bool:
    text = str(path)
    return "/pytest-of-" in text or ("/private/var/folders/" in text and "/pytest-" in text)


def _project_config_dir(project_root: Path) -> Path | None:
    for name in (".cnb", ".claudes"):
        config_dir = project_root / name
        if config_dir.is_dir():
            return config_dir
    return None


def _inspect_project_activity(project_root: Path, tmux_sessions: set[str]) -> dict[str, Any] | None:
    config_dir = _project_config_dir(project_root)
    if config_dir is None:
        return None
    config = _read_toml(config_dir / "config.toml")
    prefix = str(config.get("prefix") or "")
    configured_sessions = [str(item) for item in config.get("sessions", []) if isinstance(item, str)]
    board_db = config_dir / "board.db"
    board = _inspect_board_activity(board_db) if board_db.exists() else {}
    running_sessions = sorted(session for session in tmux_sessions if prefix and session.startswith(f"{prefix}-"))
    team_running = [session for session in running_sessions if not session.endswith("-dispatcher")]
    session_total = max(len(configured_sessions), int(board.get("sessions", 0) or 0), len(team_running))
    return {
        "name": project_root.name,
        "path": str(project_root),
        "prefix": prefix,
        "sessions": session_total,
        "running": len(team_running),
        "running_sessions": team_running[:6],
        "tasks_active": int(board.get("tasks_active", 0) or 0),
        "tasks_pending": int(board.get("tasks_pending", 0) or 0),
        "unread": int(board.get("unread", 0) or 0),
        "status_summary": board.get("status_summary", []),
        "latest_message": board.get("latest_message", ""),
    }


def _inspect_board_activity(board_db: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "sessions": 0,
        "tasks_active": 0,
        "tasks_pending": 0,
        "unread": 0,
        "status_summary": [],
        "latest_message": "",
    }
    try:
        conn = sqlite3.connect(str(board_db))
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return summary
    try:
        columns = _sqlite_table_columns(conn, "sessions")
        if columns:
            summary["sessions"] = _sqlite_count(conn, "sessions", "name NOT IN ('all', 'dispatcher')")
            if {"name", "status"} <= columns:
                rows = conn.execute(
                    "SELECT name, status FROM sessions WHERE name NOT IN ('all', 'dispatcher') ORDER BY name"
                ).fetchall()
                active = []
                for row in rows:
                    status = str(row["status"] or "").strip()
                    if status and not status.startswith("shutdown"):
                        active.append(f"{row['name']}:{_truncate_inline(status, 48)}")
                summary["status_summary"] = active[:4]

        task_columns = _sqlite_table_columns(conn, "tasks")
        if task_columns:
            summary["tasks_active"] = _sqlite_count(conn, "tasks", "status='active'")
            summary["tasks_pending"] = _sqlite_count(conn, "tasks", "status='pending'")

        inbox_columns = _sqlite_table_columns(conn, "inbox")
        if inbox_columns:
            if "read" in inbox_columns:
                summary["unread"] = _sqlite_count(conn, "inbox", "read=0")
            else:
                summary["unread"] = _sqlite_count(conn, "inbox")

        message_columns = _sqlite_table_columns(conn, "messages")
        if {"ts", "sender", "recipient", "body"} <= message_columns:
            row = conn.execute("SELECT ts, sender, recipient, body FROM messages ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                body = _truncate_inline(str(row["body"] or ""), 56)
                summary["latest_message"] = f"{row['sender']}->{row['recipient']}: {body}"
    except sqlite3.Error:
        return summary
    finally:
        conn.close()
    return summary


def _sqlite_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _sqlite_count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    try:
        suffix = f" WHERE {where}" if where else ""
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}{suffix}").fetchone()[0])
    except sqlite3.Error:
        return 0


def _format_project_activity(project: dict[str, Any]) -> str:
    name = project.get("name", "(unnamed)")
    sessions = int(project.get("sessions", 0) or 0)
    running = int(project.get("running", 0) or 0)
    tasks_active = int(project.get("tasks_active", 0) or 0)
    tasks_pending = int(project.get("tasks_pending", 0) or 0)
    unread = int(project.get("unread", 0) or 0)
    bits = [f"{name} {running}/{sessions} 个同学在线"]
    if tasks_active or tasks_pending:
        bits.append(f"任务 {tasks_active} active/{tasks_pending} pending")
    if unread:
        bits.append(f"未读 {unread}")
    statuses = project.get("status_summary") or []
    if statuses:
        bits.append("状态 " + "，".join(str(item) for item in statuses[:3]))
    elif project.get("latest_message"):
        bits.append("最近 " + str(project["latest_message"]))
    return "，".join(bits)


def describe_foreground_agent_sessions(*, limit: int = 6) -> str:
    sessions = foreground_agent_sessions(limit=limit)
    if not sessions:
        return "未发现用户前台操作的非 tmux Codex/Claude Code 会话。"
    lines = [_format_foreground_session(session) for session in sessions[:limit]]
    if len(sessions) > limit:
        lines.append(f"另有 {len(sessions) - limit} 个未展开")
    return "；".join(lines)


def foreground_agent_sessions(*, limit: int = 12) -> list[dict[str, str]]:
    rows = _process_rows()
    by_pid = {row["pid"]: row for row in rows}
    sessions: list[dict[str, str]] = []
    for row in rows:
        engine = _agent_engine(row)
        if not engine or _is_child_agent_process(row, by_pid) or _is_under_tmux(row, by_pid):
            continue
        tty = row.get("tty", "")
        if tty in {"", "?", "??"}:
            continue
        cwd = _extract_cd_path(row.get("args", "")) or _process_cwd(row["pid"])
        sessions.append(
            {
                "engine": engine,
                "pid": str(row["pid"]),
                "tty": tty,
                "cwd": cwd,
                "command": _short_agent_command(row.get("args", "")),
            }
        )
    return sessions[:limit]


def _process_rows() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,tty=,stat=,comm=,args="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 5)
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        rows.append({"pid": pid, "ppid": ppid, "tty": parts[2], "stat": parts[3], "comm": parts[4], "args": parts[5]})
    return rows


def _agent_engine(row: dict[str, Any]) -> str:
    comm = Path(str(row.get("comm", ""))).name.lower()
    args = str(row.get("args", ""))
    lowered = f"{comm} {args}".lower()
    if "codex computer use.app" in lowered:
        return ""
    if "rg -i" in lowered or "ps -axo" in lowered:
        return ""
    if "codex" in comm or re.search(r"(^|\s|/)codex(\s|$)", lowered):
        return "codex"
    if "claude" in comm or (AGENT_PROCESS_RE.search(lowered) and "codex" not in lowered):
        return "claude"
    return ""


def _is_child_agent_process(row: dict[str, Any], by_pid: dict[int, dict[str, Any]]) -> bool:
    engine = _agent_engine(row)
    parent = by_pid.get(int(row.get("ppid", 0)))
    return bool(engine and parent and _agent_engine(parent) == engine)


def _is_under_tmux(row: dict[str, Any], by_pid: dict[int, dict[str, Any]]) -> bool:
    ppid = int(row.get("ppid", 0))
    for _ in range(12):
        parent = by_pid.get(ppid)
        if not parent:
            return False
        comm = Path(str(parent.get("comm", ""))).name.lower()
        args = str(parent.get("args", "")).lower()
        if comm == "tmux" or args.startswith("tmux "):
            return True
        ppid = int(parent.get("ppid", 0))
    return False


def _extract_cd_path(args: str) -> str:
    try:
        parts = shlex.split(args)
    except ValueError:
        return ""
    for index, part in enumerate(parts[:-1]):
        if part == "--cd":
            return parts[index + 1]
    return ""


def _process_cwd(pid: int) -> str:
    if not shutil.which("lsof"):
        return ""
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def _short_agent_command(args: str) -> str:
    text = " ".join(args.split())
    if " resume " in f" {text} ":
        return "resume"
    if " --cd " in f" {text} ":
        return "--cd"
    return _truncate_inline(text, 64)


def _format_foreground_session(session: dict[str, str]) -> str:
    cwd = session.get("cwd", "")
    cwd_bit = f" cwd={cwd}" if cwd else ""
    command = session.get("command", "")
    command_bit = f" {command}" if command else ""
    return f"{session.get('engine')} pid={session.get('pid')} tty={session.get('tty')}{cwd_bit}{command_bit}"


def referenced_message_id(event: FeishuInboundEvent) -> str:
    for candidate in (event.parent_id, event.root_id, event.upper_message_id):
        if candidate and candidate != event.message_id:
            return candidate
    return ""


def resolve_message_reference(event: FeishuInboundEvent, cfg: FeishuBridgeConfig) -> str:
    target = referenced_message_id(event)
    if not target or cfg.transport != "local_openapi":
        return ""
    result = get_message_openapi(cfg, target)
    if not result.handled:
        return f"{target}（无法读取引用内容：{result.detail}）"
    summary = summarize_openapi_message(result.detail)
    return summary or f"{target}（引用消息内容为空或暂不支持展示）"


def get_message_openapi(cfg: FeishuBridgeConfig, message_id: str) -> BridgeResult:
    if not message_id:
        return BridgeResult(False, "message_id missing")
    token = tenant_access_token(cfg)
    if not token.handled:
        return token
    return openapi_get(
        f"/open-apis/im/v1/messages/{message_id}",
        headers={"Authorization": f"Bearer {token.detail}"},
        params={"user_id_type": "open_id", "card_msg_content_type": "user_card_content"},
    )


def readback_guard(cfg: FeishuBridgeConfig) -> BridgeResult:
    if not cfg.readback_enabled:
        return BridgeResult(
            False,
            "飞书回读未启用；如需按需排障，在 [feishu] 设置 readback_enabled = true 后重试。",
        )
    if cfg.transport != "local_openapi":
        return BridgeResult(False, "飞书回读只支持 local_openapi transport")
    return BridgeResult(True, "readback enabled")


def resolve_readback_chat_id(cfg: FeishuBridgeConfig, requested_chat_id: str = "") -> BridgeResult:
    chat_id = requested_chat_id.strip()
    if chat_id:
        if chat_id in cfg.allowed_chat_ids or cfg.readback_allow_unlisted_chat:
            return BridgeResult(True, chat_id)
        return BridgeResult(False, f"chat {chat_id} 不在回读 allowlist；不要读取未授权飞书会话")
    if len(cfg.allowed_chat_ids) == 1:
        return BridgeResult(True, next(iter(cfg.allowed_chat_ids)))
    if len(cfg.allowed_chat_ids) > 1:
        return BridgeResult(False, "配置了多个允许 chat；请显式传 --chat-id")
    return BridgeResult(False, "没有配置允许回读的 chat_id")


def fetch_chat_history_openapi(cfg: FeishuBridgeConfig, chat_id: str, *, limit: int = 0) -> BridgeResult:
    guard = readback_guard(cfg)
    if not guard.handled:
        return guard
    resolved = resolve_readback_chat_id(cfg, chat_id)
    if not resolved.handled:
        return resolved
    token = tenant_access_token(cfg)
    if not token.handled:
        return token
    page_size = str(_readback_limit(cfg, limit))
    return openapi_get(
        "/open-apis/im/v1/messages",
        headers={"Authorization": f"Bearer {token.detail}"},
        params={
            "container_id_type": "chat",
            "container_id": resolved.detail,
            "sort_type": "ByCreateTimeDesc",
            "page_size": page_size,
            "card_msg_content_type": "user_card_content",
        },
    )


def build_history_readback(cfg: FeishuBridgeConfig, *, chat_id: str = "", limit: int = 0) -> BridgeResult:
    guard = readback_guard(cfg)
    if not guard.handled:
        return guard
    resolved = resolve_readback_chat_id(cfg, chat_id)
    if not resolved.handled:
        return resolved
    result = fetch_chat_history_openapi(cfg, resolved.detail, limit=limit)
    if not result.handled:
        return result
    return BridgeResult(
        True, render_feishu_history_response(result.detail, resolved.detail, limit=_readback_limit(cfg, limit))
    )


def inspect_message_readback(
    cfg: FeishuBridgeConfig,
    message_id: str,
    *,
    include_read_users: bool = True,
    read_user_limit: int = 20,
) -> BridgeResult:
    guard = readback_guard(cfg)
    if not guard.handled:
        return guard
    message = get_message_openapi(cfg, message_id)
    if not message.handled:
        return message
    lines = render_feishu_message_inspection(message.detail, cfg)
    for item in _openapi_message_items(message.detail):
        handoff = describe_message_resource_handoff(
            cfg,
            str(item.get("message_id") or message_id),
            str(item.get("msg_type") or item.get("message_type") or ""),
            item_content_object(item),
        )
        if handoff:
            lines.extend(["资源/链接交接：", handoff])
    if include_read_users:
        items = _openapi_message_items(message.detail)
        if any(_message_sent_by_current_bot(item, cfg) for item in items):
            read_users = get_message_read_users_openapi(cfg, message_id, limit=read_user_limit)
            if read_users.handled:
                lines.append(render_feishu_read_users_response(read_users.detail))
            else:
                lines.append(f"已读状态不可用：{read_users.detail}")
        else:
            lines.append("已读状态：跳过（飞书只允许当前机器人查询自己发送消息的已读状态）")
    return BridgeResult(True, "\n".join(lines))


def get_message_read_users_openapi(cfg: FeishuBridgeConfig, message_id: str, *, limit: int = 20) -> BridgeResult:
    if not message_id:
        return BridgeResult(False, "message_id missing")
    token = tenant_access_token(cfg)
    if not token.handled:
        return token
    page_size = str(max(1, min(100, limit)))
    return openapi_get(
        f"/open-apis/im/v1/messages/{message_id}/read_users",
        headers={"Authorization": f"Bearer {token.detail}"},
        params={"user_id_type": "open_id", "page_size": page_size},
    )


def describe_event_resource_handoff(
    event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, dry_run: bool = False
) -> str:
    content = event_content_object(event)
    return describe_message_resource_handoff(
        cfg,
        event.message_id,
        event.message_type,
        content,
        dry_run=dry_run,
    )


def describe_message_resource_handoff(
    cfg: FeishuBridgeConfig,
    message_id: str,
    msg_type: str,
    content: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    resources, links, notes = collect_message_resources_and_links(msg_type, content)
    lines: list[str] = []
    if resources:
        if not cfg.resource_handoff_enabled:
            lines.append("资源交接已关闭：配置 resource_handoff_enabled=false。")
        elif not message_id:
            lines.append("资源交接跳过：message_id 缺失，无法调用飞书消息资源下载接口。")
        elif cfg.transport != "local_openapi":
            lines.append("资源交接跳过：只支持 local_openapi transport。")
        else:
            for resource in resources:
                if dry_run:
                    lines.append(_format_resource_reference(resource, path="(dry-run 未下载)"))
                    continue
                downloaded = download_message_resource_openapi(cfg, message_id, resource)
                if downloaded.handled:
                    lines.append(
                        _format_resource_reference(
                            resource,
                            path=downloaded.path,
                            content_type=downloaded.content_type,
                            size=downloaded.size,
                        )
                    )
                else:
                    lines.append(f"- {resource['kind']} {resource['key']}：下载失败：{downloaded.detail}")
    if links:
        lines.append("链接：")
        for link in links[:12]:
            lines.append(f"- {link}")
        if len(links) > 12:
            lines.append(f"- 另有 {len(links) - 12} 个链接未展开")
    if notes:
        lines.append("未自动交接：")
        for note in notes[:8]:
            lines.append(f"- {note}")
    return "\n".join(lines)


def event_content_object(event: FeishuInboundEvent) -> dict[str, Any]:
    root = event.raw.get("event") if isinstance(event.raw.get("event"), dict) else event.raw
    message_value = root.get("message") if isinstance(root, dict) else None
    message = message_value if isinstance(message_value, dict) else {}
    content = root.get("content") if isinstance(root, dict) and "content" in root else message.get("content")
    parsed = _parse_json_object(content)
    return parsed or {}


def item_content_object(item: dict[str, Any]) -> dict[str, Any]:
    body = item.get("body")
    content = body.get("content") if isinstance(body, dict) else item.get("content")
    return _parse_json_object(content) or {}


def collect_message_resources_and_links(
    msg_type: str, content: dict[str, Any]
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    resources: list[dict[str, str]] = []
    links: list[str] = []
    notes: list[str] = []

    def add_resource(kind: str, key: Any, file_name: Any = "", source: str = "") -> None:
        value = str(key or "").strip()
        if not value:
            return
        resource = {
            "kind": kind,
            "key": value,
            "file_name": str(file_name or "").strip(),
            "source": source,
        }
        if resource not in resources:
            resources.append(resource)

    def add_link(value: Any) -> None:
        url = str(value or "").strip()
        if url and url not in links:
            links.append(url)

    if msg_type == "image" or "image_key" in content:
        add_resource("image", content.get("image_key"), source=msg_type or "image")
    if msg_type in {"file", "audio", "media"} or ("file_key" in content and msg_type != "folder"):
        add_resource("file", content.get("file_key"), content.get("file_name"), source=msg_type or "file")
    if msg_type == "folder":
        notes.append(
            f"folder {content.get('file_name') or content.get('file_key') or '(unnamed)'}：飞书 API 不支持按 key 下载文件夹"
        )

    text = str(content.get("text") or "")
    for link in extract_links(text):
        add_link(link)

    post_content = content.get("content")
    if isinstance(post_content, list):
        for row in post_content:
            elements = row if isinstance(row, list) else [row]
            for element in elements:
                if not isinstance(element, dict):
                    continue
                tag = str(element.get("tag") or "")
                if tag == "img":
                    add_resource("image", element.get("image_key"), source="post.img")
                elif tag == "media":
                    add_resource("file", element.get("file_key"), element.get("file_name"), source="post.media")
                    add_resource("image", element.get("image_key"), source="post.media.cover")
                elif tag == "a":
                    add_link(element.get("href"))
                elif tag == "emotion":
                    notes.append(f"emotion {element.get('emoji_type') or ''}".strip())
                for key in ("text", "href", "url"):
                    for link in extract_links(str(element.get(key) or "")):
                        add_link(link)

    for link in extract_links(json.dumps(content, ensure_ascii=False)):
        add_link(link)
    return resources, links, notes


def extract_links(text: str) -> list[str]:
    links: list[str] = []
    for _label, url in re.findall(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)", text):
        if url not in links:
            links.append(url)
    for url in re.findall(r"https?://[^\s)>\]\"']+", text):
        cleaned = url.rstrip(".,;，。；")
        if cleaned and cleaned not in links:
            links.append(cleaned)
    return links


def download_message_resource_openapi(
    cfg: FeishuBridgeConfig, message_id: str, resource: dict[str, str]
) -> ResourceDownloadResult:
    token = tenant_access_token(cfg)
    if not token.handled:
        return ResourceDownloadResult(False, token.detail)
    key = resource.get("key", "")
    kind = resource.get("kind", "")
    if kind not in {"image", "file"}:
        return ResourceDownloadResult(False, f"unsupported resource kind: {kind}")
    message_dir = resource_handoff_dir(cfg) / _safe_path_part(message_id)
    suggested_name = resource.get("file_name") or key
    return openapi_download(
        f"/open-apis/im/v1/messages/{message_id}/resources/{key}",
        params={"type": kind},
        headers={"Authorization": f"Bearer {token.detail}"},
        output_dir=message_dir,
        suggested_name=suggested_name,
        max_bytes=cfg.resource_handoff_max_bytes,
    )


def resource_handoff_dir(cfg: FeishuBridgeConfig) -> Path:
    return cfg.config_path.with_name("feishu_resources")


def openapi_download(
    path: str,
    *,
    params: dict[str, str],
    headers: dict[str, str],
    output_dir: Path,
    suggested_name: str,
    max_bytes: int,
) -> ResourceDownloadResult:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    request = urllib.request.Request(
        f"https://open.feishu.cn{path}{query}",
        headers={"Content-Type": "application/json; charset=utf-8", **headers},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_length = _int(response.headers.get("Content-Length"), 0)
            if content_length > max_bytes:
                return ResourceDownloadResult(False, f"资源超过本地交接上限 {max_bytes} bytes")
            content_type = str(response.headers.get("Content-Type") or "application/octet-stream")
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        return ResourceDownloadResult(False, f"Feishu OpenAPI HTTP {exc.code}: {_snippet(detail)}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ResourceDownloadResult(False, f"Feishu OpenAPI failed: {exc}")
    if len(data) > max_bytes:
        return ResourceDownloadResult(False, f"资源超过本地交接上限 {max_bytes} bytes")
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(suggested_name) or "resource"
    filename = _filename_with_extension(filename, content_type)
    target = _unique_path(output_dir / filename)
    try:
        target.write_bytes(data)
    except OSError as exc:
        return ResourceDownloadResult(False, f"写入本地资源失败：{exc}")
    return ResourceDownloadResult(True, "downloaded", str(target), content_type, len(data))


def _format_resource_reference(
    resource: dict[str, str],
    *,
    path: str,
    content_type: str = "",
    size: int = 0,
) -> str:
    bits = [resource.get("kind", "resource"), resource.get("source", ""), resource.get("file_name", "")]
    label = " ".join(bit for bit in bits if bit).strip()
    meta = []
    if content_type:
        meta.append(content_type)
    if size:
        meta.append(f"{size} bytes")
    suffix = f" ({', '.join(meta)})" if meta else ""
    return f"- {label or resource.get('key')} -> {path}{suffix}"


def _safe_path_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:80] or "unknown"


def _safe_filename(value: str) -> str:
    name = Path(value).name.strip()
    name = re.sub(r"[\x00-\x1f/\\\\:]+", "-", name).strip(". ")
    return name[:120] or "resource"


def _filename_with_extension(filename: str, content_type: str) -> str:
    if Path(filename).suffix:
        return filename
    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "application/zip": ".zip",
    }.get(content_type.split(";", 1)[0].lower(), "")
    return filename + ext


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem}-{int(time.time())}{suffix}")


def _readback_limit(cfg: FeishuBridgeConfig, requested: int = 0) -> int:
    base = requested if requested > 0 else cfg.readback_default_limit
    return max(1, min(cfg.readback_max_limit, base, MAX_READBACK_LIMIT))


def render_feishu_history_response(text: str, chat_id: str, *, limit: int) -> str:
    items = _openapi_message_items(text)
    lines = [f"飞书回读：chat {chat_id} 最近 {min(len(items), limit)} 条（新到旧）"]
    if not items:
        lines.append("(未返回历史消息)")
        return "\n".join(lines)
    for item in items[:limit]:
        lines.append(f"- {format_feishu_message_item(item, content_limit=240)}")
    if _openapi_has_more(text):
        lines.append("还有更多历史消息；需要时用更大的 --limit 或继续分页能力扩展。")
    return "\n".join(lines)


def render_feishu_message_inspection(text: str, cfg: FeishuBridgeConfig) -> list[str]:
    items = _openapi_message_items(text)
    lines = ["飞书消息检查："]
    if not items:
        lines.append("- 未返回消息内容。")
        return lines
    for item in items:
        lines.append(f"- {format_feishu_message_item(item, content_limit=500)}")
        for key in ("chat_id", "root_id", "parent_id", "thread_id", "upper_message_id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                lines.append(f"  {key}: {value}")
        if _message_sent_by_current_bot(item, cfg):
            lines.append("  发送者：当前机器人")
    return lines


def render_feishu_read_users_response(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return "已读状态：飞书返回非 JSON"
    data = payload.get("data")
    if not isinstance(data, dict):
        return "已读状态：飞书返回缺少 data"
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return "已读状态：未返回已读用户；飞书只返回已读者，不返回未读者。"
    parts: list[str] = []
    for item in items[:10]:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("user_id") or "")
        timestamp = _format_feishu_timestamp(item.get("timestamp"))
        parts.append(f"{user_id} {timestamp}".strip())
    suffix = f"；另有 {len(items) - 10} 个未展开" if len(items) > 10 else ""
    return f"已读状态：{len(items)} 个已读用户；" + "，".join(parts) + suffix


def _openapi_message_items(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _openapi_has_more(text: str) -> bool:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    data = payload.get("data")
    return bool(data.get("has_more")) if isinstance(data, dict) else False


def _message_sent_by_current_bot(item: dict[str, Any], cfg: FeishuBridgeConfig) -> bool:
    sender = item.get("sender")
    if not isinstance(sender, dict):
        return False
    sender_type = str(sender.get("sender_type") or sender.get("type") or "")
    sender_id = _id_value(sender.get("id")) or _id_value(sender.get("sender_id")) or str(sender.get("id") or "")
    return sender_type == "app" and bool(sender_id) and sender_id == cfg.app_id


def format_feishu_message_item(item: dict[str, Any], *, content_limit: int) -> str:
    created = _format_feishu_timestamp(item.get("create_time"))
    deleted = " deleted" if item.get("deleted") is True else ""
    summary = summarize_feishu_message_item(item, content_limit=content_limit)
    return " ".join(bit for bit in (created, summary + deleted) if bit)


def _format_feishu_timestamp(value: Any) -> str:
    try:
        raw = int(str(value))
    except (TypeError, ValueError):
        return ""
    seconds = raw / 1000 if raw > 10_000_000_000 else raw
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))


def summarize_openapi_message(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return ""
    item = items[0]
    return summarize_feishu_message_item(item if isinstance(item, dict) else {})


def summarize_feishu_message_item(item: dict[str, Any], *, content_limit: int = 600) -> str:
    message_id = str(item.get("message_id") or "")
    msg_type = str(item.get("msg_type") or item.get("message_type") or "")
    sender = item.get("sender")
    sender_label = _sender_label(sender if isinstance(sender, dict) else {})
    body = item.get("body")
    body_content = body.get("content") if isinstance(body, dict) else item.get("content")
    content = _decode_reference_content(body_content, msg_type)
    bits = [bit for bit in (message_id, sender_label, msg_type) if bit]
    prefix = " ".join(bits)
    if content and not prefix:
        return _truncate_inline(content, content_limit)
    return f"{prefix}: {_truncate_inline(content, content_limit)}" if content else prefix


def _sender_label(sender: dict[str, Any]) -> str:
    sender_type = str(sender.get("sender_type") or sender.get("type") or "")
    sender_id = _id_value(sender.get("id")) or _id_value(sender.get("sender_id")) or str(sender.get("id") or "")
    if sender_type and sender_id:
        return f"{sender_type}:{sender_id}"
    return sender_type or sender_id


def _decode_reference_content(content: Any, msg_type: str = "") -> str:
    parsed = _parse_json_object(content)
    if isinstance(parsed, dict):
        if msg_type == "interactive" or parsed.get("schema") or parsed.get("header"):
            return _summarize_card_content(parsed)
        decoded = _decode_content(parsed)
        if decoded:
            return decoded
    return _decode_content(content)


def _parse_json_object(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _summarize_card_content(card: dict[str, Any]) -> str:
    parts: list[str] = []
    header = card.get("header")
    if isinstance(header, dict):
        title = header.get("title")
        if isinstance(title, dict):
            value = title.get("content")
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    body = card.get("body")
    elements = body.get("elements") if isinstance(body, dict) else card.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue
            value = element.get("content")
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                continue
            text = element.get("text")
            if isinstance(text, dict):
                value = text.get("content")
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
            if len(parts) >= 3:
                break
    return " / ".join(_truncate_inline(part, 160) for part in parts) or "interactive card"


def build_activity_card(snapshot: ActivitySnapshot) -> dict[str, Any]:
    if snapshot.style == "claude":
        return build_claude_activity_card(snapshot)
    return build_codex_activity_card(snapshot)


def build_codex_activity_card(snapshot: ActivitySnapshot) -> dict[str, Any]:
    return _build_activity_card(snapshot, template="blue", accent="Codex run-loop snapshot")


def build_claude_activity_card(snapshot: ActivitySnapshot) -> dict[str, Any]:
    return _build_activity_card(snapshot, template="purple", accent="Claude-style activity snapshot")


def _build_activity_card(snapshot: ActivitySnapshot, *, template: str, accent: str) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    screen_mode = len(snapshot.sections) == 1 and snapshot.sections[0].tone == "screen"
    if snapshot.subtitle and not screen_mode:
        elements.append(
            {
                "tag": "markdown",
                "content": f"**{_card_escape(accent)}**\n{_card_escape(snapshot.subtitle)}",
                "text_align": "left",
                "text_size": "normal_v2",
            }
        )
    for section in snapshot.sections:
        elements.append(
            {
                "tag": "markdown",
                "content": _activity_card_section_markdown(section),
                "text_align": "left",
                "text_size": "normal_v2",
            }
        )
    if not screen_mode:
        elements.append(
            {
                "tag": "markdown",
                "content": _card_escape(f"更新于 {snapshot.updated_at}；后续自动状态会更新这张卡片。"),
                "text_align": "left",
                "text_size": "normal_v2",
            }
        )
    return {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "style": {"text_size": {"normal_v2": {"default": "normal", "pc": "normal", "mobile": "heading"}}},
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 12px 12px",
            "elements": elements,
        },
        "header": {
            "title": {"tag": "plain_text", "content": _normalize_activity_title(snapshot.title)},
            "subtitle": {"tag": "plain_text", "content": ""},
            "template": template,
            "padding": "12px 12px 12px 12px",
        },
    }


def _normalize_activity_title(title: str) -> str:
    cleaned = str(title or "").strip()
    cleaned = re.sub(r"^(?:Codex|Claude Code)\s+", "", cleaned)
    if "·" in cleaned:
        cleaned = cleaned.split("·", 1)[-1].strip()
    return cleaned or "实时一屏"


def _card_escape(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _activity_card_section_markdown(section: ActivitySection) -> str:
    if section.tone == "screen":
        return _activity_card_screen_markdown(section)
    lines = _split_activity_card_lines(section.body)
    if len(lines) <= 1:
        body = _card_escape(lines[0] if lines else section.body)
        return f"**{_card_escape(section.title)}**\n{body}"
    bullets = "\n".join(f"- {_card_escape(line)}" for line in lines)
    return f"**{_card_escape(section.title)}**\n{bullets}"


def _split_activity_card_lines(body: str) -> list[str]:
    lines = [part.strip() for part in re.split(r"[；\n]+", body) if part.strip()]
    if not lines:
        return [body.strip()] if body.strip() else []
    return [_truncate_inline(line, ACTIVITY_CARD_LINE_MAX_CHARS) for line in lines]


def _activity_card_screen_markdown(section: ActivitySection) -> str:
    lines, _omitted = _activity_card_screen_lines(section.body)
    if not lines:
        return "(当前 TUI 没有可见内容)"
    rendered: list[str] = []
    for line in lines:
        rendered.append(_render_activity_line(line))
    return "\n".join(rendered)


def _activity_card_screen_lines(body: str) -> tuple[list[str], int]:
    lines = [ANSI_ESCAPE_RE.sub("", line.expandtabs(2)).rstrip() for line in body.splitlines()]
    noise_blob = "\n".join(
        part
        for part in (
            bridge_affordance_text(),
            command_help_text(),
        )
        if part
    )
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_noise_screen_line(stripped, noise_blob):
            continue
        filtered.append(line)
    lines = filtered
    omitted = max(0, len(lines) - ACTIVITY_CARD_SCREEN_MAX_LINES)
    tail = lines[-ACTIVITY_CARD_SCREEN_MAX_LINES:]
    return [_truncate_terminal_line(line, ACTIVITY_CARD_SCREEN_LINE_MAX_CHARS) for line in tail], omitted


def _truncate_terminal_line(line: str, limit: int) -> str:
    if len(line) <= limit:
        return line
    return line[: max(0, limit - 1)] + "…"


def _card_escape_terminal_line(text: str) -> str:
    escaped = _card_escape(text).replace("\\", "\\\\")
    for char in ("`", "*", "_", "[", "]", "|", "~"):
        escaped = escaped.replace(char, f"\\{char}")
    return escaped or " "


def _render_activity_line(text: str) -> str:
    stripped = text.strip()
    escaped = _card_escape_terminal_line(stripped)
    lower = stripped.lower()
    if "http 400" in lower or "invalid ids" in lower or "traceback" in lower or "error" in lower:
        return f"<font color='red'><b>{escaped}</b></font>"
    if stripped.startswith(
        ("回复 ", "• ", "◦ ", "● ", "› ", "> ", "Working", "Run ", "gpt-", "当前一屏", "实时一屏", "更新于")
    ):
        return f"<font color='grey'>{escaped}</font>"
    return f"<b>{escaped}</b>" if escaped.strip() else escaped


def _is_noise_screen_line(line: str, noise_blob: str) -> bool:
    if not line:
        return False
    if line.startswith(
        (
            "实时一屏",
            "当前一屏",
            "更新于",
            "回复 ",
            "cnb_Macbook_",
            "cnb_Macbook_主管同学",
            "cnb_Macbook_主管同学机器人",
        )
    ):
        return True
    if line.startswith(
        (
            "• ",
            "◦ ",
            "● ",
            "› ",
            "> ",
            "Working",
            "Run ",
            "gpt-",
            "background terminal running",
            "/ps to view",
            "esc to interrupt",
        )
    ):
        return True
    if line in {"Codex screen", "Claude Code screen"}:
        return True
    if line in noise_blob:
        return True
    return len(line) >= 12 and noise_blob.find(line) >= 0


def send_activity_update(cfg: FeishuBridgeConfig, event: FeishuInboundEvent, elapsed_seconds: int) -> BridgeResult:
    if activity_is_done(cfg, event.message_id):
        return BridgeResult(False, "activity already done")
    snapshot = build_activity_snapshot(cfg, elapsed_seconds)
    return send_activity_card(cfg, event, snapshot)


def should_send_ack(cfg: FeishuBridgeConfig) -> bool:
    return cfg.ack and cfg.notification_policy in {"ack", "live"}


def should_start_activity_monitor(cfg: FeishuBridgeConfig) -> bool:
    return cfg.activity_updates and cfg.notification_policy == "live"


def describe_notification_policy(cfg: FeishuBridgeConfig) -> str:
    if cfg.notification_policy == "final_only":
        return "final_only（普通请求只路由；仅最终 cnb feishu reply 推送）"
    if cfg.notification_policy == "ack":
        return "ack（收到后推送一次 ack；实时状态不推送）"
    return "live（ack + 活动卡更新；适合临时排障）"


def send_activity_card(cfg: FeishuBridgeConfig, event: FeishuInboundEvent, snapshot: ActivitySnapshot) -> BridgeResult:
    existing_message_id = activity_update_message_id(cfg, event.message_id)
    if cfg.transport == "local_openapi":
        card = build_activity_card(snapshot)
        if existing_message_id:
            updated = update_message_card_openapi(cfg, existing_message_id, card)
            if updated.handled:
                return BridgeResult(True, "activity card updated")
        sent = send_reply_card_openapi(
            cfg,
            event.message_id,
            card,
            idempotency_key=f"cnb-feishu-activity-{_message_digest(event.message_id)}-{snapshot.elapsed_seconds}",
        )
        if not sent.handled:
            return sent
        update_message_id = _message_id_from_openapi_response(sent.detail)
        if update_message_id:
            record_activity_update_message(cfg, event.message_id, update_message_id)
        return BridgeResult(True, "activity card sent")

    text = f"状态更新（约 {snapshot.elapsed_seconds}s）：\n{render_activity_snapshot_text(snapshot)}"
    return send_reply(
        cfg,
        event.message_id,
        text,
        idempotency_key=f"cnb-feishu-activity-{_message_digest(event.message_id)}-{snapshot.elapsed_seconds}",
    )


def start_activity_monitor(event: FeishuInboundEvent, cfg: FeishuBridgeConfig) -> BridgeResult:
    if not should_start_activity_monitor(cfg):
        return BridgeResult(False, f"activity updates disabled by {cfg.notification_policy} policy")
    if not event.message_id:
        return BridgeResult(False, "message_id missing")
    record_activity_start(cfg, event)
    thread = threading.Thread(target=_activity_monitor_loop, args=(event, cfg), daemon=True)
    thread.start()
    return BridgeResult(True, "activity monitor started")


def _activity_monitor_loop(event: FeishuInboundEvent, cfg: FeishuBridgeConfig) -> None:
    started = time.monotonic()
    for elapsed in iter_activity_update_elapsed_seconds(cfg):
        delay = started + elapsed - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        if activity_is_done(cfg, event.message_id):
            return
        result = send_activity_update(cfg, event, elapsed)
        print(f"[cnb-feishu-activity] {event.message_id} {elapsed}s: {result.detail}", file=sys.stderr)
    if not activity_is_done(cfg, event.message_id):
        max_seconds = cfg.activity_update_max_seconds or 0
        reason = (
            f"activity monitor reached {max_seconds}s limit" if max_seconds else "activity monitor schedule exhausted"
        )
        mark_activity_monitor_closed(cfg, event.message_id, reason=reason)
        mark_activity_blocked(cfg, event.message_id, reason=f"final Feishu reply not confirmed: {reason}")


def iter_activity_update_elapsed_seconds(cfg: FeishuBridgeConfig):
    fixed = sorted(set(cfg.activity_update_seconds))
    max_elapsed = max(0, cfg.activity_update_max_seconds)
    for elapsed in fixed:
        if max_elapsed and elapsed > max_elapsed:
            return
        yield elapsed
    repeat = max(0, cfg.activity_update_repeat_seconds)
    if repeat <= 0:
        return
    elapsed = fixed[-1] if fixed else 0
    while True:
        elapsed += repeat
        if max_elapsed and elapsed > max_elapsed:
            return
        yield elapsed


def reply_ack(event: FeishuInboundEvent, cfg: FeishuBridgeConfig, detail: str) -> BridgeResult:
    if not should_send_ack(cfg):
        return BridgeResult(False, f"ack disabled by {cfg.notification_policy} policy")
    if not event.message_id:
        return BridgeResult(False, "message_id missing")
    text = f"{ack_prefix(cfg)}。{detail}"
    return send_reply(cfg, event.message_id, text, idempotency_key=_ack_key(event.message_id))


def send_reply(cfg: FeishuBridgeConfig, message_id: str, text: str, *, idempotency_key: str = "") -> BridgeResult:
    if not message_id:
        return BridgeResult(False, "message_id missing")
    text = normalize_reply_text(text).strip()
    if not text:
        return BridgeResult(False, "reply text is empty")
    if cfg.transport == "local_openapi":
        return send_reply_openapi(cfg, message_id, text, idempotency_key=idempotency_key)
    if cfg.transport == "hermes_lark_cli":
        return send_reply_hermes_lark_cli(cfg, message_id, text, idempotency_key=idempotency_key)
    return BridgeResult(False, f"unsupported Feishu transport: {cfg.transport}")


def send_short_reply(cfg: FeishuBridgeConfig, message_id: str, text: str) -> BridgeResult:
    text = normalize_reply_text(text).strip()
    validation = validate_short_reply_text(text)
    if not validation.handled:
        return validation
    result = send_reply(cfg, message_id, text, idempotency_key=_short_reply_key(message_id, text))
    if not result.handled:
        return result
    return BridgeResult(True, "short reply sent; activity remains open")


def send_final_reply(cfg: FeishuBridgeConfig, message_id: str, text: str) -> BridgeResult:
    result = send_reply(cfg, message_id, text)
    if result.handled:
        mark_activity_done(cfg, message_id, reason="final Feishu reply sent")
        return BridgeResult(True, "final reply sent; activity marked done")
    detail = f"final Feishu reply failed: {result.detail}"
    mark_activity_blocked(cfg, message_id, reason=detail)
    print(f"[cnb-feishu-reply] {message_id or '(missing message_id)'} {detail}", file=sys.stderr)
    return BridgeResult(False, f"{detail}; activity remains open")


def normalize_reply_text(text: str) -> str:
    if "\n" in text or "\\n" not in text:
        return text
    return text.replace("\\r\\n", "\n").replace("\\n", "\n")


def validate_short_reply_text(text: str) -> BridgeResult:
    if not text:
        return BridgeResult(False, "short reply text is empty")
    if len(text) > SHORT_REPLY_MAX_CHARS:
        return BridgeResult(False, f"short reply is too long; max {SHORT_REPLY_MAX_CHARS} chars")
    if len(text.splitlines()) > SHORT_REPLY_MAX_LINES:
        return BridgeResult(False, f"short reply has too many lines; max {SHORT_REPLY_MAX_LINES}")
    if CODE_FENCE_RE.search(text):
        return BridgeResult(False, "short reply cannot include fenced code blocks; use final reply for summaries")
    return BridgeResult(True, "short reply text accepted")


def send_reply_hermes_lark_cli(
    cfg: FeishuBridgeConfig,
    message_id: str,
    text: str,
    *,
    idempotency_key: str = "",
) -> BridgeResult:
    cmd = [
        *lark_cli_command(cfg),
        "im",
        "+messages-reply",
        "--as",
        cfg.identity,
        "--message-id",
        message_id,
        "--text",
        text,
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


def lark_cli_command(cfg: FeishuBridgeConfig) -> list[str]:
    cmd = ["lark-cli"]
    if cfg.lark_cli_profile:
        cmd.extend(["--profile", cfg.lark_cli_profile])
    return cmd


def send_reply_openapi(
    cfg: FeishuBridgeConfig,
    message_id: str,
    text: str,
    *,
    idempotency_key: str = "",
) -> BridgeResult:
    token = tenant_access_token(cfg)
    if not token.handled:
        return token
    headers = {"Authorization": f"Bearer {token.detail}"}
    if idempotency_key:
        headers["X-Request-Id"] = idempotency_key
    payload = build_openapi_reply_payload(text)
    result = openapi_post(f"/open-apis/im/v1/messages/{message_id}/reply", payload, headers=headers)
    if not result.handled:
        return result
    record_outgoing_reply(cfg, message_id, _message_id_from_openapi_response(result.detail))
    return BridgeResult(True, "reply sent")


def build_openapi_reply_payload(text: str) -> dict[str, str]:
    if should_send_reply_as_post(text):
        return {
            "msg_type": "post",
            "content": json.dumps({"zh_cn": {"content": [[{"tag": "md", "text": text}]]}}, ensure_ascii=False),
        }
    return {
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }


def should_send_reply_as_post(text: str) -> bool:
    return bool(CODE_FENCE_RE.search(text) or MARKDOWN_REPLY_RE.search(text))


def send_reply_card_openapi(
    cfg: FeishuBridgeConfig,
    message_id: str,
    card: dict[str, Any],
    *,
    idempotency_key: str = "",
) -> BridgeResult:
    token = tenant_access_token(cfg)
    if not token.handled:
        return token
    headers = {"Authorization": f"Bearer {token.detail}"}
    if idempotency_key:
        headers["X-Request-Id"] = idempotency_key
    payload = {
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    return openapi_post(f"/open-apis/im/v1/messages/{message_id}/reply", payload, headers=headers)


def update_message_card_openapi(cfg: FeishuBridgeConfig, message_id: str, card: dict[str, Any]) -> BridgeResult:
    if not message_id:
        return BridgeResult(False, "message_id missing")
    token = tenant_access_token(cfg)
    if not token.handled:
        return token
    payload = {"content": json.dumps(card, ensure_ascii=False)}
    return openapi_request(
        "PATCH",
        f"/open-apis/im/v1/messages/{message_id}",
        payload,
        headers={"Authorization": f"Bearer {token.detail}"},
    )


def _message_id_from_openapi_response(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""
    message_id = data.get("message_id")
    return message_id if isinstance(message_id, str) else ""


def tenant_access_token(cfg: FeishuBridgeConfig) -> BridgeResult:
    if not cfg.app_id or not cfg.app_secret:
        return BridgeResult(False, "Feishu app_id/app_secret missing for local_openapi transport")
    result = openapi_post(
        "/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": cfg.app_id, "app_secret": cfg.app_secret},
    )
    if not result.handled:
        return result
    try:
        payload = json.loads(result.detail)
    except json.JSONDecodeError:
        return BridgeResult(False, "invalid tenant_access_token response")
    token = payload.get("tenant_access_token")
    if isinstance(token, str) and token:
        return BridgeResult(True, token)
    return BridgeResult(False, f"tenant_access_token missing: {_snippet(result.detail)}")


def openapi_post(path: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> BridgeResult:
    return openapi_request("POST", path, payload, headers=headers)


def openapi_get(
    path: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> BridgeResult:
    return openapi_request("GET", path, None, params=params, headers=headers)


def openapi_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> BridgeResult:
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req_headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    request = urllib.request.Request(
        f"https://open.feishu.cn{path}{query}", data=body, headers=req_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        return BridgeResult(False, f"Feishu OpenAPI HTTP {exc.code}: {_snippet(detail)}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return BridgeResult(False, f"Feishu OpenAPI failed: {exc}")
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return BridgeResult(False, f"Feishu OpenAPI returned non-json: {_snippet(text)}")
    if decoded.get("code", 0) == 0:
        return BridgeResult(True, text)
    return BridgeResult(False, f"Feishu OpenAPI error: {_snippet(text)}")


def handle_bridge_command(
    event: FeishuInboundEvent, cfg: FeishuBridgeConfig, *, dry_run: bool = False
) -> BridgeResult | None:
    name = command_name(event.text)
    if name in TUI_COMMANDS:
        reply = build_tui_snapshot_reply(cfg)
        return reply_to_command(event, cfg, reply, dry_run=dry_run)
    if name in WATCH_COMMANDS:
        started = start_watch_viewer(cfg)
        reply = started.detail if started.handled else f"无法启动只读 Web TUI：{started.detail}"
        return reply_to_command(event, cfg, reply, dry_run=dry_run)
    if name in HELP_COMMANDS:
        return reply_to_command(event, cfg, command_help_text(cfg), dry_run=dry_run)
    if name in STATUS_COMMANDS:
        return reply_to_command(event, cfg, build_status_reply(cfg), dry_run=dry_run)
    return None


def reply_to_command(
    event: FeishuInboundEvent, cfg: FeishuBridgeConfig, text: str, *, dry_run: bool = False
) -> BridgeResult:
    if dry_run:
        print(text)
        return BridgeResult(True, "dry-run command")
    result = send_reply(cfg, event.message_id, text)
    if result.handled:
        return BridgeResult(True, "command reply sent")
    return BridgeResult(False, result.detail)


def command_help_text(cfg: FeishuBridgeConfig | None = None) -> str:
    label = role_label(cfg)
    status_scope = (
        "机器总管、设备主管、团队工作面、用户前台 CLI"
        if cfg and _resolve_role(cfg.pilot_role) is CHIEF_ROLE
        else "设备主管、团队工作面、用户前台 CLI"
    )
    return (
        f"CNB 飞书可以直接用自然语言说明目标，{label}会自己选择需要的本机能力。\n\n"
        "精确命令是可选兜底：\n"
        f"- /cnb_tui 或 /c_tui：查看{label}当前 TUI 快照\n"
        "- /cnb_watch 或 /c_watch：启动只读 Web TUI 观看链接\n"
        f"- /cnb_status 或 /c_status：查看{status_scope}状态\n"
        "- /cnb_help 或 /c_help：显示这段帮助\n\n"
        f"普通消息会转给{label}处理；默认只在最终回复时推送通知。"
    )


def build_status_reply(cfg: FeishuBridgeConfig) -> str:
    return f"{role_status_title(cfg)}：\n{describe_activity(cfg)}"


def build_activity_reply(cfg: FeishuBridgeConfig) -> str:
    snapshot = build_activity_snapshot(cfg)
    return f"{snapshot.title}\n{render_activity_snapshot_text(snapshot)}"


def bridge_affordance_text(cfg: FeishuBridgeConfig | None = None) -> str:
    policy = cfg.notification_policy if cfg is not None else DEFAULT_NOTIFICATION_POLICY
    policy_line = (
        "- 通知策略：默认只推最终结果；不要为了实时状态连续发送飞书回复，实时观察优先发 `cnb feishu watch` 链接。"
        if policy == "final_only"
        else "- 通知策略：按当前配置可以推送收到/活动状态，但仍要避免无信息量的连续回复。"
    )
    readback_line = (
        "- 飞书侧消息排障：只有用户明确问消息没发到、飞书历史或已读状态时，且 `readback_enabled=true`，"
        "才运行 `cnb feishu history --limit 12` 或 `cnb feishu inspect-message <message_id>`；不要默认读取聊天历史。"
    )
    resource_line = (
        "- 飞书图片/文件/文档链接：bridge 会把当前入站消息中的资源下载成本机路径或列出链接；"
        "看到 `[Feishu resources handed to Claude Code]` 后直接读取路径/链接。"
    )
    return (
        "原则：不要要求用户记命令。先理解用户自然语言目标，再直接调用本机能力完成。\n"
        f"{policy_line}\n"
        '- 短请求：需要用户补充信息、确认选择或授权动作时，可以用 `cnb feishu ask <message_id> "短问题"`；'
        "这不会结束当前任务，不要用它刷状态。\n"
        "- 回复文案：不要写 `[收到]`、`[OK]` 这类伪飞书表情；需要 reaction 时用真实 `emoji_type`，否则用普通文本。\n"
        "- 状态/进度/终端画面：用户明确要看时再运行 `cnb feishu activity`，把当前一屏用 `cnb feishu reply` 发回飞书。\n"
        "- 运行面/团队/前台进程排障：只有用户明确要求实例、会话、进程或团队看板时才展开。\n"
        "- 观察链接/只读画面：运行 `cnb feishu watch`，把返回链接发回飞书。\n"
        f"{resource_line}\n"
        f"{readback_line}\n"
        "- 普通开发、排障、调研任务：照常处理；完成、卡住或需要确认时用 `cnb feishu reply` 主动回报。"
    )


def build_tui_snapshot_reply(cfg: FeishuBridgeConfig) -> str:
    captured = capture_tui_snapshot(cfg)
    if not captured.handled:
        return f"无法获取{role_label(cfg)} TUI：{captured.detail}"
    body = _truncate_text(captured.detail.strip() or "(tmux pane has no visible content)", SNAPSHOT_MAX_CHARS)
    return f"{role_label(cfg)} TUI 快照（最近 {cfg.tui_capture_lines} 行）：\n\n```text\n{body}\n```"


def capture_current_tui_screen(cfg: FeishuBridgeConfig) -> BridgeResult:
    started = start_pilot_if_needed(cfg)
    if not started.handled:
        return started
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", cfg.pilot_tmux, "-p", "-J"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"tmux capture failed: {exc}")
    if result.returncode != 0:
        detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
        return BridgeResult(False, f"tmux capture failed: {detail}")
    return BridgeResult(True, result.stdout)


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
        return _watch_url_with_token(cfg.watch_public_url, cfg.watch_token)
    host = "127.0.0.1" if cfg.watch_host in {"", "0.0.0.0", "::"} else cfg.watch_host
    return _watch_url_with_token(f"http://{host}:{port}", cfg.watch_token)


def _watch_url_with_token(url: str, token: str) -> str:
    if not token:
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if any(key == "token" for key, _value in query):
        return url
    query.append(("token", token))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def redacted_watch_url(url: str, token: str) -> str:
    if not token:
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, "<redacted>" if key == "token" else value) for key, value in query]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
    )


def derive_watch_public_url(public_url: str) -> str:
    return f"{public_url.rstrip('/')}/watch" if public_url else ""


def watch_route(path: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(path)
    route = parsed.path.rstrip("/") or "/"
    if route == "/watch" or route.endswith("/watch"):
        return "page", route
    if route == "/watch/snapshot" or route.endswith("/watch/snapshot"):
        return "snapshot", route
    return "", route


def _watch_request_token(path: str, headers: Any) -> str:
    parsed = urllib.parse.urlparse(path)
    query = urllib.parse.parse_qs(parsed.query)
    token = query.get("token", [""])[0]
    if token:
        return token
    header_token = headers.get("X-CNB-Watch-Token", "") if headers else ""
    if header_token:
        return str(header_token)
    auth = headers.get("Authorization", "") if headers else ""
    if isinstance(auth, str) and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def watch_request_authorized(path: str, headers: Any, cfg: FeishuBridgeConfig, *, require_token: bool = False) -> bool:
    if not cfg.watch_token:
        return not require_token
    return secrets.compare_digest(_watch_request_token(path, headers), cfg.watch_token)


def watch_snapshot_payload(cfg: FeishuBridgeConfig) -> dict[str, Any]:
    captured = capture_tui_snapshot(cfg)
    return {
        "ok": captured.handled,
        "text": captured.detail if captured.handled else f"ERROR: {captured.detail}",
        "session": cfg.pilot_tmux,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


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


def _tmux_session_names() -> set[str]:
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _truncate_inline(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "…"


def serve_watch_viewer(cfg: FeishuBridgeConfig, host: str, port: int) -> int:
    class WatchHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request_cfg = FeishuBridgeConfig.load(config_path=cfg.config_path, project_root=cfg.project_root)
            route = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
            if route in {"/", "/index.html"}:
                if not watch_request_authorized(self.path, self.headers, request_cfg):
                    self._send_json({"ok": False, "error": "watch token required"}, status=HTTPStatus.FORBIDDEN)
                    return
                embedded = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("embed", [""])[0] == "1"
                self._send_html(watch_page_html(request_cfg, embedded=embedded))
                return
            if route == "/snapshot":
                if not watch_request_authorized(self.path, self.headers, request_cfg):
                    self._send_json({"ok": False, "error": "watch token required"}, status=HTTPStatus.FORBIDDEN)
                    return
                self._send_json(watch_snapshot_payload(request_cfg))
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

        def _send_json(self, payload: dict[str, Any], *, status: int = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
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


def watch_page_html(cfg: FeishuBridgeConfig, snapshot_url: str = "", *, embedded: bool = False) -> str:
    title = f"CNB TUI - {cfg.pilot_tmux}"
    safe_title = html.escape(title)
    snapshot = json.dumps(snapshot_url or _watch_url_with_token("/snapshot", cfg.watch_token))
    refresh_ms = max(100, min(cfg.watch_refresh_ms, 5000))
    header_html = (
        "" if embedded else f'<header><strong>{safe_title}</strong><span id="meta">connecting...</span></header>'
    )
    screen_min_height = "100vh" if embedded else "calc(100vh - 43px)"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    html, body {{ min-height: 100%; }}
    body {{ margin: 0; background: #0c0d0e; color: #e7e7e7; font: 14px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    header {{ position: sticky; top: 0; z-index: 1; display: flex; justify-content: space-between; gap: 16px; padding: 10px 14px; background: #17191b; border-bottom: 1px solid #30343a; }}
    #screen {{ white-space: pre-wrap; margin: 0; padding: 14px; line-height: 1.4; overflow-wrap: anywhere; min-height: {screen_min_height}; }}
    #meta {{ color: #9aa0a6; }}
  </style>
</head>
<body>
  {header_html}
  <pre id="screen"></pre>
  <script>
    const REFRESH_MS = {refresh_ms};
    const BOTTOM_SLOP = 80;
    const screen = document.getElementById('screen');
    const meta = document.getElementById('meta');
    let lastText = null;
    let inFlight = false;
    let pinnedToBottom = true;
    function maxScrollTop() {{
      return Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    }}
    function nearBottom() {{
      return maxScrollTop() - window.scrollY <= BOTTOM_SLOP;
    }}
    function scrollToBottom() {{
      window.scrollTo({{ top: maxScrollTop() }});
    }}
    window.addEventListener('scroll', () => {{
      pinnedToBottom = nearBottom();
    }}, {{ passive: true }});
    async function refresh() {{
      if (inFlight) return;
      inFlight = true;
      const shouldStick = pinnedToBottom || nearBottom();
      try {{
        const res = await fetch({snapshot}, {{ cache: 'no-store' }});
        const data = await res.json();
        const text = data.text || '';
        if (text !== lastText) {{
          lastText = text;
          screen.textContent = text;
        }}
        if (shouldStick) {{
          requestAnimationFrame(scrollToBottom);
        }}
        if (meta) meta.textContent = (data.updated_at || '') + ' · ' + REFRESH_MS + 'ms';
      }} catch (err) {{
        if (meta) meta.textContent = String(err);
      }} finally {{
        inFlight = false;
      }}
    }}
    refresh();
    setInterval(refresh, REFRESH_MS);
  </script>
</body>
</html>
"""


def _ack_key(message_id: str) -> str:
    return f"cnb-feishu-ack-{_message_digest(message_id)}"


def _short_reply_key(message_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{message_id}\n{text}".encode()).hexdigest()[:16]
    return f"cnb-feishu-ask-{_message_digest(message_id)}-{digest}"


def _message_digest(message_id: str) -> str:
    return hashlib.sha256(message_id.encode()).hexdigest()[:16]


def _snippet(text: str) -> str:
    return " ".join(text.strip().split())[:240]


def setup_config(args: argparse.Namespace, base: FeishuBridgeConfig) -> BridgeResult:
    has_chat_id = bool(args.chat_id or base.allowed_chat_ids)
    role = _resolve_role(getattr(args, "role", "") or base.pilot_role)
    base_role = _resolve_role(base.pilot_role)
    default_bridge_tmux = role.default_bridge_tmux
    default_watch_tmux = role.default_watch_tmux
    default_pilot_name = role.default_name
    default_pilot_tmux = role.default_tmux
    device_supervisor_name = getattr(args, "device_supervisor_name", "")
    device_supervisor_tmux = getattr(args, "device_supervisor_tmux", "")
    device_chief_name = getattr(args, "device_chief_name", "")
    device_chief_tmux = getattr(args, "device_chief_tmux", "")
    terminal_supervisor_name = getattr(args, "terminal_supervisor_name", "")
    terminal_supervisor_tmux = getattr(args, "terminal_supervisor_tmux", "")
    watch_public_url = getattr(args, "watch_public_url", "") or base.watch_public_url
    watch_token = getattr(args, "watch_token", "") or base.watch_token or secrets.token_urlsafe(24)
    pilot_name = (
        device_chief_name
        or device_supervisor_name
        or terminal_supervisor_name
        or (base.pilot_name if base_role is role else default_pilot_name)
    )
    pilot_tmux = (
        device_chief_tmux
        or device_supervisor_tmux
        or terminal_supervisor_tmux
        or (base.pilot_tmux if base_role is role else default_pilot_tmux)
    )
    group_routing_chat_ids = list(base.group_message_routing_chat_ids)
    explicit_group_chats = getattr(args, "group_routing_chat_id", None) or []
    if explicit_group_chats:
        group_routing_chat_ids = [str(item) for item in explicit_group_chats if str(item)]
    group_routing = getattr(args, "group_message_routing", "") or base.group_message_routing
    section = {
        "role": role.role_id,
        "transport": "local_openapi",
        "app_id": args.app_id or base.app_id,
        "app_secret": args.app_secret or base.app_secret,
        "verification_token": args.verification_token or base.verification_token or secrets.token_urlsafe(24),
        "event_key": DEFAULT_EVENT_KEY,
        "identity": "bot",
        "webhook_host": args.webhook_host or base.webhook_host,
        "webhook_port": args.webhook_port or base.webhook_port,
        "webhook_public_url": args.webhook_public_url or base.webhook_public_url,
        "chat_id": args.chat_id or (next(iter(base.allowed_chat_ids), "")),
        "auto_bind_chat": False if has_chat_id else not getattr(args, "no_auto_bind_chat", False),
        "bot_open_id": getattr(args, "bot_open_id", "") or base.bot_open_id,
        "bot_name": getattr(args, "bot_name", "") or base.bot_name,
        "group_message_routing": _group_message_routing(group_routing),
        "group_message_routing_chat_ids": sorted(set(group_routing_chat_ids)),
        "bridge_tmux": base.bridge_tmux if base_role is role else default_bridge_tmux,
        "agent": "codex",
        "notification_policy": base.notification_policy,
        "ack": True,
        "activity_updates": True,
        "activity_update_seconds": list(base.activity_update_seconds),
        "activity_update_repeat_seconds": base.activity_update_repeat_seconds,
        "activity_update_max_seconds": base.activity_update_max_seconds,
        "activity_render_style": base.activity_render_style,
        "auto_start": True,
        "startup_wait_seconds": base.startup_wait_seconds,
        "tui_capture_lines": base.tui_capture_lines,
        "watch_tool": "builtin",
        "watch_tmux": base.watch_tmux if base_role is role else default_watch_tmux,
        "watch_host": base.watch_host,
        "watch_port": base.watch_port,
        "watch_public_url": watch_public_url,
        "watch_token": watch_token,
        "watch_refresh_ms": base.watch_refresh_ms,
        "readback_enabled": base.readback_enabled,
        "readback_allow_unlisted_chat": base.readback_allow_unlisted_chat,
        "readback_default_limit": base.readback_default_limit,
        "readback_max_limit": base.readback_max_limit,
        "resource_handoff_enabled": base.resource_handoff_enabled,
        "resource_handoff_max_bytes": base.resource_handoff_max_bytes,
        "caffeine_enabled": base.caffeine_enabled,
    }
    if role is CHIEF_ROLE:
        section["device_chief_name"] = pilot_name
        section["device_chief_tmux"] = pilot_tmux
    else:
        section["device_supervisor_name"] = pilot_name
        section["device_supervisor_tmux"] = pilot_tmux
    public_url = str(section["webhook_public_url"])
    if not public_url and args.tunnel != "none":
        tunnel = ensure_tunnel(str(section["webhook_host"]), int(str(section["webhook_port"])), mode=args.tunnel)
        if tunnel.handled:
            public_url = tunnel.detail
            section["webhook_public_url"] = public_url
    if public_url and not str(section["watch_public_url"]):
        section["watch_public_url"] = derive_watch_public_url(public_url)

    try:
        current = base.config_path.read_text() if base.config_path.exists() else ""
        base.config_path.parent.mkdir(parents=True, exist_ok=True)
        base.config_path.write_text(_replace_toml_section(current, "feishu", _render_feishu_section(section)))
    except OSError as exc:
        return BridgeResult(False, f"failed to write {base.config_path}: {exc}")

    details = [f"config written: {base.config_path}"]
    if public_url:
        details.append(f"webhook_url: {public_url}")
    watch_public_url_value = str(section["watch_public_url"])
    if watch_public_url_value:
        detail_cfg = replace(
            base,
            watch_public_url=watch_public_url_value,
            watch_token=str(section["watch_token"]),
        )
        detail_url = redacted_watch_url(
            watch_url(detail_cfg, int(str(section["watch_port"]))), str(section["watch_token"])
        )
        details.append(f"watch_url: {detail_url}")
    if not section["app_id"] or not section["app_secret"]:
        details.append("app credentials pending")
    return BridgeResult(True, "; ".join(details))


def ensure_tunnel(host: str, port: int, *, mode: str = "auto") -> BridgeResult:
    if mode not in {"auto", "ngrok", "none"}:
        return BridgeResult(False, f"unsupported tunnel mode: {mode}")
    if mode == "none":
        return BridgeResult(False, "tunnel disabled")
    if not shutil.which("ngrok"):
        return BridgeResult(False, "ngrok not found; install ngrok and authenticate it before enabling tunnel setup")
    current = ngrok_public_url_for(host, port)
    if current:
        return BridgeResult(True, current)
    session = "cnb-feishu-tunnel" if port == DEFAULT_WEBHOOK_PORT else f"cnb-feishu-tunnel-{port}"
    if not has_session(session):
        try:
            result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", session, "ngrok", "http", f"{host}:{port}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BridgeResult(False, f"failed to start ngrok: {exc}")
        if result.returncode != 0:
            detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
            return BridgeResult(False, f"failed to start ngrok: {detail}")
    for _ in range(20):
        time.sleep(0.5)
        current = ngrok_public_url_for(host, port)
        if current:
            return BridgeResult(True, current)
    return BridgeResult(False, "ngrok public URL not ready")


def _ngrok_tunnels() -> list[dict[str, Any]]:
    request = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            payload: dict[str, Any] = json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []
    tunnels = payload.get("tunnels")
    if not isinstance(tunnels, list):
        return []
    return [tunnel for tunnel in tunnels if isinstance(tunnel, dict)]


def ngrok_public_url_for(host: str, port: int) -> str:
    for tunnel in _ngrok_tunnels():
        assert isinstance(tunnel, dict)
        raw_cfg = tunnel.get("config")
        cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
        addr = str(cfg.get("addr") or "")
        if not _ngrok_addr_matches(addr, host, port):
            continue
        url = tunnel.get("public_url")
        if isinstance(url, str) and url.startswith("https://"):
            return url
    for tunnel in _ngrok_tunnels():
        assert isinstance(tunnel, dict)
        raw_cfg = tunnel.get("config")
        cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
        addr = str(cfg.get("addr") or "")
        if not _ngrok_addr_matches(addr, host, port):
            continue
        url = tunnel.get("public_url")
        if isinstance(url, str):
            return url
    return ""


def _ngrok_addr_matches(addr: str, host: str, port: int) -> bool:
    if not addr:
        return False
    parsed = urllib.parse.urlparse(addr if "://" in addr else f"http://{addr}")
    if parsed.port != port:
        return False
    configured_host = (host or DEFAULT_WEBHOOK_HOST).strip()
    actual_host = parsed.hostname or ""
    return configured_host in {"0.0.0.0", "", actual_host} or actual_host in {"127.0.0.1", "localhost"}


def ngrok_public_url() -> str:
    tunnels = _ngrok_tunnels()
    if not tunnels:
        return ""
    for tunnel in tunnels:
        url = tunnel.get("public_url")
        if isinstance(url, str) and url.startswith("https://"):
            return url
    for tunnel in tunnels:
        url = tunnel.get("public_url")
        if isinstance(url, str):
            return url
    return ""


def run_setup(args: argparse.Namespace, cfg: FeishuBridgeConfig) -> int:
    configured = setup_config(args, cfg)
    print(configured.detail)
    if not configured.handled:
        return 1
    next_cfg = FeishuBridgeConfig.load(config_path=cfg.config_path, project_root=cfg.project_root)
    if not args.no_start:
        started = start_bridge_daemon(next_cfg)
        print(started.detail)
        if not started.handled:
            return 1
    print("OK feishu setup")
    return 0


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
    bound = bind_chat_if_needed(event, cfg)
    if not bound.handled:
        return bound
    if cfg.auto_bind_chat and event.chat_id:
        cfg = replace(cfg, allowed_chat_ids=frozenset({event.chat_id}), auto_bind_chat=False)

    command_result = handle_bridge_command(event, cfg, dry_run=dry_run)
    if command_result is not None:
        return command_result

    routed = route_event(event, cfg, dry_run=dry_run)
    if routed.handled and not dry_run:
        record_activity_start(cfg, event)
    if routed.handled and send_ack and not dry_run:
        progress_details: list[str] = []
        ack = reply_ack(
            event,
            cfg,
            f"已收到，{role_label(cfg)}已开始处理；你可以用自然语言继续要求状态、终端画面或观察链接。",
        )
        if ack.handled:
            progress_details.append(ack.detail)
        elif should_send_ack(cfg):
            return BridgeResult(True, f"{routed.detail}; ack skipped: {ack.detail}")
        activity = start_activity_monitor(event, cfg)
        if activity.handled:
            progress_details.append(activity.detail)
        if progress_details:
            return BridgeResult(True, f"{routed.detail}; {'; '.join(progress_details)}")
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


def handle_webhook_payload(
    payload: dict[str, Any],
    cfg: FeishuBridgeConfig,
    *,
    allow_any_chat: bool = False,
    dry_run: bool = False,
) -> tuple[int, dict[str, Any], BridgeResult]:
    if not webhook_token_ok(payload, cfg):
        return (
            HTTPStatus.FORBIDDEN,
            {"ok": False, "error": "verification token mismatch"},
            BridgeResult(False, "token mismatch"),
        )
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if isinstance(challenge, str):
            return HTTPStatus.OK, {"challenge": challenge}, BridgeResult(True, "url verification")
        return (
            HTTPStatus.BAD_REQUEST,
            {"ok": False, "error": "challenge missing"},
            BridgeResult(False, "challenge missing"),
        )

    result = handle_payload(payload, cfg, allow_any_chat=allow_any_chat, dry_run=dry_run)
    return HTTPStatus.OK, {"ok": result.handled, "detail": result.detail}, result


def webhook_token_ok(payload: dict[str, Any], cfg: FeishuBridgeConfig) -> bool:
    if not cfg.verification_token:
        return True
    header_value = payload.get("header")
    header: dict[str, Any] = header_value if isinstance(header_value, dict) else {}
    token = payload.get("token") or header.get("token")
    return token == cfg.verification_token


def serve_webhook(
    cfg: FeishuBridgeConfig,
    *,
    allow_any_chat: bool = False,
    dry_run: bool = False,
    max_events: int = 0,
) -> int:
    if cfg.transport != "local_openapi":
        return consume_hermes_events(cfg, allow_any_chat=allow_any_chat, dry_run=dry_run, max_events=max_events)
    if not cfg.enabled:
        print("ERROR: feishu bridge disabled", file=sys.stderr)
        return 1
    if not cfg.allowed_chat_ids and not cfg.auto_bind_chat and not allow_any_chat:
        print(
            "WARN: no allowed_chat_ids configured; URL verification will work, messages will be skipped.",
            file=sys.stderr,
        )
    if cfg.auto_bind_chat and not cfg.allowed_chat_ids:
        print(
            "WARN: auto_bind_chat enabled; the first incoming Feishu chat will be bound to this Mac.",
            file=sys.stderr,
        )

    class FeishuWebhookHandler(BaseHTTPRequestHandler):
        handled_events = 0

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or "0")
            try:
                payload = json.loads(self.rfile.read(length).decode() or "{}")
            except json.JSONDecodeError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid json: {exc}"})
                return
            if not isinstance(payload, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload"})
                return

            request_cfg = FeishuBridgeConfig.load(config_path=cfg.config_path, project_root=cfg.project_root)
            status, response, result = handle_webhook_payload(
                payload, request_cfg, allow_any_chat=allow_any_chat, dry_run=dry_run
            )
            print(result.detail, file=sys.stderr)
            if result.handled and payload.get("type") != "url_verification":
                type(self).handled_events += 1
            self._send_json(status, response)
            if max_events > 0 and type(self).handled_events >= max_events:
                threading.Thread(target=self.server.shutdown, daemon=True).start()

        def do_GET(self) -> None:
            request_cfg = FeishuBridgeConfig.load(config_path=cfg.config_path, project_root=cfg.project_root)
            route_kind, route_path = watch_route(self.path)
            if route_kind == "page":
                if not watch_request_authorized(self.path, self.headers, request_cfg, require_token=True):
                    self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "watch token required"})
                    return
                snapshot_url = _watch_url_with_token(f"{route_path}/snapshot", request_cfg.watch_token)
                self._send_html(watch_page_html(request_cfg, snapshot_url=snapshot_url))
                return
            if route_kind == "snapshot":
                if not watch_request_authorized(self.path, self.headers, request_cfg, require_token=True):
                    self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "watch token required"})
                    return
                self._send_json(HTTPStatus.OK, watch_snapshot_payload(request_cfg))
                return
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "cnb feishu local_openapi webhook",
                    "project": str(cfg.project_root),
                },
            )

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[cnb-feishu-webhook] {self.address_string()} {fmt % args}", file=sys.stderr)

        def _send_html(self, body: str) -> None:
            encoded = body.encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    try:
        server = ThreadingHTTPServer((cfg.webhook_host, cfg.webhook_port), FeishuWebhookHandler)
    except OSError as exc:
        print(f"ERROR: failed to bind Feishu webhook server: {exc}", file=sys.stderr)
        return 1
    url = cfg.webhook_public_url or f"http://{cfg.webhook_host}:{cfg.webhook_port}/"
    print(f"[cnb-feishu-webhook] ready transport=local_openapi url={url}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    print(f"feishu bridge handled {FeishuWebhookHandler.handled_events} event(s)")
    return 0


def _stderr_ready_pump(stream: Any, ready: threading.Event) -> None:
    for line in stream:
        if "[event] ready" in line:
            ready.set()
        print(line, end="", file=sys.stderr)


def consume_hermes_events(
    cfg: FeishuBridgeConfig,
    *,
    allow_any_chat: bool = False,
    dry_run: bool = False,
    max_events: int = 0,
    timeout: str = "",
) -> int:
    if not cfg.enabled:
        print("ERROR: feishu bridge disabled", file=sys.stderr)
        return 1
    if cfg.transport != "hermes_lark_cli":
        print(f"ERROR: unsupported Hermes transport: {cfg.transport}", file=sys.stderr)
        return 1
    if not cfg.allowed_chat_ids and not allow_any_chat:
        print("ERROR: no allowed_chat_ids configured in ~/.cnb/config.toml [feishu]", file=sys.stderr)
        print("For development only, pass --allow-any-chat.", file=sys.stderr)
        return 1

    cmd = [*lark_cli_command(cfg), "event", "consume", cfg.event_key, "--as", cfg.identity]
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


def consume_events(
    cfg: FeishuBridgeConfig,
    *,
    allow_any_chat: bool = False,
    dry_run: bool = False,
    max_events: int = 0,
    timeout: str = "",
) -> int:
    if cfg.transport == "local_openapi":
        return serve_webhook(cfg, allow_any_chat=allow_any_chat, dry_run=dry_run, max_events=max_events)
    if cfg.transport == "hermes_lark_cli":
        return consume_hermes_events(
            cfg,
            allow_any_chat=allow_any_chat,
            dry_run=dry_run,
            max_events=max_events,
            timeout=timeout,
        )
    print(f"ERROR: unsupported Feishu transport: {cfg.transport}", file=sys.stderr)
    return 1


def caffeine_pid_file(cfg: FeishuBridgeConfig) -> Path:
    return cfg.config_path.parent / f"{_safe_path_part(cfg.bridge_tmux)}.caffeinate.pid"


def _read_caffeine_pid(path: Path) -> int | None:
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    try:
        pid = int(text)
    except ValueError:
        return None
    return pid if pid > 0 else None


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _remove_caffeine_pid_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def caffeine_status(cfg: FeishuBridgeConfig) -> tuple[str, str]:
    if not cfg.caffeine_enabled:
        return "disabled", "caffeine_enabled=false"
    if sys.platform != "darwin":
        return "unavailable", "not macOS"
    executable = shutil.which("caffeinate")
    if not executable:
        return "unavailable", "caffeinate not found"

    path = caffeine_pid_file(cfg)
    pid = _read_caffeine_pid(path)
    if pid is None:
        if path.exists():
            return "stale", f"invalid pid file {path}"
        return "stopped", f"{executable} available"
    if _pid_is_running(pid):
        return "active", f"pid={pid}"
    return "stale", f"pid={pid}"


def start_caffeine_companion(cfg: FeishuBridgeConfig) -> BridgeResult:
    state, detail = caffeine_status(cfg)
    if state == "disabled":
        return BridgeResult(True, "keep-awake disabled")
    if state == "unavailable":
        return BridgeResult(True, f"keep-awake unavailable ({detail})")
    if state == "active":
        return BridgeResult(True, f"keep-awake active ({detail})")
    if state == "stale":
        _remove_caffeine_pid_file(caffeine_pid_file(cfg))

    executable = shutil.which("caffeinate")
    if not executable:
        return BridgeResult(True, "keep-awake unavailable (caffeinate not found)")
    try:
        proc = subprocess.Popen(
            [executable, *CAFFEINATE_ARGS],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return BridgeResult(False, f"failed to start keep-awake companion: {exc}")

    path = caffeine_pid_file(cfg)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{proc.pid}\n")
    except OSError as exc:
        try:
            proc.terminate()
        except OSError:
            pass
        return BridgeResult(False, f"failed to record keep-awake pid: {exc}")
    return BridgeResult(True, f"keep-awake active (pid={proc.pid})")


def stop_caffeine_companion(cfg: FeishuBridgeConfig) -> BridgeResult:
    path = caffeine_pid_file(cfg)
    pid = _read_caffeine_pid(path)
    if pid is None:
        if path.exists():
            _remove_caffeine_pid_file(path)
            return BridgeResult(True, "cleared stale keep-awake pid file")
        return BridgeResult(True, "keep-awake not running")
    if not _pid_is_running(pid):
        _remove_caffeine_pid_file(path)
        return BridgeResult(True, f"cleared stale keep-awake pid={pid}")

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _remove_caffeine_pid_file(path)
        return BridgeResult(True, f"cleared stale keep-awake pid={pid}")
    except PermissionError as exc:
        return BridgeResult(False, f"failed to stop keep-awake pid={pid}: {exc}")
    except OSError as exc:
        return BridgeResult(False, f"failed to stop keep-awake pid={pid}: {exc}")
    _remove_caffeine_pid_file(path)
    return BridgeResult(True, f"stopped keep-awake pid={pid}")


def _with_companion_detail(base: str, companion: BridgeResult) -> str:
    if not companion.detail:
        return base
    if companion.handled:
        return f"{base}; {companion.detail}"
    return f"{base}; keep-awake warning: {companion.detail}"


def start_bridge_daemon(cfg: FeishuBridgeConfig) -> BridgeResult:
    if has_session(cfg.bridge_tmux):
        caffeine = start_caffeine_companion(cfg)
        return BridgeResult(True, _with_companion_detail(f"{cfg.bridge_tmux} already running", caffeine))
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
        caffeine = start_caffeine_companion(cfg)
        return BridgeResult(True, _with_companion_detail(f"started {cfg.bridge_tmux}", caffeine))
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"failed to start {cfg.bridge_tmux}: {detail}")


def stop_bridge_daemon(cfg: FeishuBridgeConfig) -> BridgeResult:
    if not has_session(cfg.bridge_tmux):
        caffeine = stop_caffeine_companion(cfg)
        return BridgeResult(caffeine.handled, _with_companion_detail(f"{cfg.bridge_tmux} is not running", caffeine))
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", cfg.bridge_tmux], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to stop {cfg.bridge_tmux}: {exc}")
    if result.returncode == 0:
        caffeine = stop_caffeine_companion(cfg)
        return BridgeResult(caffeine.handled, _with_companion_detail(f"stopped {cfg.bridge_tmux}", caffeine))
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"failed to stop {cfg.bridge_tmux}: {detail}")


def stop_watch_viewer(cfg: FeishuBridgeConfig) -> BridgeResult:
    if not has_session(cfg.watch_tmux):
        return BridgeResult(True, f"{cfg.watch_tmux} is not running")
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", cfg.watch_tmux], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to stop {cfg.watch_tmux}: {exc}")
    if result.returncode == 0:
        return BridgeResult(True, f"stopped {cfg.watch_tmux}")
    detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
    return BridgeResult(False, f"failed to stop {cfg.watch_tmux}: {detail}")


def restart_supervisor(cfg: FeishuBridgeConfig, *, force: bool = False) -> BridgeResult:
    if not has_session(cfg.pilot_tmux):
        return BridgeResult(
            False,
            f"{cfg.pilot_tmux} is not running; use 'cnb feishu start' to start",
        )

    if not force:
        open_items = open_activity_items(cfg)
        if open_items:
            count = len(open_items)
            items_summary = ", ".join(
                f"{item['message_id']} ({_format_duration(item['age_seconds'])})" for item in open_items[:3]
            )
            if count > 3:
                items_summary += f" 等{count}个"
            return BridgeResult(
                False,
                f"{role_label(cfg)} 正在处理 {count} 个飞书请求: {items_summary}; "
                f"使用 --force 强制重启，但可能中断进行中的工作",
            )

    current_hash = get_current_prompt_hash(cfg)
    stored_hash = get_stored_prompt_hash(cfg)
    if stored_hash == current_hash:
        freshness_note = " (提示词已是最新，无需重启)"
    else:
        freshness_note = f" (更新提示词: {stored_hash} -> {current_hash})"

    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", cfg.pilot_tmux],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BridgeResult(False, f"failed to stop {cfg.pilot_tmux}: {exc}")

    if result.returncode != 0:
        detail = _snippet(result.stderr) or _snippet(result.stdout) or f"exit {result.returncode}"
        return BridgeResult(False, f"failed to stop {cfg.pilot_tmux}: {detail}")

    start_result = start_pilot_if_needed(cfg)
    if start_result.handled:
        return BridgeResult(
            True,
            f"{cfg.pilot_tmux} has been restarted{freshness_note}",
        )
    return BridgeResult(
        False,
        f"{cfg.pilot_tmux} stopped but failed to restart: {start_result.detail}",
    )


def print_status(cfg: FeishuBridgeConfig) -> None:
    print(f"配置文件: {cfg.config_path}")
    print(f"启用: {'是' if cfg.enabled else '否'}")
    if cfg.transport == "hermes_lark_cli":
        print("通道: hermes_lark_cli（仅开发测试；不要作为 CNB 运行链路）")
        print(f"lark-cli profile: {cfg.lark_cli_profile or '(active default)'}")
    else:
        print("通道: local_openapi（本机 webhook + 飞书 OpenAPI，不经过 Hermes）")
    print(f"事件: {cfg.event_key} ({cfg.identity})")
    print(f"webhook: {cfg.webhook_public_url or f'http://{cfg.webhook_host}:{cfg.webhook_port}/'}")
    if cfg.allowed_chat_ids:
        chat_status = ", ".join(sorted(cfg.allowed_chat_ids))
    elif cfg.auto_bind_chat:
        chat_status = "(首次收到消息时自动绑定)"
    else:
        chat_status = "(未配置)"
    print(f"允许 chat: {chat_status}")
    print(f"允许 sender: {', '.join(sorted(cfg.allowed_sender_ids)) if cfg.allowed_sender_ids else '(全部)'}")
    bot_bits = [bit for bit in (cfg.bot_name, cfg.bot_open_id) if bit]
    print(f"群消息路由: {cfg.group_message_routing} ({' / '.join(bot_bits) if bot_bits else '未配置 bot_open_id'})")
    print(f"角色: {_resolve_role(cfg.pilot_role).role_id}")
    print(f"{role_label(cfg)}: {cfg.pilot_name}")
    print(f"{role_label(cfg)} tmux: {cfg.pilot_tmux} ({'running' if has_session(cfg.pilot_tmux) else 'stopped'})")
    print(describe_prompt_freshness(cfg))
    print(f"bridge tmux: {cfg.bridge_tmux} ({'running' if has_session(cfg.bridge_tmux) else 'stopped'})")
    print(f"watch tmux: {cfg.watch_tmux} ({'running' if has_session(cfg.watch_tmux) else 'stopped'})")
    caffeine_state, caffeine_detail = caffeine_status(cfg)
    print(f"Mac 防睡眠: {caffeine_state} ({caffeine_detail}; {caffeine_pid_file(cfg)})")
    print("飞书命令: /cnb_tui, /c_tui, /cnb_watch, /c_watch, /cnb_status, /c_status")
    print(
        f"Web TUI: {redacted_watch_url(watch_url(cfg, cfg.watch_port), cfg.watch_token)} "
        f"({cfg.watch_tool}, {cfg.watch_refresh_ms}ms)"
    )
    print(f"通知策略: {describe_notification_policy(cfg)}")
    print(f"飞书请求: {describe_request_activity(cfg)}")
    activity = "开" if should_start_activity_monitor(cfg) else "关"
    print(
        "活动反馈: "
        f"{activity} ({', '.join(str(v) + 's' for v in cfg.activity_update_seconds)}; "
        f"之后每 {cfg.activity_update_repeat_seconds}s; 最长 {cfg.activity_update_max_seconds}s)"
    )
    print(f"活动渲染: {resolve_activity_render_style(cfg)}")
    readback_scope = "允许 chat" if not cfg.readback_allow_unlisted_chat else "允许显式未列 chat"
    print(
        f"飞书回读: {'开' if cfg.readback_enabled else '关'} "
        f"({readback_scope}; 默认 {cfg.readback_default_limit} 条，最多 {cfg.readback_max_limit} 条)"
    )
    print(
        f"资源交接: {'开' if cfg.resource_handoff_enabled else '关'} "
        f"({resource_handoff_dir(cfg)}; max {cfg.resource_handoff_max_bytes} bytes)"
    )
    print(f"引擎: {cfg.agent}")
    print(f"项目目录: {cfg.project_root}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cnb feishu", description="Feishu inbound bridge for a CNB supervisor or device chief tongxue"
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="path to global cnb config (default: ~/.cnb/config.toml)"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="show bridge config and tmux status")

    setup = sub.add_parser("setup", help="write local Feishu config, start webhook, and prepare tunnel")
    setup.add_argument("--app-id", default="")
    setup.add_argument("--app-secret", default="")
    setup.add_argument("--verification-token", default="")
    setup.add_argument("--chat-id", default="")
    setup.add_argument("--webhook-public-url", default="")
    setup.add_argument("--webhook-host", default="")
    setup.add_argument("--webhook-port", type=int, default=0)
    setup.add_argument("--watch-public-url", default="")
    setup.add_argument("--watch-token", default="")
    setup.add_argument("--role", choices=("device_supervisor", "device_chief"), default="")
    setup.add_argument("--device-chief-name", default="")
    setup.add_argument("--device-chief-tmux", default="")
    setup.add_argument("--device-supervisor-name", default="")
    setup.add_argument("--device-supervisor-tmux", default="")
    setup.add_argument("--terminal-supervisor-name", default="")
    setup.add_argument("--terminal-supervisor-tmux", default="")
    setup.add_argument("--bot-open-id", default="")
    setup.add_argument("--bot-name", default="")
    setup.add_argument("--group-message-routing", choices=("all", "targeted"), default="")
    setup.add_argument("--group-routing-chat-id", action="append", default=[])
    setup.add_argument("--tunnel", choices=("auto", "ngrok", "none"), default="auto")
    setup.add_argument("--no-auto-bind-chat", action="store_true")
    setup.add_argument("--no-start", action="store_true")

    listen = sub.add_parser("listen", help="consume Feishu IM events and route them to the device supervisor tongxue")
    listen.add_argument(
        "--allow-any-chat", action="store_true", help="development only: accept events without chat allowlist"
    )
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
    restart_sv = sub.add_parser(
        "restart-supervisor", help="safely restart the supervisor to pick up an updated system prompt"
    )
    restart_sv.add_argument(
        "--force", action="store_true", help="restart even while the supervisor is actively working"
    )
    sub.add_parser("activity", help="print the current device supervisor TUI screen")
    sub.add_parser("tui", help="print the device supervisor TUI snapshot")
    sub.add_parser("watch", help="start the read-only Web TUI viewer")
    sub.add_parser("watch-stop", help="stop the read-only Web TUI viewer")
    history = sub.add_parser("history", help="opt-in Feishu chat history readback for delivery troubleshooting")
    history.add_argument("--chat-id", default="", help="Feishu chat ID to inspect; defaults to the single allowed chat")
    history.add_argument("--limit", type=int, default=0, help="number of recent messages to read")
    inspect = sub.add_parser("inspect-message", help="opt-in Feishu message inspection by message_id")
    inspect.add_argument("message_id")
    inspect.add_argument("--no-read-users", action="store_true", help="skip bot-sent message read-status lookup")
    inspect.add_argument("--read-user-limit", type=int, default=20)
    watch_serve = sub.add_parser("watch-serve", help="serve the built-in read-only Web TUI viewer")
    watch_serve.add_argument("--host", default=None)
    watch_serve.add_argument("--port", type=int, default=None)

    ask = sub.add_parser("ask", help="send a short non-final Feishu reply by message_id")
    ask.add_argument("message_id")
    ask.add_argument("text", nargs=argparse.REMAINDER)

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
    if args.cmd == "setup":
        return run_setup(args, cfg)
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
    if args.cmd == "restart-supervisor":
        result = restart_supervisor(cfg, force=args.force)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "activity":
        print(build_activity_reply(cfg))
        return 0
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
    if args.cmd == "history":
        result = build_history_readback(cfg, chat_id=args.chat_id, limit=args.limit)
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "inspect-message":
        result = inspect_message_readback(
            cfg,
            args.message_id,
            include_read_users=not args.no_read_users,
            read_user_limit=args.read_user_limit,
        )
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "watch-serve":
        return serve_watch_viewer(cfg, args.host or cfg.watch_host, args.port or cfg.watch_port)
    if args.cmd == "ask":
        result = send_short_reply(cfg, args.message_id, " ".join(args.text))
        print(result.detail)
        return 0 if result.handled else 1
    if args.cmd == "reply":
        result = send_final_reply(cfg, args.message_id, " ".join(args.text))
        print(result.detail)
        return 0 if result.handled else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
