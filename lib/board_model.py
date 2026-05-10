"""board model — switch LLM provider by updating settings.json env vars."""

import json
import os
import tomllib
from pathlib import Path

from lib.common import ClaudesEnv

PROVIDER_ENV_KEYS = {
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "CLAUDE_CODE_EFFORT_LEVEL",
}


def _resolve_value(value: str) -> str | None:
    if value.startswith("$"):
        resolved = os.environ.get(value[1:])
        if resolved is None:
            print(f"WARNING: 环境变量 {value[1:]} 未设置，跳过")
        return resolved
    return value


def _load_config(env: ClaudesEnv) -> dict:
    toml_file = env.claudes_dir / "config.toml"
    if toml_file.exists():
        return tomllib.loads(toml_file.read_text())
    return {}


def _load_profiles(env: ClaudesEnv) -> dict:
    config = _load_config(env)
    custom_path = config.get("model_profiles", "")
    if custom_path:
        profiles_path = Path(custom_path)
    else:
        profiles_path = env.claudes_dir / "model-profiles.json"

    if not profiles_path.exists():
        print(f"ERROR: profiles 文件不存在: {profiles_path}")
        print(f"创建示例: cp board/profiles.example.json {profiles_path}")
        raise SystemExit(1)

    with open(profiles_path) as f:
        return json.load(f)


def _resolve_profile(profiles: dict, name: str) -> str | None:
    """Resolve profile name via exact match or alias lookup."""
    if name in profiles:
        return name
    for key, p in profiles.items():
        if name in p.get("aliases", []):
            return key
    return None


def _default_scope(env: ClaudesEnv) -> str:
    config = _load_config(env)
    return config.get("model_scope", "global")


def _find_project_settings() -> Path | None:
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        candidate = d / ".claude" / "settings.json"
        if candidate.exists():
            return candidate
    return None


def _switch(env: ClaudesEnv, profile_name: str, scope: str) -> None:
    profiles = _load_profiles(env)
    resolved = _resolve_profile(profiles, profile_name)
    if not resolved:
        print(f"ERROR: 未找到 profile '{profile_name}'")
        print(f"可用: {', '.join(profiles.keys())}")
        raise SystemExit(1)

    profile = profiles[resolved]

    if scope == "project":
        settings_path = _find_project_settings()
        if not settings_path:
            print("ERROR: 未找到项目级 .claude/settings.json")
            raise SystemExit(1)
    else:
        settings_path = Path.home() / ".claude" / "settings.json"

    settings = {}
    if settings_path.exists():
        with open(settings_path) as f:
            settings = json.load(f)

    current_env = settings.get("env", {})
    for key in PROVIDER_ENV_KEYS:
        current_env.pop(key, None)

    for key, value in profile.get("env", {}).items():
        resolved_val = _resolve_value(value)
        if resolved_val is not None:
            current_env[key] = resolved_val

    settings["env"] = current_env

    perms = profile.get("permissions")
    if perms:
        existing_perms = settings.get("permissions", {})
        merged = dict(existing_perms)
        merged.update(perms)
        settings["permissions"] = merged

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")

    display = profile.get("name", resolved)
    print(f"OK 已切换到 [{display}]")
    print(f"   配置: {settings_path}")
    for k in PROVIDER_ENV_KEYS:
        if k in current_env:
            v = current_env[k]
            if "KEY" in k or "TOKEN" in k:
                v = v[:8] + "..." if len(v) > 8 else "***"
            print(f"   {k}={v}")
    if perms:
        print(f"   permissions: {merged}")
    if not profile.get("env"):
        print("   已清空 provider 变量 (恢复 Anthropic 原生)")
    print("\n重启 Claude Code 后生效。")


def _show_current() -> None:
    for label, path in [
        ("全局", Path.home() / ".claude" / "settings.json"),
        ("项目", _find_project_settings()),
    ]:
        if path and path.exists():
            with open(path) as f:
                env_vars = json.load(f).get("env", {})
            provider_vars = {k: v for k, v in env_vars.items() if k in PROVIDER_ENV_KEYS}
            if provider_vars:
                print(f"{label} ({path}):")
                for k, v in provider_vars.items():
                    if "KEY" in k or "TOKEN" in k:
                        v = v[:8] + "..." if len(v) > 8 else "***"
                    print(f"  {k}={v}")
            else:
                print(f"{label}: 默认 (Anthropic 原生)")
        elif label == "全局":
            print(f"{label}: 默认 (Anthropic 原生)")


def _list_profiles(env: ClaudesEnv) -> None:
    profiles = _load_profiles(env)
    print("可用 profiles:")
    for name, p in profiles.items():
        aliases = p.get("aliases", [])
        alias_str = f" [{', '.join(aliases)}]" if aliases else ""
        model = p.get("env", {}).get("ANTHROPIC_MODEL", "claude (原生)")
        print(f"  {name:20s}{alias_str:20s} {p.get('name', name):25s} model={model}")


def _print_menu(env: ClaudesEnv) -> None:
    print("cnb m (model) — 切换 LLM provider\n")
    print("  cnb m <profile> [-s global|project]    切换（推荐）")
    print("  cnb m current                          查看当前")
    print("  cnb m list                             列出可用")
    print()
    _show_current()
    print()
    try:
        _list_profiles(env)
    except SystemExit:
        pass


def _parse_scope(args: list[str], default: str) -> str:
    for flag in ("--scope", "-s"):
        if flag in args:
            idx = args.index(flag)
            if idx + 1 < len(args):
                return args[idx + 1]
            print(f"WARNING: {flag} 缺少参数，使用默认 '{default}'")
    return default


# ── Subcommand handler ──


def cmd_model(db, rest):
    env = ClaudesEnv.load()

    if not rest:
        _print_menu(env)
        return

    cmd = rest[0]
    args = rest[1:]

    if cmd in ("menu", "help", "-h", "--help"):
        _print_menu(env)
    elif cmd == "list":
        _list_profiles(env)
    elif cmd == "current":
        _show_current()
    elif cmd == "use":
        if not args:
            print("Usage: cnb m <profile> [-s global|project]")
            return
        _switch(env, args[0], _parse_scope(args, _default_scope(env)))
    else:
        _switch(env, cmd, _parse_scope(rest, _default_scope(env)))
