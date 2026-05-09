"""Tests for Feishu inbound bridge event routing."""

from __future__ import annotations

import json
from types import SimpleNamespace

from lib import feishu_bridge
from lib.feishu_bridge import FeishuBridgeConfig, FeishuInboundEvent


def _cfg(tmp_path, **kwargs):
    defaults = {
        "config_path": tmp_path / "config.toml",
        "project_root": tmp_path,
        "allowed_chat_ids": frozenset({"oc_allowed"}),
        "startup_wait_seconds": 0,
        "ack": False,
    }
    defaults.update(kwargs)
    return FeishuBridgeConfig(**defaults)


class TestFeishuBridgeConfig:
    def test_loads_feishu_section(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            """
[feishu]
chat_id = "oc_allowed"
sender_ids = ["ou_user"]
terminal_supervisor_name = "mac-owner"
terminal_supervisor_tmux = "cnb-mac-owner"
bridge_tmux = "cnb-feishu"
agent = "codex"
ack = false
"""
        )

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.allowed_chat_ids == frozenset({"oc_allowed"})
        assert cfg.allowed_sender_ids == frozenset({"ou_user"})
        assert cfg.pilot_name == "mac-owner"
        assert cfg.pilot_tmux == "cnb-mac-owner"
        assert cfg.bridge_tmux == "cnb-feishu"
        assert cfg.agent == "codex"
        assert cfg.ack is False
        assert cfg.transport == "hermes_lark_cli"

    def test_loads_tui_and_watch_settings(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            """
[feishu]
tui_capture_lines = 80
watch_tmux = "cnb-watch-test"
watch_host = "0.0.0.0"
watch_port = 9876
watch_public_url = "https://watch.example.test"
watch_tool = "ttyd"
"""
        )

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.tui_capture_lines == 80
        assert cfg.watch_tmux == "cnb-watch-test"
        assert cfg.watch_host == "0.0.0.0"
        assert cfg.watch_port == 9876
        assert cfg.watch_public_url == "https://watch.example.test"
        assert cfg.watch_tool == "ttyd"

    def test_loads_notification_feishu_section(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            """
[notification.feishu]
chat_ids = ["oc_a", "oc_b"]
"""
        )

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.allowed_chat_ids == frozenset({"oc_a", "oc_b"})

    def test_claude_agent_config_falls_back_to_codex(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('[feishu]\nagent = "claude"\n')

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.agent == "codex"


class TestEventExtraction:
    def test_extracts_flat_event_payload(self):
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "message_type": "text",
            "content": '{"text":"启动终端主管同学"}',
        }

        event = feishu_bridge.extract_event(payload)

        assert event.message_id == "om_1"
        assert event.chat_id == "oc_allowed"
        assert event.sender_id == "ou_user"
        assert event.text == "启动终端主管同学"

    def test_extracts_v2_message_payload(self):
        payload = {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_user"}},
                "message": {
                    "message_id": "om_2",
                    "chat_id": "oc_allowed",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": {"text": "看一下 #64"},
                },
            }
        }

        event = feishu_bridge.extract_event(payload)

        assert event.message_id == "om_2"
        assert event.chat_id == "oc_allowed"
        assert event.sender_id == "ou_user"
        assert event.chat_type == "group"
        assert event.text == "看一下 #64"


class TestFiltering:
    def test_rejects_without_allowlist_by_default(self, tmp_path):
        cfg = _cfg(tmp_path, allowed_chat_ids=frozenset())
        event = FeishuInboundEvent(text="hello", chat_id="oc_any")

        accepted, reason = feishu_bridge.should_accept(event, cfg)

        assert accepted is False
        assert "allowed_chat_ids" in reason

    def test_allow_any_chat_overrides_missing_allowlist(self, tmp_path):
        cfg = _cfg(tmp_path, allowed_chat_ids=frozenset())
        event = FeishuInboundEvent(text="hello", chat_id="oc_any")

        accepted, reason = feishu_bridge.should_accept(event, cfg, allow_any_chat=True)

        assert accepted is True
        assert reason == "accepted"

    def test_rejects_unlisted_chat(self, tmp_path):
        cfg = _cfg(tmp_path)
        event = FeishuInboundEvent(text="hello", chat_id="oc_other")

        accepted, reason = feishu_bridge.should_accept(event, cfg)

        assert accepted is False
        assert "not allowed" in reason

    def test_rejects_bridge_ack_messages(self, tmp_path):
        cfg = _cfg(tmp_path)
        event = FeishuInboundEvent(text=f"{feishu_bridge.ACK_PREFIX}。delivered", chat_id="oc_allowed")

        accepted, reason = feishu_bridge.should_accept(event, cfg)

        assert accepted is False
        assert "ack" in reason


