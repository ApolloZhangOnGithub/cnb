"""Tests for role manifest loading and integration."""

from __future__ import annotations

from pathlib import Path

from src.roles import (
    EMPTY_MANIFEST,
    RoleManifest,
    load_all_manifests,
    load_manifest,
    resolve_role_for_identity,
    resolve_role_for_pilot,
)


class TestRoleManifest:
    def test_load_all_manifests(self):
        manifests = load_all_manifests()

        assert len(manifests) >= 7
        assert "tx_device_manager" in manifests
        assert "tx_project_member" in manifests
        assert "main_user" in manifests

    def test_load_manifest_by_name(self):
        m = load_manifest("tx_project_member")

        assert m.role == "tx_project_member"
        assert m.label == "项目成员同学"
        assert m.kind == "tongxue"
        assert len(m.commands_primary) > 0

    def test_load_manifest_with_alias(self):
        m = load_manifest("device_supervisor")

        assert m.role == "tx_device_manager"

    def test_load_manifest_missing(self):
        m = load_manifest("nonexistent_role")

        assert m is EMPTY_MANIFEST
        assert m.role == ""

    def test_resolve_role_for_identity(self):
        assert resolve_role_for_identity("lead") == "tx_project_manager"
        assert resolve_role_for_identity("dispatcher") == "tx_project_manager"
        assert resolve_role_for_identity("musk") == "tx_project_member"
        assert resolve_role_for_identity("bezos") == "tx_project_member"

    def test_resolve_role_for_pilot(self):
        assert resolve_role_for_pilot("device_supervisor") == "tx_device_manager"
        assert resolve_role_for_pilot("device_chief") == "tx_super_admin"

    def test_is_command_in_scope(self):
        m = load_manifest("tx_project_member")

        assert m.is_command_in_scope("board --as X inbox")
        assert m.is_command_in_scope("board --as X send")
        assert not m.is_command_in_scope("cnb feishu restart-supervisor")

    def test_boundary_warning(self):
        m = load_manifest("tx_project_member")

        assert m.boundary_warning("board --as X inbox") is None
        warning = m.boundary_warning("cnb feishu setup")
        assert warning is not None
        assert "项目成员同学" in warning

    def test_generate_prompt_section(self):
        m = load_manifest("tx_device_manager")

        prompt = m.generate_prompt_section()

        assert "设备主管同学" in prompt
        assert "cnb feishu reply" in prompt
        assert "你不应该" in prompt

    def test_all_commands(self):
        m = load_manifest("admin_user")

        all_cmds = m.all_commands()

        assert len(all_cmds) == len(m.commands_primary) + len(m.commands_secondary) + len(m.commands_infra)

    def test_manifest_from_dict(self):
        data = {
            "role": "test_role",
            "label": "测试角色",
            "description": "for testing",
            "kind": "tongxue",
            "scope": {"sees": ["everything"], "manages": ["nothing"]},
            "commands": {"primary": ["cmd1", "cmd2"], "secondary": ["cmd3"]},
            "boundaries": {"does_not": ["break things"]},
        }

        m = RoleManifest.from_dict(data)

        assert m.role == "test_role"
        assert m.commands_primary == ("cmd1", "cmd2")
        assert m.does_not == ("break things",)
