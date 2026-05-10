#!/usr/bin/env python3
"""Export Feishu chat settings for the CNB Island simulator app."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

CNB_HOME = Path.home() / ".cnb"
CONFIG_FILE = CNB_HOME / "config.toml"
CHAT_CONFIG_FILE = CNB_HOME / "feishu_chat.json"


def _read_config(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _feishu_section(config: dict[str, Any]) -> dict[str, Any]:
    direct = config.get("feishu")
    if isinstance(direct, dict):
        return direct
    notification = config.get("notification")
    if isinstance(notification, dict):
        nested = notification.get("feishu")
        if isinstance(nested, dict):
            return nested
    return {}


def _first_string(section: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = section.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text:
                    return text
    return ""


def build_payload(config_path: Path) -> dict[str, str]:
    section = _feishu_section(_read_config(config_path))
    return {
        "appID": _first_string(section, "app_id", "app-id"),
        "appSecret": _first_string(section, "app_secret", "app-secret"),
        "chatID": _first_string(section, "chat_id", "chat-id", "allowed_chat_ids", "chat_ids"),
        "replyMessageID": "",
        "webhookURL": _first_string(section, "webhook_public_url", "webhook-public-url"),
        "verificationToken": _first_string(section, "verification_token", "verification-token"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--output", type=Path, default=CHAT_CONFIG_FILE)
    args = parser.parse_args()

    payload = build_payload(args.config.expanduser())
    args.output.expanduser().parent.mkdir(parents=True, exist_ok=True)
    args.output.expanduser().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    optional = {"replyMessageID", "webhookURL", "verificationToken"}
    missing = [key for key, value in payload.items() if key not in optional and not value]
    if missing:
        print(f"WARN wrote {args.output.expanduser()} with missing fields: {', '.join(missing)}")
    else:
        print(f"OK wrote {args.output.expanduser()} for chat {payload['chatID']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
