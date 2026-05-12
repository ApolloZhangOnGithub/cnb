"""Role manifest loading, resolution, and prompt generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RoleManifest:
    role: str
    label: str
    description: str
    kind: str  # "human" or "tongxue"
    sees: tuple[str, ...] = ()
    manages: tuple[str, ...] = ()
    commands_primary: tuple[str, ...] = ()
    commands_secondary: tuple[str, ...] = ()
    commands_infra: tuple[str, ...] = ()
    does_not: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoleManifest:
        scope = data.get("scope") or {}
        commands = data.get("commands") or {}
        boundaries = data.get("boundaries") or {}
        return cls(
            role=str(data.get("role", "")),
            label=str(data.get("label", "")),
            description=str(data.get("description", "")),
            kind=str(data.get("kind", "tongxue")),
            sees=_str_tuple(scope.get("sees")),
            manages=_str_tuple(scope.get("manages")),
            commands_primary=_str_tuple(commands.get("primary")),
            commands_secondary=_str_tuple(commands.get("secondary")),
            commands_infra=_str_tuple(commands.get("infra")),
            does_not=_str_tuple(boundaries.get("does_not")),
        )

    def all_commands(self) -> tuple[str, ...]:
        return self.commands_primary + self.commands_secondary + self.commands_infra

    def command_base_names(self) -> set[str]:
        names: set[str] = set()
        for cmd in self.all_commands():
            base = cmd.split("#")[0].strip()
            if base:
                names.add(base)
        return names

    def is_command_in_scope(self, command: str) -> bool:
        for cmd in self.all_commands():
            base = cmd.split("#")[0].strip()
            if command.startswith(base) or base.startswith(command):
                return True
        return False

    def generate_prompt_section(self) -> str:
        lines = [
            f"你的角色是{self.label}。{self.description}",
            "",
            "你的主要命令：",
        ]
        for cmd in self.commands_primary:
            lines.append(f"  {cmd}")
        if self.commands_secondary:
            lines.append("")
            lines.append("辅助命令：")
            for cmd in self.commands_secondary:
                lines.append(f"  {cmd}")
        if self.does_not:
            lines.append("")
            lines.append("你不应该：")
            for item in self.does_not:
                lines.append(f"  - {item}")
        return "\n".join(lines)

    def boundary_warning(self, command: str) -> str | None:
        if self.is_command_in_scope(command):
            return None
        return f"提示: {command} 不在{self.label}的常用命令中。"


EMPTY_MANIFEST = RoleManifest(role="", label="", description="", kind="")

_ROLE_MAP: dict[str, str] = {
    "lead": "tx_project_manager",
    "dispatcher": "tx_project_manager",
    "device_supervisor": "tx_device_manager",
    "device-supervisor": "tx_device_manager",
    "terminal_supervisor": "tx_device_manager",
    "device_chief": "tx_super_admin",
    "device-chief": "tx_super_admin",
}


def _roles_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "roles"


def _str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if v)
    return ()


def load_manifest(role_name: str, roles_dir: Path | None = None) -> RoleManifest:
    resolved = _ROLE_MAP.get(role_name, role_name)
    d = roles_dir or _roles_dir()
    path = d / f"{resolved}.yaml"
    if not path.exists():
        return EMPTY_MANIFEST
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return EMPTY_MANIFEST
    if not isinstance(data, dict):
        return EMPTY_MANIFEST
    return RoleManifest.from_dict(data)


def load_all_manifests(roles_dir: Path | None = None) -> dict[str, RoleManifest]:
    d = roles_dir or _roles_dir()
    manifests: dict[str, RoleManifest] = {}
    if not d.is_dir():
        return manifests
    for path in sorted(d.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict) or "role" not in data:
            continue
        m = RoleManifest.from_dict(data)
        manifests[m.role] = m
    return manifests


def resolve_role_for_identity(identity: str) -> str:
    if identity in _ROLE_MAP:
        return _ROLE_MAP[identity]
    return "tx_project_member"


def resolve_role_for_pilot(pilot_role: str) -> str:
    return _ROLE_MAP.get(pilot_role, "tx_device_manager")


def main() -> None:
    import sys

    args = sys.argv[1:]
    cmd = args[0] if args else "list"

    if cmd in ("list", "ls"):
        manifests = load_all_manifests()
        print(f"{'角色':<25} {'类型':<10} {'标签':<14} {'命令数'}")
        print("-" * 65)
        for name, m in manifests.items():
            total = len(m.commands_primary) + len(m.commands_secondary) + len(m.commands_infra)
            print(f"{m.role:<25} {m.kind:<10} {m.label:<14} {total} ({len(m.commands_primary)}+{len(m.commands_secondary)}+{len(m.commands_infra)})")
    elif cmd == "show":
        if len(args) < 2:
            print("Usage: cnb roles show <role>")
            raise SystemExit(1)
        m = load_manifest(args[1])
        if not m.role:
            print(f"ERROR: role '{args[1]}' not found")
            raise SystemExit(1)
        print(f"角色: {m.role} ({m.label})")
        print(f"类型: {m.kind}")
        print(f"描述: {m.description}")
        print(f"\n管辖: {', '.join(m.manages) if m.manages else '(无)'}")
        print(f"可见: {', '.join(m.sees) if m.sees else '(无)'}")
        print(f"\n主要命令:")
        for cmd_line in m.commands_primary:
            print(f"  {cmd_line}")
        if m.commands_secondary:
            print(f"\n辅助命令:")
            for cmd_line in m.commands_secondary:
                print(f"  {cmd_line}")
        if m.commands_infra:
            print(f"\n基础设施命令:")
            for cmd_line in m.commands_infra:
                print(f"  {cmd_line}")
        if m.does_not:
            print(f"\n不应该:")
            for item in m.does_not:
                print(f"  - {item}")
    elif cmd == "prompt":
        if len(args) < 2:
            print("Usage: cnb roles prompt <role>")
            raise SystemExit(1)
        m = load_manifest(args[1])
        if not m.role:
            print(f"ERROR: role '{args[1]}' not found")
            raise SystemExit(1)
        print(m.generate_prompt_section())
    else:
        print("Usage: cnb roles <list|show|prompt> [role]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
