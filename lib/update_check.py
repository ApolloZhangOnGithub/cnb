"""update_check — detect stale cnb install and notify the device-supervisor tongxue.

Python port of the bash-only check in `bin/cnb`, so tongxue who run `bin/board`
directly (skipping the `cnb` wrapper) also get covered. Shares the same on-disk
state files (`~/.cnb/latest-version`, `~/.cnb/update-notified`) for consistency
across the two entry points.

Always non-blocking: a failed or skipped check must never break a board call.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cnb"
CACHE_LATEST = CACHE_DIR / "latest-version"
CACHE_NOTIFIED = CACHE_DIR / "update-notified"

NPM_PACKAGE = "claude-nb"
CACHE_TTL_SECONDS = 60 * 60  # refresh latest version at most hourly


def is_venv() -> bool:
    if os.environ.get("VIRTUAL_ENV"):
        return True
    return sys.prefix != sys.base_prefix


def read_update_owner(env: Any) -> str | None:
    """Resolve the device-supervisor tongxue who applies updates.

    Resolution order matches `bin/cnb`:
      1. `CNB_UPDATE_OWNER` env var
      2. `~/.cnb/config.toml` (top-level update_owner / cnb_owner / maintainer / owner,
         or `[cnb]` table with same keys)
      3. project config: first session with role=lead, else "lead" if listed, else first session
    """
    explicit = os.environ.get("CNB_UPDATE_OWNER", "").strip()
    if explicit:
        return explicit

    global_cfg = CACHE_DIR / "config.toml"
    if global_cfg.is_file():
        owner = _owner_from_global(global_cfg)
        if owner:
            return owner

    project_cfg = env.claudes_dir / "config.toml"
    if project_cfg.is_file():
        owner = _owner_from_project(project_cfg)
        if owner:
            return owner
    return None


def _owner_from_global(path: Path) -> str | None:
    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return None
    for key in ("update_owner", "cnb_owner", "maintainer", "owner"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    cnb_table = data.get("cnb")
    if isinstance(cnb_table, dict):
        for key in ("update_owner", "owner", "maintainer"):
            value = cnb_table.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _owner_from_project(path: Path) -> str | None:
    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return None
    sessions = data.get("session")
    if isinstance(sessions, dict):
        for name, meta in sessions.items():
            if isinstance(meta, dict) and meta.get("role") == "lead":
                return str(name)
    names = data.get("sessions")
    if isinstance(names, list):
        if "lead" in names:
            return "lead"
        for name in names:
            if isinstance(name, str) and name:
                return name
    return None


def cached_latest_version() -> str | None:
    if not CACHE_LATEST.is_file():
        return None
    try:
        return CACHE_LATEST.read_text().strip() or None
    except OSError:
        return None


def cache_is_fresh(ttl_seconds: int = CACHE_TTL_SECONDS) -> bool:
    if not CACHE_LATEST.is_file():
        return False
    try:
        age = time.time() - CACHE_LATEST.stat().st_mtime
    except OSError:
        return False
    return age < ttl_seconds


def refresh_latest_version_async() -> None:
    """Spawn a backgrounded `npm view` to refresh the cache. Best-effort; never blocks."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_LATEST.with_suffix(".tmp")
    # Shell pipeline so we can redirect + move atomically; npm may be missing.
    cmd = f'npm view {NPM_PACKAGE} version > "{tmp}" 2>/dev/null && mv "{tmp}" "{CACHE_LATEST}" || rm -f "{tmp}"'
    try:
        subprocess.Popen(
            ["sh", "-c", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


_DEV_SUFFIX = re.compile(r"\.dev\d*$")
_PRERELEASE = re.compile(r"[-+].*$")


def normalize_version(version: str) -> tuple[int, ...]:
    v = version.strip().lstrip("vV")
    v = _DEV_SUFFIX.sub("", v)
    v = _PRERELEASE.sub("", v)
    parts: list[int] = []
    for part in v.split("."):
        match = re.match(r"\d+", part)
        parts.append(int(match.group(0)) if match else 0)
    parts.extend([0] * (4 - len(parts)))
    return tuple(parts[:4])


def version_gt(a: str, b: str) -> bool:
    return normalize_version(a) > normalize_version(b)


def notify_update_owner(env: Any, latest: str, current: str, *, sender: str = "dispatcher") -> bool:
    """Send a board message to the owner. Returns True if a new notification was sent.

    Suppresses duplicates via `~/.cnb/update-notified` keyed by owner:current->latest.
    """
    owner = read_update_owner(env)
    if not owner:
        return False
    if not (env.board_db.is_file()):
        return False

    key = f"{owner}:{current}->{latest}"
    if CACHE_NOTIFIED.is_file():
        try:
            if CACHE_NOTIFIED.read_text().strip() == key:
                return False
        except OSError:
            pass

    msg = f"[cnb update] cnb v{latest} 已发布，当前 v{current}。请由本机 cnb 负责人执行：npm install -g claude-nb"
    board_bin = env.install_home / "bin" / "board"
    try:
        result = subprocess.run(
            [str(board_bin), "--as", sender, "send", owner, msg],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    if result.returncode != 0:
        return False
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_NOTIFIED.write_text(key)
    except OSError:
        pass
    return True


def check_update(env: Any, current: str) -> bool:
    """Main entry. Cheap when no-op. Returns True iff a notification was sent.

    Order:
      1. Skip in venv (user-managed install).
      2. Refresh cache asynchronously if older than TTL — non-blocking.
      3. Compare cached latest against `current`. If newer, notify owner.
    """
    if is_venv():
        return False
    if not cache_is_fresh():
        refresh_latest_version_async()
    latest = cached_latest_version()
    if not latest:
        return False
    if not version_gt(latest, current):
        return False
    return notify_update_owner(env, latest, current)


def cmd_update_check(db: Any, args: list[str]) -> None:
    """Board command — manual trigger for debugging / cron jobs.

    `--force` ignores the notification-suppression key so the message resends even
    if the owner was already nudged for this version pair.
    """
    assert db.env is not None
    current_version = _read_local_version(db.env.install_home)
    if "--force" in args:
        CACHE_NOTIFIED.unlink(missing_ok=True)
        refresh_latest_version_async()
        # Give the spawned npm a beat to land; harmless if still pending.
        time.sleep(2)
    sent = check_update(db.env, current_version)
    latest = cached_latest_version() or "?"
    owner = read_update_owner(db.env) or "?"
    if is_venv():
        print(f"OK update-check skipped: in venv (current v{current_version})")
        return
    if sent:
        print(f"OK update-check notified {owner}: v{current_version} -> v{latest}")
    elif latest != "?" and version_gt(latest, current_version):
        print(f"OK update-check stale (already notified {owner} for v{latest})")
    else:
        print(f"OK update-check up to date (v{current_version}, latest v{latest})")


def _read_local_version(install_home: Path) -> str:
    version_file = install_home / "VERSION"
    if version_file.is_file():
        try:
            return version_file.read_text().strip()
        except OSError:
            pass
    return "dev"
