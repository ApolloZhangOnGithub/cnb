"""Tests for Feishu inbound bridge event routing."""

from __future__ import annotations

import io
import itertools
import json
import urllib.error
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
notification_policy = "live"
auto_bind_chat = true
activity_updates = true
activity_update_seconds = [1, 2]
activity_update_repeat_seconds = 45
activity_render_style = "codex"
caffeine_enabled = false
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
        assert cfg.notification_policy == "live"
        assert cfg.auto_bind_chat is True
        assert cfg.activity_updates is True
        assert cfg.activity_update_seconds == (1, 2)
        assert cfg.activity_update_repeat_seconds == 45
        assert cfg.activity_render_style == "codex"
        assert cfg.caffeine_enabled is False
        assert cfg.transport == "local_openapi"

    def test_loads_device_supervisor_aliases(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            """
[feishu]
device_supervisor_name = "mac-owner"
device_supervisor_tmux = "cnb-mac-owner"
"""
        )

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.pilot_name == "mac-owner"
        assert cfg.pilot_tmux == "cnb-mac-owner"

    def test_caffeine_status_disabled(self, tmp_path):
        cfg = _cfg(tmp_path, caffeine_enabled=False)

        assert feishu_bridge.caffeine_status(cfg) == "disabled"

    def test_caffeine_status_unavailable_off_mac(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        monkeypatch.setattr(feishu_bridge.sys, "platform", "linux")

        assert feishu_bridge.caffeine_status(cfg) == "unavailable (non-macOS)"

    def test_start_bridge_starts_caffeine_on_mac(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, bridge_tmux="cnb-feishu-test")
        calls = []

        class FakePopen:
            pid = 4321

            def __init__(self, args, **kwargs):
                calls.append(("popen", args, kwargs))

        def fake_run(args, **kwargs):
            calls.append(("run", args, kwargs))
            if args[:2] == ["ps", "-p"]:
                return SimpleNamespace(returncode=0, stdout="/usr/bin/caffeinate\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.sys, "platform", "darwin")
        monkeypatch.setattr(
            feishu_bridge.shutil, "which", lambda name: "/usr/bin/caffeinate" if name == "caffeinate" else None
        )
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)
        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)
        monkeypatch.setattr(feishu_bridge.subprocess, "Popen", FakePopen)
        monkeypatch.setattr(feishu_bridge.os, "kill", lambda pid, sig: None)

        result = feishu_bridge.start_bridge_daemon(cfg)

        assert result.handled is True
        assert "started cnb-feishu-test" in result.detail
        assert "caffeine active (pid 4321)" in result.detail
        assert feishu_bridge.caffeine_pid_path(cfg).read_text() == "4321"
        assert calls[0][1][:4] == ["tmux", "new-session", "-d", "-s"]
        assert calls[-1][1] == ["caffeinate", "-di"]

    def test_stop_bridge_stops_caffeine_on_mac(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, bridge_tmux="cnb-feishu-test")
        feishu_bridge.caffeine_pid_path(cfg).parent.mkdir(parents=True)
        feishu_bridge.caffeine_pid_path(cfg).write_text("4321")
        killed = []

        def fake_run(args, **kwargs):
            if args[:2] == ["ps", "-p"]:
                return SimpleNamespace(returncode=0, stdout="/usr/bin/caffeinate\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        def fake_kill(pid, sig):
            if sig != 0:
                killed.append((pid, sig))

        monkeypatch.setattr(feishu_bridge.sys, "platform", "darwin")
        monkeypatch.setattr(
            feishu_bridge.shutil, "which", lambda name: "/usr/bin/caffeinate" if name == "caffeinate" else None
        )
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)
        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)
        monkeypatch.setattr(feishu_bridge.os, "kill", fake_kill)

        result = feishu_bridge.stop_bridge_daemon(cfg)

        assert result.handled is True
        assert "stopped cnb-feishu-test" in result.detail
        assert "caffeine stopped" in result.detail
        assert killed == [(4321, feishu_bridge.signal.SIGTERM)]
        assert not feishu_bridge.caffeine_pid_path(cfg).exists()

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
watch_token = "secret-watch"
watch_tool = "ttyd"
watch_refresh_ms = 333
"""
        )

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.tui_capture_lines == 80
        assert cfg.watch_tmux == "cnb-watch-test"
        assert cfg.watch_host == "0.0.0.0"
        assert cfg.watch_port == 9876
        assert cfg.watch_public_url == "https://watch.example.test"
        assert cfg.watch_token == "secret-watch"
        assert cfg.watch_tool == "ttyd"
        assert cfg.watch_refresh_ms == 333

    def test_loads_readback_settings(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            """