class TestRouting:
    def test_bridge_commands_are_namespaced(self):
        assert feishu_bridge.is_bridge_command("/cnb_tui")
        assert feishu_bridge.is_bridge_command("/c_tui please")
        assert feishu_bridge.is_bridge_command("/cnb_watch")
        assert not feishu_bridge.is_bridge_command("/tui")
        assert not feishu_bridge.is_bridge_command("/watch")

    def test_terminal_supervisor_prompt_describes_async_reply_protocol(self, tmp_path):
        cfg = _cfg(tmp_path)

        prompt = feishu_bridge.build_pilot_system_prompt(cfg)

        assert "实时 TUI" in prompt
        assert 'cnb feishu reply <message_id> "回复内容"' in prompt
        assert "/cnb_tui" in prompt

    def test_build_pilot_command_uses_codex(self, tmp_path):
        cfg = _cfg(tmp_path, agent="codex")

        command = feishu_bridge.build_pilot_command(cfg)

        assert command[0] == "codex"
        assert "claude" not in command

    def test_route_event_starts_pilot_and_sends_message(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, pilot_tmux="cnb-pilot-test", agent="codex")
        event = FeishuInboundEvent(text="帮我看项目", message_id="om_1", chat_id="oc_allowed", sender_id="ou_user")
        calls = []

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)
        monkeypatch.setattr(feishu_bridge, "tmux_send", lambda name, text: calls.append((name, text)) or True)

        def fake_run(cmd, **kwargs):
            calls.append(tuple(cmd))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.route_event(event, cfg)

        assert result.handled is True
        assert any(call[0:4] == ("tmux", "new-session", "-d", "-s") for call in calls if isinstance(call, tuple))
        assert ("cnb-pilot-test", feishu_bridge.format_for_pilot(event)) in calls

    def test_cnb_tui_command_replies_with_snapshot(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        replies = []
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"/cnb_tui"}',
        }

        monkeypatch.setattr(feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running"))
        monkeypatch.setattr(feishu_bridge, "send_reply", lambda cfg, mid, text, **kwargs: replies.append((mid, text)) or feishu_bridge.BridgeResult(True, "sent"))

        def fake_run(cmd, **kwargs):
            assert cmd[:3] == ["tmux", "capture-pane", "-t"]
            return SimpleNamespace(returncode=0, stdout="Claude Code screen\nReady", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.handle_payload(payload, cfg)

        assert result.handled is True
        assert replies[0][0] == "om_1"
        assert "Claude Code screen" in replies[0][1]

    def test_cnb_watch_command_replies_with_builtin_viewer_url(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        replies = []
        calls = []
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"/cnb_watch"}',
        }

        monkeypatch.setattr(feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running"))
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)
        monkeypatch.setattr(feishu_bridge, "_port_available", lambda host, port: True)
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda cfg, mid, text, **kwargs: replies.append(text) or feishu_bridge.BridgeResult(True, "sent"),
        )

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.handle_payload(payload, cfg)

        assert result.handled is True
        assert "builtin" in replies[0]
        assert "http://127.0.0.1:8765" in replies[0]
        assert "watch-serve" in calls[0][-1]

    def test_start_watch_viewer_uses_ttyd_readonly(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, watch_tmux="cnb-watch-test", watch_tool="ttyd")
        calls = []

        monkeypatch.setattr(feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running"))
        monkeypatch.setattr(feishu_bridge, "choose_watch_tool", lambda preferred: "ttyd")
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)
        monkeypatch.setattr(feishu_bridge, "_port_available", lambda host, port: True)

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.start_watch_viewer(cfg)

        assert result.handled is True
        command = calls[0][-1]
        assert "ttyd -R" in command
        assert "tmux attach-session -t cnb-terminal-supervisor" in command

    def test_start_watch_viewer_existing_session_reports_configured_port(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, watch_tmux="cnb-watch-test", watch_port=8765)

        monkeypatch.setattr(feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running"))
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: name == "cnb-watch-test")
        monkeypatch.setattr(feishu_bridge, "_port_available", lambda host, port: False)

        result = feishu_bridge.start_watch_viewer(cfg)

        assert result.handled is True
        assert "127.0.0.1:8765" in result.detail
        assert "8766" not in result.detail

    def test_watch_page_html_contains_snapshot_endpoint(self, tmp_path):
        cfg = _cfg(tmp_path)

        page = feishu_bridge.watch_page_html(cfg)

        assert "/snapshot" in page
        assert cfg.pilot_tmux in page

    def test_handle_payload_dry_run_prints_message(self, tmp_path, capsys):
        cfg = _cfg(tmp_path)
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"ping"}',
        }

        result = feishu_bridge.handle_payload(payload, cfg, dry_run=True)

        out = capsys.readouterr().out
        assert result.handled is True
        assert "[Feishu inbound]" in out
        assert "ping" in out

    def test_reply_ack_uses_lark_reply_shortcut(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, ack=True)
        event = FeishuInboundEvent(text="hello", message_id="om_1", chat_id="oc_allowed")
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="{}", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.reply_ack(event, cfg, "delivered")

        assert result.handled is True
        assert calls[0][:4] == ["lark-cli", "im", "+messages-reply", "--as"]
        assert "--message-id" in calls[0]
        assert "om_1" in calls[0]

    def test_send_reply_rejects_empty_text(self, tmp_path):
        cfg = _cfg(tmp_path)

        result = feishu_bridge.send_reply(cfg, "om_1", "")

        assert result.handled is False
        assert "empty" in result.detail

    def test_send_reply_sends_plain_text(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="{}", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.send_reply(cfg, "om_1", "处理完成")

        assert result.handled is True
        assert calls[0][:4] == ["lark-cli", "im", "+messages-reply", "--as"]
        assert "--text" in calls[0]
        assert "处理完成" in calls[0]

    def test_start_bridge_daemon_preserves_config_path(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, config_path=tmp_path / "custom.toml", bridge_tmux="cnb-feishu-test")
        calls = []

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.start_bridge_daemon(cfg)

        assert result.handled is True
        command = calls[0][-1]
        assert "feishu --config" in command
        assert str(cfg.config_path) in command


class TestCli:
    def test_handle_event_cli_dry_run(self, tmp_path, capsys):
        path = tmp_path / "config.toml"
        path.write_text('[feishu]\nchat_id = "oc_allowed"\nack = false\n')
        payload = json.dumps({"chat_id": "oc_allowed", "message_id": "om_1", "content": '{"text":"hello"}'})

        code = feishu_bridge.main(["--config", str(path), "handle-event", payload, "--dry-run"])

        out = capsys.readouterr().out
        assert code == 0
        assert "hello" in out
