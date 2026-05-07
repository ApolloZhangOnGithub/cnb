"""Global project registry for cross-project discovery and shared credentials.

Registry lives at ~/.cnb/ and tracks:
- projects.json: all cnb projects on this machine
- shared/credentials.json: credential status (valid/expired/unknown)
"""

import json
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CNB_HOME = Path.home() / ".cnb"
PROJECTS_FILE = CNB_HOME / "projects.json"
CREDENTIALS_FILE = CNB_HOME / "shared" / "credentials.json"

VALID_CREDENTIAL_STATUSES = frozenset({"valid", "expired", "unknown"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    """Create ~/.cnb/ and ~/.cnb/shared/ if they don't exist."""
    CNB_HOME.mkdir(parents=True, exist_ok=True)
    (CNB_HOME / "shared").mkdir(exist_ok=True)


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_projects(path: Path | None = None) -> dict:
    """Read projects.json, returning {'projects': [...]}."""
    p = path or PROJECTS_FILE
    if not p.exists():
        return {"projects": []}
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict) or "projects" not in data:
            return {"projects": []}
        return data
    except (json.JSONDecodeError, OSError):
        return {"projects": []}


def _write_projects(data: dict, path: Path | None = None) -> None:
    """Write projects.json atomically."""
    p = path or PROJECTS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _read_credentials(path: Path | None = None) -> dict:
    """Read credentials.json, returning {name: {status, updated, updated_by}}."""
    p = path or CREDENTIALS_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _write_credentials(data: dict, path: Path | None = None) -> None:
    """Write credentials.json."""
    p = path or CREDENTIALS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_project(project_path: str | Path, name: str, *, registry_path: Path | None = None) -> None:
    """Add or update a project in the global registry.

    If the project path already exists, updates name and last_active.
    """
    _ensure_dirs()
    path_str = str(Path(project_path).resolve())
    data = _read_projects(registry_path)

    # Update existing or append new
    for entry in data["projects"]:
        if entry.get("path") == path_str:
            entry["name"] = name
            entry["last_active"] = _now_iso()
            _write_projects(data, registry_path)
            return

    data["projects"].append(
        {
            "path": path_str,
            "name": name,
            "last_active": _now_iso(),
        }
    )
    _write_projects(data, registry_path)


def list_projects(*, registry_path: Path | None = None) -> list[dict[str, str]]:
    """Return the list of registered project dicts."""
    projects: list[dict[str, str]] = _read_projects(registry_path).get("projects", [])
    return projects


def remove_project(project_path: str | Path, *, registry_path: Path | None = None) -> bool:
    """Remove a project by path. Returns True if found and removed."""
    path_str = str(Path(project_path).resolve())
    data = _read_projects(registry_path)
    original_len = len(data["projects"])
    data["projects"] = [e for e in data["projects"] if e.get("path") != path_str]
    if len(data["projects"]) < original_len:
        _write_projects(data, registry_path)
        return True
    return False


def update_credential(
    name: str,
    status: str,
    *,
    updated_by: str | Path | None = None,
    credentials_path: Path | None = None,
) -> None:
    """Set credential status (valid/expired/unknown).

    Args:
        name: credential name (e.g. 'npm', 'lark')
        status: one of 'valid', 'expired', 'unknown'
        updated_by: project path that updated the credential
        credentials_path: override path for testing
    """
    if status not in VALID_CREDENTIAL_STATUSES:
        print(f"ERROR: 无效的凭证状态 '{status}'，有效值: {', '.join(sorted(VALID_CREDENTIAL_STATUSES))}")
        raise SystemExit(1)

    _ensure_dirs()
    data = _read_credentials(credentials_path)
    data[name] = {
        "status": status,
        "updated": _now_iso(),
        "updated_by": str(updated_by) if updated_by else "",
    }
    _write_credentials(data, credentials_path)


def check_credential(name: str, *, credentials_path: Path | None = None) -> dict | None:
    """Check credential status. Returns status dict or None if not tracked."""
    data = _read_credentials(credentials_path)
    return data.get(name)


def cleanup(*, registry_path: Path | None = None) -> list[str]:
    """Remove projects whose paths no longer exist on disk.

    Returns list of removed project paths.
    """
    data = _read_projects(registry_path)
    removed = []
    surviving = []
    for entry in data["projects"]:
        p = Path(entry.get("path", ""))
        if p.exists():
            surviving.append(entry)
        else:
            removed.append(entry.get("path", ""))
    if removed:
        data["projects"] = surviving
        _write_projects(data, registry_path)
    return removed