[feishu]
readback_enabled = true
readback_allow_unlisted_chat = true
readback_default_limit = 8
readback_max_limit = 20
resource_handoff_enabled = false
resource_handoff_max_bytes = 4096
"""
        )

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.readback_enabled is True
        assert cfg.readback_allow_unlisted_chat is True
        assert cfg.readback_default_limit == 8
        assert cfg.readback_max_limit == 20
        assert cfg.resource_handoff_enabled is False
        assert cfg.resource_handoff_max_bytes == 4096

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

    def test_claude_agent_config_is_accepted(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('[feishu]\nagent = "claude"\n')

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.agent == "claude"

    def test_unsupported_agent_falls_back_to_claude(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('[feishu]\nagent = "unknown_engine"\n')

        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)

        assert cfg.agent == "claude"

    def test_setup_config_writes_local_openapi_section(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('[other]\nname = "kept"\n')
        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)
        args = SimpleNamespace(
            app_id="cli_test",
            app_secret="secret",
            verification_token="verify",
            chat_id="oc_allowed",
            webhook_public_url="https://example.test/cnb",
            webhook_host="",
            webhook_port=0,
            terminal_supervisor_name="",
            terminal_supervisor_tmux="",
            tunnel="none",
            no_auto_bind_chat=False,
        )

        result = feishu_bridge.setup_config(args, cfg)

        written = path.read_text()
        assert result.handled is True
        assert "[other]" in written
        assert 'transport = "local_openapi"' in written
        assert 'app_id = "cli_test"' in written
        assert 'chat_id = "oc_allowed"' in written
        assert "auto_bind_chat = false" in written
        assert 'notification_policy = "final_only"' in written
        assert "activity_updates = true" in written
        assert "activity_update_seconds = [1]" in written
        assert "activity_update_repeat_seconds = 1" in written
        assert 'activity_render_style = "auto"' in written
        assert 'device_supervisor_name = "device-supervisor"' in written
        assert 'watch_public_url = "https://example.test/cnb/watch"' in written
        assert "watch_refresh_ms = 250" in written
        assert "watch_token =" in written
        assert "readback_enabled = false" in written
        assert "resource_handoff_enabled = true" in written
        assert "token=%3Credacted%3E" in result.detail
        assert 'agent = "claude"' in written

    def test_setup_config_accepts_explicit_watch_public_url_and_token(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("[feishu]\n")
        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)
        args = SimpleNamespace(
            app_id="",
            app_secret="",
            verification_token="",
            chat_id="",
            webhook_public_url="https://bridge.example.test",
            webhook_host="",
            webhook_port=0,
            watch_public_url="https://watch.example.test/custom",
            watch_token="explicit-token",
            terminal_supervisor_name="",
            terminal_supervisor_tmux="",
            tunnel="none",
            no_auto_bind_chat=False,
        )

        result = feishu_bridge.setup_config(args, cfg)

        written = path.read_text()
        assert result.handled is True
        assert 'watch_public_url = "https://watch.example.test/custom"' in written
        assert 'watch_token = "explicit-token"' in written
        assert "token=%3Credacted%3E" in result.detail


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
                    "root_id": "om_root",
                    "parent_id": "om_parent",
                    "chat_id": "oc_allowed",
                    "chat_type": "group",
                    "thread_id": "omt_thread",
                    "message_type": "text",
                    "content": {"text": "看一下 #64"},
                },
            }
        }

        event = feishu_bridge.extract_event(payload)

        assert event.message_id == "om_2"
        assert event.root_id == "om_root"
        assert event.parent_id == "om_parent"
        assert event.thread_id == "omt_thread"
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

    def test_auto_bind_chat_accepts_missing_allowlist(self, tmp_path):
        cfg = _cfg(tmp_path, allowed_chat_ids=frozenset(), auto_bind_chat=True)
        event = FeishuInboundEvent(text="hello", chat_id="oc_any")

        accepted, reason = feishu_bridge.should_accept(event, cfg)

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


class _FakeHTTPResponse:
    def __init__(self, body: str):
        self.body = body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class TestOpenAPITransport:
    def test_openapi_request_reports_http_error_body(self, monkeypatch):
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                hdrs={},
                fp=io.BytesIO(b'{"code":999,"msg":"bad app_id"}'),
            )

        monkeypatch.setattr(feishu_bridge.urllib.request, "urlopen", fake_urlopen)

        result = feishu_bridge.openapi_post("/open-apis/test", {"hello": "world"})

        assert result.handled is False
        assert "HTTP 400" in result.detail
        assert "bad app_id" in result.detail

    def test_openapi_request_reports_network_failure(self, monkeypatch):
        def fake_urlopen(request, timeout):
            raise urllib.error.URLError("timed out")

        monkeypatch.setattr(feishu_bridge.urllib.request, "urlopen", fake_urlopen)

        result = feishu_bridge.openapi_post("/open-apis/test", {"hello": "world"})

        assert result.handled is False
        assert "Feishu OpenAPI failed" in result.detail
        assert "timed out" in result.detail

    def test_openapi_request_rejects_non_json_response(self, monkeypatch):
        monkeypatch.setattr(
            feishu_bridge.urllib.request,
            "urlopen",
            lambda request, timeout: _FakeHTTPResponse("not json"),
        )

        result = feishu_bridge.openapi_post("/open-apis/test", {"hello": "world"})

        assert result.handled is False
        assert "returned non-json" in result.detail
        assert "not json" in result.detail

    def test_send_reply_stops_when_tenant_token_fails(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")
        calls = []

        def fake_openapi_post(path, payload, **kwargs):
            calls.append((path, payload, kwargs))
            return feishu_bridge.BridgeResult(False, "tenant token failed")

        monkeypatch.setattr(feishu_bridge, "openapi_post", fake_openapi_post)

        result = feishu_bridge.send_reply(cfg, "om_1", "处理完成")

        assert result.handled is False
        assert result.detail == "tenant token failed"
        assert [call[0] for call in calls] == ["/open-apis/auth/v3/tenant_access_token/internal"]


class TestRouting:
    def test_bridge_commands_are_namespaced(self):
        assert feishu_bridge.is_bridge_command("/cnb_tui")
        assert feishu_bridge.is_bridge_command("/c_tui please")
        assert feishu_bridge.is_bridge_command("/cnb_watch")
        assert feishu_bridge.is_bridge_command("/cnb_status")
        assert feishu_bridge.is_bridge_command("/c_status")
        assert not feishu_bridge.is_bridge_command("/tui")
        assert not feishu_bridge.is_bridge_command("/watch")

    def test_terminal_supervisor_prompt_describes_async_reply_protocol(self, tmp_path):
        cfg = _cfg(tmp_path)

        prompt = feishu_bridge.build_pilot_system_prompt(cfg)

        assert "实时 TUI" in prompt
        assert 'cnb feishu ask <message_id> "短问题"' in prompt
        assert 'cnb feishu reply <message_id> "回复内容"' in prompt
        assert "不要要求用户记飞书命令" in prompt
        assert "Feishu referenced message" in prompt
        assert "cnb feishu activity" in prompt
        assert "cnb feishu tui" in prompt
        assert "cnb feishu history" in prompt
        assert "readback_enabled=true" in prompt
        assert "伪飞书表情" in feishu_bridge.bridge_affordance_text(cfg)

    def test_terminal_supervisor_prompt_counts_itself_as_running_tongxue(self, tmp_path):
        cfg = _cfg(tmp_path)

        prompt = feishu_bridge.build_pilot_system_prompt(cfg)

        assert "你自己就是一个正在值班的 cnb 同学/负责人实例" in prompt
        assert "必须把你自己算作 1 个正在运行的" in prompt
        assert "设备主管同学" in prompt
        assert "bridge/tunnel/watch 基础设施要分别列出" in prompt

    def test_build_pilot_command_uses_codex(self, tmp_path):
        cfg = _cfg(tmp_path, agent="codex")

        command = feishu_bridge.build_pilot_command(cfg)

        assert command[0] == "codex"
        assert "claude" not in command

    def test_build_pilot_command_uses_claude(self, tmp_path):
        cfg = _cfg(tmp_path, agent="claude")

        command = feishu_bridge.build_pilot_command(cfg)

        assert command[0] == "claude"
        assert "--dangerously-skip-permissions" in command
        assert "--append-system-prompt" in command

    def test_startup_notification_sends_to_chat(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, agent="claude", allowed_chat_ids=frozenset({"oc_notify"}))
        posts = []

        def fake_token(c):
            return feishu_bridge.BridgeResult(True, "fake_token")

        def fake_post(path, payload, *, headers=None):
            posts.append((path, payload))
            return feishu_bridge.BridgeResult(True, '{"code":0}')

        monkeypatch.setattr(feishu_bridge, "tenant_access_token", fake_token)
        monkeypatch.setattr(feishu_bridge, "openapi_post", fake_post)
        monkeypatch.setattr(feishu_bridge, "discover_project_activity", lambda cfg, limit=20: [])

        result = feishu_bridge.send_pilot_startup_notification(cfg)

        assert result.handled is True
        assert len(posts) == 1
        path, payload = posts[0]
        assert "receive_id_type=chat_id" in path
        assert payload["receive_id"] == "oc_notify"
        content = json.loads(payload["content"])
        assert "上线" in content["text"]
        assert "Claude Code" in content["text"]

    def test_startup_notification_skipped_without_chat_id(self, tmp_path):
        cfg = _cfg(tmp_path, allowed_chat_ids=frozenset())

        result = feishu_bridge.send_pilot_startup_notification(cfg)

        assert result.handled is False

    def test_start_pilot_sends_notification(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, pilot_tmux="cnb-notify-test", agent="claude", allowed_chat_ids=frozenset({"oc_test"}))
        notifications = []

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        def fake_notify(c):
            notifications.append(c.pilot_name)
            return feishu_bridge.BridgeResult(True, "sent")

        monkeypatch.setattr(feishu_bridge, "send_pilot_startup_notification", fake_notify)

        result = feishu_bridge.start_pilot_if_needed(cfg)

        assert result.handled is True
        assert len(notifications) == 1

    def test_standby_agent_defaults_to_opposite_engine(self, tmp_path):
        assert feishu_bridge._standby_agent(None, "claude") == "codex"
        assert feishu_bridge._standby_agent(None, "codex") == "claude"
        assert feishu_bridge._standby_agent("codex", "claude") == "codex"

    def test_resolve_standby_tmux(self, tmp_path):
        cfg_default = _cfg(tmp_path, standby_pilot_tmux="")
        cfg_custom = _cfg(tmp_path, standby_pilot_tmux="my-standby")

        assert feishu_bridge.resolve_standby_tmux(cfg_default) == f"{cfg_default.pilot_tmux}-standby"
        assert feishu_bridge.resolve_standby_tmux(cfg_custom) == "my-standby"

    def test_start_standby_disabled(self, tmp_path):
        cfg = _cfg(tmp_path, standby_enabled=False)

        result = feishu_bridge.start_standby_if_needed(cfg)

        assert result.handled is False
        assert "disabled" in result.detail

    def test_start_standby_launches_tmux(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, standby_enabled=True, standby_agent="codex")
        launched = []

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: False)

        def fake_run(cmd, **kwargs):
            launched.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.start_standby_if_needed(cfg)

        assert result.handled is True
        assert any("new-session" in str(c) for c in launched)

    def test_check_pilot_health_detects_trust_prompt(self, tmp_path, monkeypatch):
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout="Do you trust the contents of this directory?\n› 1. Yes, continue\n  2. No, quit\n",
                stderr="",
            )

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.check_pilot_health(_cfg(tmp_path), "cnb-test")

        assert result.handled is False
        assert "trust prompt" in result.detail

    def test_check_pilot_health_healthy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0, stdout="❯ Working on task...\nbypass permissions on\n", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.check_pilot_health(_cfg(tmp_path), "cnb-test")

        assert result.handled is True

    def test_failover_renames_standby_to_primary(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, standby_enabled=True, standby_agent="codex", allowed_chat_ids=frozenset({"oc_test"}))
        renames = []
        kills = []

        def fake_has_session(name):
            standby = feishu_bridge.resolve_standby_tmux(cfg)
            return name == standby

        monkeypatch.setattr(feishu_bridge, "has_session", fake_has_session)
        monkeypatch.setattr(
            feishu_bridge, "send_feishu_notification", lambda c, t: feishu_bridge.BridgeResult(True, "")
        )

        def fake_run(cmd, **kwargs):
            if "rename-session" in cmd:
                renames.append(cmd)
            if "kill-session" in cmd:
                kills.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.failover_to_standby(cfg)

        assert result.handled is True
        assert len(renames) == 1
        assert renames[0][-1] == cfg.pilot_tmux

    def test_heartbeat_dispatches_diagnosis_to_standby(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, standby_enabled=True, standby_agent="codex", allowed_chat_ids=frozenset({"oc_test"}))
        dispatched = []
        feishu_bridge._heartbeat_consecutive_failures = 0

        monkeypatch.setattr(
            feishu_bridge,
            "check_pilot_health",
            lambda c, s=None: feishu_bridge.BridgeResult(False, "stuck at trust prompt"),
        )
        monkeypatch.setattr(
            feishu_bridge, "send_feishu_notification", lambda c, t: feishu_bridge.BridgeResult(True, "")
        )
        monkeypatch.setattr(
            feishu_bridge,
            "dispatch_diagnosis_to_standby",
            lambda c, issue: dispatched.append(issue) or feishu_bridge.BridgeResult(True, "dispatched"),
        )
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)

        result = feishu_bridge.run_heartbeat_check(cfg)

        assert result.handled is True
        assert "diagnosis dispatched" in result.detail
        assert len(dispatched) == 1
        assert "trust prompt" in dispatched[0]

    def test_heartbeat_failover_after_threshold(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, standby_enabled=True, standby_agent="codex", allowed_chat_ids=frozenset({"oc_test"}))
        feishu_bridge._heartbeat_consecutive_failures = feishu_bridge.HEARTBEAT_UNHEALTHY_THRESHOLD - 1

        monkeypatch.setattr(
            feishu_bridge,
            "check_pilot_health",
            lambda c, s=None: feishu_bridge.BridgeResult(False, "still stuck"),
        )
        monkeypatch.setattr(
            feishu_bridge, "send_feishu_notification", lambda c, t: feishu_bridge.BridgeResult(True, "")
        )
        monkeypatch.setattr(
            feishu_bridge,
            "failover_to_standby",
            lambda c: feishu_bridge.BridgeResult(True, "failover done"),
        )
        monkeypatch.setattr(
            feishu_bridge,
            "start_standby_if_needed",
            lambda c: feishu_bridge.BridgeResult(True, "new standby"),
        )
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)

        result = feishu_bridge.run_heartbeat_check(cfg)

        assert result.handled is True
        assert "failover" in result.detail

    def test_build_diagnosis_request_includes_commands(self, tmp_path):
        cfg = _cfg(tmp_path, agent="claude", pilot_tmux="cnb-test")

        request = feishu_bridge.build_diagnosis_request(cfg, "stuck at trust prompt")

        assert "cnb-test" in request
        assert "tmux capture-pane" in request
        assert "cnb feishu reply" in request
        assert "trust prompt" in request

    def test_tunnel_health_skips_non_ngrok_url(self, tmp_path):
        cfg = _cfg(tmp_path, webhook_public_url="https://myserver.example.com/webhook")

        result = feishu_bridge.check_tunnel_health(cfg)

        assert result.handled is True
        assert "non-ngrok" in result.detail

    def test_tunnel_health_restarts_dead_ngrok(self, tmp_path, monkeypatch):
        cfg = _cfg(
            tmp_path, webhook_public_url="https://abc.ngrok-free.app", webhook_host="127.0.0.1", webhook_port=8787
        )
        restarts = []

        monkeypatch.setattr(feishu_bridge, "ngrok_public_url_for", lambda h, p: "")
        monkeypatch.setattr(
            feishu_bridge,
            "ensure_tunnel",
            lambda h, p: restarts.append(1) or feishu_bridge.BridgeResult(True, "https://new.ngrok-free.app"),
        )
        monkeypatch.setattr(
            feishu_bridge, "send_feishu_notification", lambda c, t: feishu_bridge.BridgeResult(True, "")
        )
        monkeypatch.setattr(feishu_bridge, "_update_config_url", lambda c, u: None)

        result = feishu_bridge.check_tunnel_health(cfg)

        assert result.handled is True
        assert len(restarts) == 1
        assert "restarted" in result.detail

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
        assert ("cnb-pilot-test", feishu_bridge.format_for_pilot(event, cfg)) in calls

    def test_route_event_hands_image_file_path_to_pilot(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        payload = {
            "message_id": "om_img",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "message_type": "image",
            "content": json.dumps({"image_key": "img_1"}),
        }
        event = feishu_bridge.extract_event(payload)
        sent = []
        image_path = tmp_path / "feishu.png"

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)
        monkeypatch.setattr(feishu_bridge, "tmux_send", lambda name, text: sent.append((name, text)) or True)
        monkeypatch.setattr(
            feishu_bridge,
            "download_message_resource_openapi",
            lambda cfg, message_id, resource: feishu_bridge.ResourceDownloadResult(
                True, "downloaded", str(image_path), "image/png", 7
            ),
        )

        result = feishu_bridge.route_event(event, cfg)

        assert result.handled is True
        routed = sent[0][1]
        assert "[Feishu resources handed to Claude Code]" in routed
        assert str(image_path) in routed
        assert "image/png" in routed
        assert "直接读取路径/链接" in routed

    def test_route_event_hands_doc_links_without_downloading(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        doc_url = "https://example.feishu.cn/docx/doccn123"
        payload = {
            "message_id": "om_text",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "message_type": "text",
            "content": json.dumps({"text": f"看这个 [需求文档]({doc_url})"}, ensure_ascii=False),
        }
        event = feishu_bridge.extract_event(payload)
        sent = []

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)
        monkeypatch.setattr(feishu_bridge, "tmux_send", lambda name, text: sent.append(text) or True)
        monkeypatch.setattr(
            feishu_bridge,
            "download_message_resource_openapi",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("download should not run")),
        )

        result = feishu_bridge.route_event(event, cfg)

        assert result.handled is True
        assert "链接：" in sent[0]
        assert doc_url in sent[0]

    def test_format_for_pilot_includes_capabilities_not_keyword_intents(self, tmp_path):
        cfg = _cfg(tmp_path)
        event = FeishuInboundEvent(
            text="随便问一个自然语言需求",
            message_id="om_1",
            parent_id="om_parent",
            root_id="om_root",
            thread_id="omt_thread",
            chat_id="oc_allowed",
        )

        formatted = feishu_bridge.format_for_pilot(
            event, cfg, reference_summary="om_parent app:ou_bot text: 前一条回复"
        )

        assert "[CNB bridge affordances]" in formatted
        assert "parent_message_id: om_parent" in formatted
        assert "root_message_id: om_root" in formatted
        assert "thread_id: omt_thread" in formatted
        assert "[Feishu referenced message]" in formatted
        assert "前一条回复" in formatted
        assert "不要要求用户记命令" in formatted
        assert "cnb feishu activity" in formatted
        assert "inspect-message" in formatted
        assert "不要默认读取聊天历史" in formatted
        assert "随便问一个自然语言需求" in formatted

    def test_handle_payload_starts_activity_monitor_after_ack_in_live_policy(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, ack=True, notification_policy="live")
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"run tests"}',
        }
        monitors = []

        monkeypatch.setattr(
            feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running")
        )
        monkeypatch.setattr(feishu_bridge, "tmux_send", lambda name, text: True)
        monkeypatch.setattr(
            feishu_bridge, "reply_ack", lambda event, cfg, detail: feishu_bridge.BridgeResult(True, "ack")
        )
        monkeypatch.setattr(
            feishu_bridge,
            "start_activity_monitor",
            lambda event, cfg: (
                monitors.append((event.message_id, cfg.pilot_tmux)) or feishu_bridge.BridgeResult(True, "monitor")
            ),
        )

        result = feishu_bridge.handle_payload(payload, cfg)

        assert result.handled is True
        assert monitors == [("om_1", "cnb-device-supervisor")]

    def test_handle_payload_final_only_suppresses_progress_pushes(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, ack=True, notification_policy="final_only")
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"run tests"}',
        }
        calls = []

        monkeypatch.setattr(
            feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running")
        )
        monkeypatch.setattr(feishu_bridge, "tmux_send", lambda name, text: True)
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda *args, **kwargs: calls.append(args) or feishu_bridge.BridgeResult(True, "sent"),
        )
        monkeypatch.setattr(
            feishu_bridge,
            "send_activity_update",
            lambda *args, **kwargs: calls.append(args) or feishu_bridge.BridgeResult(True, "activity"),
        )

        result = feishu_bridge.handle_payload(payload, cfg)

        assert result.handled is True
        assert result.detail == "delivered to cnb-device-supervisor"
        assert calls == []

    def test_cnb_tui_command_replies_with_snapshot(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        replies = []
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"/cnb_tui"}',
        }

        monkeypatch.setattr(
            feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running")
        )
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda cfg, mid, text, **kwargs: replies.append((mid, text)) or feishu_bridge.BridgeResult(True, "sent"),
        )

        def fake_run(cmd, **kwargs):
            assert cmd[:3] == ["tmux", "capture-pane", "-t"]
            return SimpleNamespace(returncode=0, stdout="Codex screen\nReady", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)

        result = feishu_bridge.handle_payload(payload, cfg)

        assert result.handled is True
        assert replies[0][0] == "om_1"
        assert "Codex screen" in replies[0][1]

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

        monkeypatch.setattr(
            feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running")
        )
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

    def test_cnb_status_command_replies_with_activity_summary(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        replies = []
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"/cnb_status"}',
        }

        monkeypatch.setattr(
            feishu_bridge,
            "describe_activity",
            lambda cfg: "- 设备主管同学：online\n- 团队工作面：busy\n- 用户前台 CLI：codex",
        )
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda cfg, mid, text, **kwargs: replies.append(text) or feishu_bridge.BridgeResult(True, "sent"),
        )

        result = feishu_bridge.handle_payload(payload, cfg)

        assert result.handled is True
        assert "CNB 设备状态" in replies[0]
        assert "团队工作面" in replies[0]

    def test_activity_cli_prints_current_screen(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / "config.toml"
        path.write_text("[feishu]\n")
        monkeypatch.setattr(feishu_bridge, "build_activity_reply", lambda cfg: "Codex 实时一屏\n```text\nok\n```")

        code = feishu_bridge.main(["--config", str(path), "activity"])

        assert code == 0
        assert "Codex 实时一屏" in capsys.readouterr().out

    def test_start_watch_viewer_uses_ttyd_readonly(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, watch_tmux="cnb-watch-test", watch_tool="ttyd")
        calls = []

        monkeypatch.setattr(
            feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running")
        )
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
        assert "tmux attach-session -t cnb-device-supervisor" in command

    def test_start_watch_viewer_existing_session_reports_configured_port(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, watch_tmux="cnb-watch-test", watch_port=8765)

        monkeypatch.setattr(
            feishu_bridge, "start_pilot_if_needed", lambda cfg: feishu_bridge.BridgeResult(True, "running")
        )
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: name == "cnb-watch-test")
        monkeypatch.setattr(feishu_bridge, "_port_available", lambda host, port: False)

        result = feishu_bridge.start_watch_viewer(cfg)

        assert result.handled is True
        assert "127.0.0.1:8765" in result.detail
        assert "8766" not in result.detail

    def test_watch_url_appends_token_without_replacing_existing_query(self, tmp_path):
        cfg = _cfg(tmp_path, watch_public_url="https://watch.example.test/view?from=feishu", watch_token="secret")

        url = feishu_bridge.watch_url(cfg, 8765)

        assert url == "https://watch.example.test/view?from=feishu&token=secret"
        assert feishu_bridge.redacted_watch_url(url, "secret") == (
            "https://watch.example.test/view?from=feishu&token=%3Credacted%3E"
        )

    def test_watch_route_accepts_prefixed_public_paths(self):
        assert feishu_bridge.watch_route("/watch?token=x") == ("page", "/watch")
        assert feishu_bridge.watch_route("/cnb/feishu/watch?token=x") == ("page", "/cnb/feishu/watch")
        assert feishu_bridge.watch_route("/cnb/feishu/watch/snapshot?token=x") == (
            "snapshot",
            "/cnb/feishu/watch/snapshot",
        )

    def test_watch_request_requires_configured_token(self, tmp_path):
        cfg = _cfg(tmp_path, watch_token="secret")

        assert feishu_bridge.watch_request_authorized("/?token=wrong", {}, cfg) is False
        assert feishu_bridge.watch_request_authorized("/?token=secret", {}, cfg) is True
        assert feishu_bridge.watch_request_authorized("/", {"Authorization": "Bearer secret"}, cfg) is True
        assert feishu_bridge.watch_request_authorized("/", {}, _cfg(tmp_path), require_token=True) is False

    def test_watch_page_html_contains_snapshot_endpoint(self, tmp_path):
        cfg = _cfg(tmp_path)

        page = feishu_bridge.watch_page_html(cfg)

        assert "/snapshot" in page
        assert cfg.pilot_tmux in page
        assert "const REFRESH_MS = 250" in page
        assert "nearBottom()" in page
        assert "scrollToBottom" in page
        assert "text !== lastText" in page

    def test_watch_page_html_uses_tokenized_snapshot_endpoint(self, tmp_path):
        cfg = _cfg(tmp_path, watch_token="secret")

        page = feishu_bridge.watch_page_html(cfg, snapshot_url="/watch/snapshot?token=secret")

        assert 'fetch("/watch/snapshot?token=secret"' in page

    def test_watch_page_html_embedded_removes_header_chrome(self, tmp_path):
        cfg = _cfg(tmp_path)

        page = feishu_bridge.watch_page_html(cfg, embedded=True)

        assert "<header>" not in page
        assert "min-height: 100vh" in page
        assert "if (meta) meta.textContent" in page

    def test_handle_payload_dry_run_prints_message(self, tmp_path, capsys):
        cfg = _cfg(tmp_path)
        payload = {
            "message_id": "om_1",
            "parent_id": "om_parent",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"ping"}',
        }

        result = feishu_bridge.handle_payload(payload, cfg, dry_run=True)

        out = capsys.readouterr().out
        assert result.handled is True
        assert "[Feishu inbound]" in out
        assert "parent_message_id: om_parent" in out
        assert "ping" in out

    def test_handle_payload_dry_run_does_not_fetch_message_reference(self, tmp_path, monkeypatch, capsys):
        cfg = _cfg(tmp_path)
        payload = {
            "message_id": "om_1",
            "parent_id": "om_parent",
            "chat_id": "oc_allowed",
            "sender_id": "ou_user",
            "content": '{"text":"ping"}',
        }

        monkeypatch.setattr(
            feishu_bridge,
            "resolve_message_reference",
            lambda event, cfg: (_ for _ in ()).throw(AssertionError("dry-run fetched reference")),
        )

        result = feishu_bridge.handle_payload(payload, cfg, dry_run=True)

        out = capsys.readouterr().out
        assert result.handled is True
        assert "parent_message_id: om_parent" in out

    def test_handle_payload_auto_binds_first_chat(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        path.write_text("[feishu]\nauto_bind_chat = true\nack = false\n")
        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)
        payload = {
            "message_id": "om_1",
            "chat_id": "oc_first",
            "sender_id": "ou_user",
            "content": '{"text":"ping"}',
        }
        calls = []

        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)
        monkeypatch.setattr(feishu_bridge, "tmux_send", lambda name, text: calls.append((name, text)) or True)

        result = feishu_bridge.handle_payload(payload, cfg)

        written = path.read_text()
        assert result.handled is True
        assert 'chat_id = "oc_first"' in written
        assert "auto_bind_chat = false" in written
        assert calls

    def test_history_readback_refuses_when_disabled(self, tmp_path):
        cfg = _cfg(tmp_path)

        result = feishu_bridge.build_history_readback(cfg, limit=3)

        assert result.handled is False
        assert "回读未启用" in result.detail

    def test_history_readback_fetches_allowed_chat(self, tmp_path, monkeypatch):
        cfg = _cfg(
            tmp_path,
            app_id="cli_bot",
            app_secret="secret",
            readback_enabled=True,
            readback_default_limit=4,
        )
        calls = []

        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_openapi_get(path, **kwargs):
            calls.append((path, kwargs))
            return feishu_bridge.BridgeResult(
                True,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "has_more": False,
                            "items": [
                                {
                                    "message_id": "om_new",
                                    "msg_type": "text",
                                    "create_time": "1778361600000",
                                    "sender": {"sender_type": "user", "id": "ou_user"},
                                    "body": {"content": json.dumps({"text": "刚才没收到回复？"}, ensure_ascii=False)},
                                    "chat_id": "oc_allowed",
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            )

        monkeypatch.setattr(feishu_bridge, "openapi_get", fake_openapi_get)

        result = feishu_bridge.build_history_readback(cfg, limit=2)

        assert result.handled is True
        assert calls[0][0] == "/open-apis/im/v1/messages"
        assert calls[0][1]["headers"] == {"Authorization": "Bearer t-token"}
        assert calls[0][1]["params"]["container_id_type"] == "chat"
        assert calls[0][1]["params"]["container_id"] == "oc_allowed"
        assert calls[0][1]["params"]["sort_type"] == "ByCreateTimeDesc"
        assert calls[0][1]["params"]["page_size"] == "2"
        assert "飞书回读：chat oc_allowed" in result.detail
        assert "刚才没收到回复" in result.detail

    def test_history_readback_rejects_unlisted_explicit_chat(self, tmp_path):
        cfg = _cfg(tmp_path, readback_enabled=True)

        result = feishu_bridge.build_history_readback(cfg, chat_id="oc_other")

        assert result.handled is False
        assert "不在回读 allowlist" in result.detail

    def test_download_message_resource_uses_message_resource_api(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_bot", app_secret="secret")
        calls = []

        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_download(path, **kwargs):
            calls.append((path, kwargs))
            return feishu_bridge.ResourceDownloadResult(True, "downloaded", str(tmp_path / "img_1.png"), "image/png", 3)

        monkeypatch.setattr(feishu_bridge, "openapi_download", fake_download)

        result = feishu_bridge.download_message_resource_openapi(
            cfg,
            "om_img",
            {"kind": "image", "key": "img_1", "file_name": "", "source": "image"},
        )

        assert result.handled is True
        assert calls[0][0] == "/open-apis/im/v1/messages/om_img/resources/img_1"
        assert calls[0][1]["params"] == {"type": "image"}
        assert calls[0][1]["headers"] == {"Authorization": "Bearer t-token"}
        assert calls[0][1]["output_dir"].name == "om_img"

    def test_inspect_message_readback_fetches_bot_read_users(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_bot", app_secret="secret", readback_enabled=True)
        calls = []

        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_openapi_get(path, **kwargs):
            calls.append((path, kwargs))
            if path.endswith("/read_users"):
                return feishu_bridge.BridgeResult(
                    True,
                    json.dumps(
                        {
                            "code": 0,
                            "data": {
                                "items": [
                                    {
                                        "user_id_type": "open_id",
                                        "user_id": "ou_reader",
                                        "timestamp": "1778361600000",
                                    }
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                )
            return feishu_bridge.BridgeResult(
                True,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "items": [
                                {
                                    "message_id": "om_bot",
                                    "msg_type": "text",
                                    "create_time": "1778361500000",
                                    "sender": {"sender_type": "app", "id": "cli_bot"},
                                    "body": {"content": json.dumps({"text": "处理完成"}, ensure_ascii=False)},
                                    "chat_id": "oc_allowed",
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
            )

        monkeypatch.setattr(feishu_bridge, "openapi_get", fake_openapi_get)

        result = feishu_bridge.inspect_message_readback(cfg, "om_bot")

        assert result.handled is True
        assert calls[0][0] == "/open-apis/im/v1/messages/om_bot"
        assert calls[1][0] == "/open-apis/im/v1/messages/om_bot/read_users"
        assert calls[1][1]["params"]["user_id_type"] == "open_id"
        assert "发送者：当前机器人" in result.detail
        assert "已读状态：1 个已读用户" in result.detail
        assert "ou_reader" in result.detail

    def test_inspect_message_readback_hands_file_path_to_cli_output(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_bot", app_secret="secret", readback_enabled=True)
        file_path = tmp_path / "report.pdf"

        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_openapi_get(path, **kwargs):
            return feishu_bridge.BridgeResult(
                True,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "items": [
                                {
                                    "message_id": "om_file",
                                    "msg_type": "file",
                                    "sender": {"sender_type": "user", "id": "ou_user"},
                                    "body": {
                                        "content": json.dumps(
                                            {"file_key": "file_1", "file_name": "report.pdf"}, ensure_ascii=False
                                        )
                                    },
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
            )

        monkeypatch.setattr(feishu_bridge, "openapi_get", fake_openapi_get)
        monkeypatch.setattr(
            feishu_bridge,
            "download_message_resource_openapi",
            lambda cfg, message_id, resource: feishu_bridge.ResourceDownloadResult(
                True, "downloaded", str(file_path), "application/pdf", 11
            ),
        )

        result = feishu_bridge.inspect_message_readback(cfg, "om_file")

        assert result.handled is True
        assert "资源/链接交接" in result.detail
        assert str(file_path) in result.detail
        assert "application/pdf" in result.detail

    def test_inspect_message_readback_reports_read_user_permission_error(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_bot", app_secret="secret", readback_enabled=True)

        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_openapi_get(path, **kwargs):
            if path.endswith("/read_users"):
                return feishu_bridge.BridgeResult(False, "Feishu OpenAPI error: lack permissions")
            return feishu_bridge.BridgeResult(
                True,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "items": [
                                {
                                    "message_id": "om_bot",
                                    "msg_type": "text",
                                    "sender": {"sender_type": "app", "id": "cli_bot"},
                                    "body": {"content": json.dumps({"text": "处理完成"}, ensure_ascii=False)},
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
            )

        monkeypatch.setattr(feishu_bridge, "openapi_get", fake_openapi_get)

        result = feishu_bridge.inspect_message_readback(cfg, "om_bot")

        assert result.handled is True
        assert "已读状态不可用" in result.detail
        assert "lack permissions" in result.detail

    def test_reply_ack_uses_hermes_lark_cli_when_configured(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, ack=True, notification_policy="ack", transport="hermes_lark_cli")
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

    def test_send_short_reply_sends_non_final_request(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        calls = []

        def fake_send_reply(cfg, message_id, text, *, idempotency_key=""):
            calls.append((message_id, text, idempotency_key))
            return feishu_bridge.BridgeResult(True, "reply sent")

        monkeypatch.setattr(feishu_bridge, "send_reply", fake_send_reply)

        result = feishu_bridge.send_short_reply(cfg, "om_1", "需要你确认是否重启服务？")

        assert result.handled is True
        assert "activity remains open" in result.detail
        assert len(calls) == 1
        assert calls[0][:2] == ("om_1", "需要你确认是否重启服务？")
        assert calls[0][2].startswith("cnb-feishu-ask-")

    def test_send_short_reply_rejects_long_text_and_code_blocks(self, tmp_path):
        cfg = _cfg(tmp_path)

        too_long = "x" * (feishu_bridge.SHORT_REPLY_MAX_CHARS + 1)

        long_result = feishu_bridge.send_short_reply(cfg, "om_1", too_long)
        code_result = feishu_bridge.send_short_reply(cfg, "om_1", "请看：\n```text\nabc\n```")

        assert long_result.handled is False
        assert "too long" in long_result.detail
        assert code_result.handled is False
        assert "fenced code" in code_result.detail

    def test_send_reply_sends_plain_text_via_local_openapi(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        calls = []

        def fake_openapi_post(path, payload, **kwargs):
            calls.append((path, payload, kwargs))
            if path.endswith("/tenant_access_token/internal"):
                return feishu_bridge.BridgeResult(True, '{"code":0,"tenant_access_token":"t-token"}')
            return feishu_bridge.BridgeResult(True, '{"code":0}')

        monkeypatch.setattr(feishu_bridge, "openapi_post", fake_openapi_post)
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")

        result = feishu_bridge.send_reply(cfg, "om_1", "处理完成")

        assert result.handled is True
        assert calls[1][0] == "/open-apis/im/v1/messages/om_1/reply"
        assert calls[1][1]["msg_type"] == "text"
        assert "处理完成" in calls[1][1]["content"]

    def test_send_reply_sends_code_fence_as_post_via_local_openapi(self, tmp_path, monkeypatch):
        calls = []

        def fake_openapi_post(path, payload, **kwargs):
            calls.append((path, payload, kwargs))
            if path.endswith("/tenant_access_token/internal"):
                return feishu_bridge.BridgeResult(True, '{"code":0,"tenant_access_token":"t-token"}')
            return feishu_bridge.BridgeResult(True, '{"code":0}')

        monkeypatch.setattr(feishu_bridge, "openapi_post", fake_openapi_post)
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")

        result = feishu_bridge.send_reply(cfg, "om_1", "说明\n\n```python\nprint('hi')\n```\n\n完成")

        assert result.handled is True
        assert calls[1][0] == "/open-apis/im/v1/messages/om_1/reply"
        assert calls[1][1]["msg_type"] == "post"
        content = json.loads(calls[1][1]["content"])
        assert content["zh_cn"]["content"][0][0]["tag"] == "md"
        assert "```python\nprint('hi')\n```" in content["zh_cn"]["content"][0][0]["text"]

    def test_send_reply_sends_markdown_summary_as_post_via_local_openapi(self, tmp_path, monkeypatch):
        calls = []

        def fake_openapi_post(path, payload, **kwargs):
            calls.append((path, payload, kwargs))
            if path.endswith("/tenant_access_token/internal"):
                return feishu_bridge.BridgeResult(True, '{"code":0,"tenant_access_token":"t-token"}')
            return feishu_bridge.BridgeResult(True, '{"code":0}')

        monkeypatch.setattr(feishu_bridge, "openapi_post", fake_openapi_post)
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")

        result = feishu_bridge.send_reply(
            cfg,
            "om_1",
            "**完成**\n\n- 修复 `activity` 渲染\n- 文档见 [README](https://example.test)",
        )

        assert result.handled is True
        assert calls[1][1]["msg_type"] == "post"
        content = json.loads(calls[1][1]["content"])
        node = content["zh_cn"]["content"][0][0]
        assert node["tag"] == "md"
        assert "- 修复 `activity` 渲染" in node["text"]

    def test_resolve_message_reference_fetches_parent_message(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")
        event = FeishuInboundEvent(
            text="继续",
            message_id="om_child",
            parent_id="om_parent",
            root_id="om_root",
            chat_id="oc_allowed",
        )
        calls = []

        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_openapi_get(path, **kwargs):
            calls.append((path, kwargs))
            return feishu_bridge.BridgeResult(
                True,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "items": [
                                {
                                    "message_id": "om_parent",
                                    "msg_type": "text",
                                    "sender": {"sender_type": "app", "id": "ou_bot"},
                                    "body": {"content": json.dumps({"text": "前一条回复"}, ensure_ascii=False)},
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
            )

        monkeypatch.setattr(feishu_bridge, "openapi_get", fake_openapi_get)

        summary = feishu_bridge.resolve_message_reference(event, cfg)

        assert calls[0][0] == "/open-apis/im/v1/messages/om_parent"
        assert calls[0][1]["params"]["card_msg_content_type"] == "user_card_content"
        assert summary == "om_parent app:ou_bot text: 前一条回复"

    def test_summarize_openapi_message_handles_interactive_cards(self):
        summary = feishu_bridge.summarize_openapi_message(
            json.dumps(
                {
                    "code": 0,
                    "data": {
                        "items": [
                            {
                                "message_id": "om_card",
                                "msg_type": "interactive",
                                "sender": {"sender_type": "app", "id": "ou_bot"},
                                "body": {
                                    "content": json.dumps(
                                        {
                                            "schema": "2.0",
                                            "header": {"title": {"tag": "plain_text", "content": "Codex 设备活动"}},
                                            "body": {
                                                "elements": [
                                                    {"tag": "markdown", "content": "**设备主管同学**\n正在运行"}
                                                ]
                                            },
                                        },
                                        ensure_ascii=False,
                                    )
                                },
                            }
                        ]
                    },
                },
                ensure_ascii=False,
            )
        )

        assert "om_card app:ou_bot interactive" in summary
        assert "Codex 设备活动" in summary
        assert "设备主管同学" in summary

    def test_activity_state_marks_done(self, tmp_path):
        cfg = _cfg(tmp_path)
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed", sender_id="ou_user")

        feishu_bridge.record_activity_start(cfg, event)

        assert feishu_bridge.activity_is_done(cfg, "om_1") is False

        feishu_bridge.mark_activity_done(cfg, "om_1")

        assert feishu_bridge.activity_is_done(cfg, "om_1") is True

    def test_send_activity_update_builds_one_screen_snapshot(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, agent="codex")
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed", sender_id="ou_user")
        snapshots = []

        feishu_bridge.record_activity_start(cfg, event)
        monkeypatch.setattr(feishu_bridge, "has_session", lambda name: True)

        def fake_run(cmd, **kwargs):
            assert cmd[:3] == ["tmux", "capture-pane", "-t"]
            assert "-S" not in cmd
            return SimpleNamespace(returncode=0, stdout="Codex screen\n• Working (12s)\n", stderr="")

        monkeypatch.setattr(feishu_bridge.subprocess, "run", fake_run)
        monkeypatch.setattr(
            feishu_bridge,
            "send_activity_card",
            lambda cfg, event, snapshot: snapshots.append(snapshot) or feishu_bridge.BridgeResult(True, "sent"),
        )

        result = feishu_bridge.send_activity_update(cfg, event, 20)

        assert result.handled is True
        text = feishu_bridge.render_activity_snapshot_text(snapshots[0])
        assert snapshots[0].style == "codex"
        assert snapshots[0].elapsed_seconds == 20
        assert snapshots[0].title == "20s"
        assert "Codex screen" in text
        assert "Working" in text
        assert "CNB tmux" not in text
        assert "团队工作面" not in text

    def test_activity_card_uses_feishu_interactive_schema(self, tmp_path):
        cfg = _cfg(tmp_path, activity_render_style="claude")
        snapshot = feishu_bridge.ActivitySnapshot(
            title="Claude Code 设备活动 · 20s",
            subtitle="状态摘要",
            sections=(feishu_bridge.ActivitySection("设备主管同学", "正在运行；等待回复"),),
            style=feishu_bridge.resolve_activity_render_style(cfg),
            elapsed_seconds=20,
            updated_at="2026-05-10 06:30:00",
        )

        card = feishu_bridge.build_activity_card(snapshot)

        assert card["schema"] == "2.0"
        assert card["config"]["update_multi"] is True
        assert card["config"]["style"]["text_size"]["normal_v2"]["mobile"] == "heading"
        assert card["header"]["template"] == "purple"
        assert card["header"]["subtitle"]["content"] == ""
        rendered = "\n".join(item.get("content", "") for item in card["body"]["elements"])
        assert "设备主管同学" in rendered
        assert "- 正在运行" in rendered
        assert "- 等待回复" in rendered

    def test_activity_card_screen_mode_only_renders_current_screen(self, tmp_path):
        cfg = _cfg(tmp_path, agent="codex")
        snapshot = feishu_bridge.ActivitySnapshot(
            title="20s",
            subtitle="设备主管同学当前 TUI 画面",
            sections=(feishu_bridge.ActivitySection("当前一屏", "Codex screen\n• Working", "screen"),),
            style=feishu_bridge.resolve_activity_render_style(cfg),
            elapsed_seconds=20,
            updated_at="2026-05-10 06:30:00",
        )

        card = feishu_bridge.build_activity_card(snapshot)

        rendered = "\n".join(item.get("content", "") for item in card["body"]["elements"])
        assert card["header"]["title"]["content"] == "20s"
        assert "Codex screen" in rendered
        assert "最后 2 行" in rendered
        assert "<font color='grey'>01</font>" in rendered
        assert "```text" not in rendered
        assert "Codex run-loop snapshot" not in rendered
        assert "CNB tmux" not in rendered

    def test_activity_card_screen_mode_keeps_mobile_tail_readable(self, tmp_path):
        cfg = _cfg(tmp_path, agent="codex")
        body = "\n".join(f"line {i:02d} with `code` and *stars*" for i in range(1, 16))
        snapshot = feishu_bridge.ActivitySnapshot(
            title="Codex 实时一屏 · 1s",
            subtitle="设备主管同学当前 TUI 画面",
            sections=(feishu_bridge.ActivitySection("当前一屏", body, "screen"),),
            style=feishu_bridge.resolve_activity_render_style(cfg),
            elapsed_seconds=1,
            updated_at="2026-05-10 06:30:00",
        )

        card = feishu_bridge.build_activity_card(snapshot)

        rendered = "\n".join(item.get("content", "") for item in card["body"]["elements"])
        assert "已省略上方 3 行" in rendered
        assert "line 04" in rendered
        assert "line 15" in rendered
        assert "line 01" not in rendered
        assert "\\`code\\`" in rendered
        assert "\\*stars\\*" in rendered

    def test_activity_update_schedule_repeats_after_configured_points(self, tmp_path):
        cfg = _cfg(tmp_path, activity_update_seconds=(20, 60, 180), activity_update_repeat_seconds=60)

        elapsed = list(itertools.islice(feishu_bridge.iter_activity_update_elapsed_seconds(cfg), 6))

        assert elapsed == [20, 60, 180, 240, 300, 360]

    def test_first_activity_card_reply_records_message_id(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed", sender_id="ou_user")
        snapshot = feishu_bridge.ActivitySnapshot(
            title="Codex 设备活动 · 20s",
            subtitle="状态摘要",
            sections=(feishu_bridge.ActivitySection("设备主管同学", "正在运行"),),
            style="codex",
            elapsed_seconds=20,
            updated_at="2026-05-10 06:30:00",
        )
        calls = []

        feishu_bridge.record_activity_start(cfg, event)

        def fake_openapi_post(path, payload, **kwargs):
            calls.append((path, payload, kwargs))
            if path.endswith("/tenant_access_token/internal"):
                return feishu_bridge.BridgeResult(True, '{"code":0,"tenant_access_token":"t-token"}')
            return feishu_bridge.BridgeResult(True, '{"code":0,"data":{"message_id":"om_status"}}')

        monkeypatch.setattr(feishu_bridge, "openapi_post", fake_openapi_post)

        result = feishu_bridge.send_activity_card(cfg, event, snapshot)

        assert result.handled is True
        assert calls[1][0] == "/open-apis/im/v1/messages/om_1/reply"
        assert calls[1][1]["msg_type"] == "interactive"
        content = json.loads(calls[1][1]["content"])
        assert content["config"]["update_multi"] is True
        assert feishu_bridge.activity_update_message_id(cfg, "om_1") == "om_status"

    def test_later_activity_card_updates_existing_message(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, app_id="cli_x", app_secret="secret")
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed", sender_id="ou_user")
        snapshot = feishu_bridge.ActivitySnapshot(
            title="Codex 设备活动 · 60s",
            subtitle="状态摘要",
            sections=(feishu_bridge.ActivitySection("设备主管同学", "仍在运行"),),
            style="codex",
            elapsed_seconds=60,
            updated_at="2026-05-10 06:31:00",
        )
        calls = []

        feishu_bridge.record_activity_start(cfg, event)
        feishu_bridge.record_activity_update_message(cfg, "om_1", "om_status")
        monkeypatch.setattr(
            feishu_bridge, "tenant_access_token", lambda cfg: feishu_bridge.BridgeResult(True, "t-token")
        )

        def fake_openapi_request(method, path, payload, **kwargs):
            calls.append((method, path, payload, kwargs))
            return feishu_bridge.BridgeResult(True, '{"code":0}')

        monkeypatch.setattr(feishu_bridge, "openapi_request", fake_openapi_request)

        result = feishu_bridge.send_activity_card(cfg, event, snapshot)

        assert result.handled is True
        assert len(calls) == 1
        assert calls[0][0] == "PATCH"
        assert calls[0][1] == "/open-apis/im/v1/messages/om_status"
        assert calls[0][3] == {"headers": {"Authorization": "Bearer t-token"}}
        assert json.loads(calls[0][2]["content"])["config"]["update_multi"] is True

    def test_describe_cnb_tmux_sessions_separates_infra_and_legacy(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, pilot_tmux="cnb-device-supervisor")
        monkeypatch.setattr(
            feishu_bridge,
            "_tmux_session_names",
            lambda: {"cnb-device-supervisor", "cnb-feishu-bridge", "cnb-feishu-watch", "cnb-codex-lead"},
        )

        summary = feishu_bridge.describe_cnb_tmux_sessions(cfg)

        assert "设备主管 cnb-device-supervisor" in summary
        assert "基础服务 cnb-feishu-bridge, cnb-feishu-watch" in summary
        assert "其他/遗留 cnb-codex-lead" in summary

    def test_foreground_agent_sessions_excludes_tmux_and_child_processes(self, monkeypatch):
        rows = [
            {"pid": 10, "ppid": 1, "tty": "??", "stat": "Ss", "comm": "tmux", "args": "tmux new-session"},
            {
                "pid": 20,
                "ppid": 10,
                "tty": "ttys005",
                "stat": "S+",
                "comm": "node",
                "args": "node /opt/homebrew/bin/codex --cd /repo",
            },
            {
                "pid": 21,
                "ppid": 20,
                "tty": "ttys005",
                "stat": "S+",
                "comm": "codex",
                "args": "/vendor/codex --cd /repo",
            },
            {
                "pid": 30,
                "ppid": 2,
                "tty": "ttys010",
                "stat": "S+",
                "comm": "node",
                "args": "node /opt/homebrew/bin/codex resume abc",
            },
            {
                "pid": 31,
                "ppid": 30,
                "tty": "ttys010",
                "stat": "S+",
                "comm": "codex",
                "args": "/vendor/codex resume abc",
            },
        ]

        monkeypatch.setattr(feishu_bridge, "_process_rows", lambda: rows)
        monkeypatch.setattr(feishu_bridge, "_process_cwd", lambda pid: "/manual")

        sessions = feishu_bridge.foreground_agent_sessions()

        assert sessions == [
            {
                "engine": "codex",
                "pid": "30",
                "tty": "ttys010",
                "cwd": "/manual",
                "command": "resume",
            }
        ]

    def test_reply_command_marks_activity_done(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        path.write_text("[feishu]\n")
        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed")
        feishu_bridge.record_activity_start(cfg, event)
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda cfg, mid, text, *, idempotency_key="": feishu_bridge.BridgeResult(True, "reply sent"),
        )

        code = feishu_bridge.main(["--config", str(path), "reply", "om_1", "done"])

        assert code == 0
        assert feishu_bridge.activity_is_done(cfg, "om_1") is True
        state = json.loads(feishu_bridge.activity_state_path(cfg).read_text())
        item = state["messages"]["om_1"]
        assert item["final_reply_result"] == "reply sent"
        assert item["final_reply_transport"] == cfg.transport
        assert item["done_at"] == item["final_reply_sent_at"]

    def test_reply_command_keeps_activity_open_when_send_fails(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / "config.toml"
        path.write_text("[feishu]\n")
        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed")
        feishu_bridge.record_activity_start(cfg, event)
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda cfg, mid, text, *, idempotency_key="": feishu_bridge.BridgeResult(False, "network down"),
        )

        code = feishu_bridge.main(["--config", str(path), "reply", "om_1", "done"])

        captured = capsys.readouterr()
        assert code == 1
        assert feishu_bridge.activity_is_done(cfg, "om_1") is False
        assert "activity remains open" in captured.out
        assert "final Feishu reply failed: network down" in captured.err
        state = json.loads(feishu_bridge.activity_state_path(cfg).read_text())
        item = state["messages"]["om_1"]
        assert item["blocked_at"]
        assert item["blocked_reason"] == "final Feishu reply failed: network down"

    def test_final_reply_uses_idempotency_key(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path)
        calls = []
        monkeypatch.setattr(
            feishu_bridge,
            "send_reply",
            lambda cfg, mid, text, *, idempotency_key="": (
                calls.append(idempotency_key) or feishu_bridge.BridgeResult(True, "reply sent")
            ),
        )

        result = feishu_bridge.send_final_reply(cfg, "om_1", "done")

        assert result.handled is True
        assert calls == [feishu_bridge._final_reply_key("om_1", "done")]

    def test_ask_command_keeps_activity_open(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        path.write_text("[feishu]\n")
        cfg = FeishuBridgeConfig.load(config_path=path, project_root=tmp_path)
        event = FeishuInboundEvent(text="ping", message_id="om_1", chat_id="oc_allowed")
        calls = []
        feishu_bridge.record_activity_start(cfg, event)
        monkeypatch.setattr(
            feishu_bridge,
            "send_short_reply",
            lambda cfg, mid, text: calls.append((mid, text)) or feishu_bridge.BridgeResult(True, "short reply sent"),
        )

        code = feishu_bridge.main(["--config", str(path), "ask", "om_1", "need", "input"])

        assert code == 0
        assert calls == [("om_1", "need input")]
        assert feishu_bridge.activity_is_done(cfg, "om_1") is False

    def test_url_verification_returns_challenge(self, tmp_path):
        cfg = _cfg(tmp_path, verification_token="token")

        status, response, result = feishu_bridge.handle_webhook_payload(
            {"type": "url_verification", "token": "token", "challenge": "abc"},
            cfg,
            allow_any_chat=True,
        )

        assert status == 200
        assert response == {"challenge": "abc"}
        assert result.handled is True

    def test_webhook_rejects_bad_verification_token(self, tmp_path):
        cfg = _cfg(tmp_path, verification_token="token")

        status, response, result = feishu_bridge.handle_webhook_payload(
            {"type": "url_verification", "token": "wrong", "challenge": "abc"},
            cfg,
            allow_any_chat=True,
        )

        assert status == 403
        assert response["ok"] is False
        assert result.handled is False

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
