"""Worktree checkpoint helpers for long-running cnb sessions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

SECRET_NAME_BITS = (
    ".env",
    ".pem",
    ".key",
    ".p8",
    "id_rsa",
    "id_dsa",
    "secret",
    "token",
    "credential",
    "credentials",
    "config.toml",
)
GENERATED_PREFIXES = ("build/", "dist/", "node_modules/", "htmlcov/", ".pytest_cache/", ".ruff_cache/")
GENERATED_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp", ".DS_Store")
BOARD_PREFIXES = ("board/", ".cnb/board/")


@dataclass(frozen=True)
class WorktreeChange:
    status: str
    path: str
    bucket: str
    reason: str


@dataclass(frozen=True)
class WorktreeCheckpoint:
    root: Path
    branch: str
    head: str
    upstream: str
    ahead: int
    behind: int
    changes: tuple[WorktreeChange, ...]
    git_available: bool = True

    @property
    def has_dirty_changes(self) -> bool:
        return bool(self.changes)

    @property
    def has_secret_risk(self) -> bool:
        return any(change.bucket == "secret/config risk" for change in self.changes)


def build_checkpoint(project_root: Path) -> WorktreeCheckpoint:
    root = _git(project_root, "rev-parse", "--show-toplevel")
    if root is None:
        return WorktreeCheckpoint(project_root, "", "", "", 0, 0, (), git_available=False)
    git_root = Path(root)
    branch = _git(git_root, "branch", "--show-current") or "(detached)"
    head = _git(git_root, "log", "--oneline", "-1") or ""
    upstream = _git(git_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or ""
    ahead, behind = _ahead_behind(git_root, upstream)
    status = _git(git_root, "status", "--porcelain")
    changes = tuple(parse_status(status or ""))
    return WorktreeCheckpoint(git_root, branch, head, upstream, ahead, behind, changes)


def parse_status(text: str) -> list[WorktreeChange]:
    changes: list[WorktreeChange] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or line[:2]
        path = _status_path(line)
        bucket, reason = classify_path(path, status)
        changes.append(WorktreeChange(status, path, bucket, reason))
    return changes


def classify_path(path: str, status: str = "") -> tuple[str, str]:
    lowered = path.lower()
    if any(bit in lowered for bit in SECRET_NAME_BITS):
        return "secret/config risk", "do not auto-commit; inspect or move to ignored local config first"
    if lowered.startswith(BOARD_PREFIXES):
        return "board/runtime churn", "coordination state, usually not part of product commits"
    if lowered.startswith(GENERATED_PREFIXES) or lowered.endswith(GENERATED_SUFFIXES):
        return "generated artifact", "usually regenerate or ignore instead of committing blindly"
    if status == "??":
        return "untracked local file", "decide whether this is new source, generated output, or local-only data"
    return "code/docs change", "review, test, then commit on a task branch"


def render_checkpoint(checkpoint: WorktreeCheckpoint, *, guard: bool = False) -> str:
    if not checkpoint.git_available:
        return f"=== Worktree Checkpoint ===\n\nNot a git worktree: {checkpoint.root}"

    lines = [
        "=== Worktree Checkpoint ===",
        "",
        f"Root: {checkpoint.root}",
        f"Branch: {checkpoint.branch}",
        f"Head: {checkpoint.head or '(unknown)'}",
    ]
    if checkpoint.upstream:
        lines.append(f"Upstream: {checkpoint.upstream} (ahead {checkpoint.ahead}, behind {checkpoint.behind})")
    else:
        lines.append("Upstream: (none)")
    lines.append("")

    if not checkpoint.changes:
        lines.append("Working tree clean.")
        if checkpoint.ahead:
            lines.append(f"Local commits not pushed: {checkpoint.ahead}; push or open a PR before handoff.")
        else:
            lines.append("No local dirty state. Track GitHub-only planning in issues/PRs.")
        return "\n".join(lines)

    grouped: dict[str, list[WorktreeChange]] = {}
    for change in checkpoint.changes:
        grouped.setdefault(change.bucket, []).append(change)
    for bucket in (
        "secret/config risk",
        "code/docs change",
        "untracked local file",
        "generated artifact",
        "board/runtime churn",
    ):
        items = grouped.get(bucket, [])
        if not items:
            continue
        lines.append(f"{bucket}: {len(items)}")
        for change in items[:20]:
            lines.append(f"  {change.status:<2} {change.path} — {change.reason}")
        if len(items) > 20:
            lines.append(f"  ... {len(items) - 20} more")
        lines.append("")

    lines.extend(_recommendations(checkpoint, guard=guard))
    return "\n".join(lines).rstrip()


def checkpoint_has_blocker(checkpoint: WorktreeCheckpoint) -> bool:
    return checkpoint.has_dirty_changes or checkpoint.has_secret_risk or checkpoint.ahead > 0


def _recommendations(checkpoint: WorktreeCheckpoint, *, guard: bool) -> list[str]:
    lines = ["Suggested action:"]
    if checkpoint.has_secret_risk:
        lines.append(
            "- Secret/config-looking files are present. Do not commit until inspected and ignored or redacted."
        )
    if any(change.bucket == "code/docs change" for change in checkpoint.changes):
        lines.append("- Commit intentional code/docs changes on a branch after running the relevant tests.")
    if any(change.bucket == "untracked local file" for change in checkpoint.changes):
        lines.append("- Classify untracked files before handoff: source, generated artifact, or local-only data.")
    if any(change.bucket == "generated artifact" for change in checkpoint.changes):
        lines.append("- Regenerate or ignore generated artifacts unless the project explicitly tracks them.")
    if any(change.bucket == "board/runtime churn" for change in checkpoint.changes):
        lines.append("- Leave board/runtime churn out of product commits unless it is the task output.")
    if checkpoint.ahead:
        lines.append(f"- Push/open PR for {checkpoint.ahead} local commit(s) before migration or shutdown.")
    if guard:
        lines.append(
            "- Guard mode: pause shutdown/migration/prompt refresh until the above is saved or explicitly accepted."
        )
    lines.append("- Related follow-ups: #74 repository sweep and #41 shift-report handoff.")
    return lines


def _ahead_behind(root: Path, upstream: str) -> tuple[int, int]:
    if not upstream:
        return 0, 0
    counts = _git(root, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
    if not counts:
        return 0, 0
    try:
        behind, ahead = (int(part) for part in counts.split())
    except ValueError:
        return 0, 0
    return ahead, behind


def _status_path(line: str) -> str:
    raw = line[3:] if len(line) > 3 else line.strip()
    if " -> " in raw:
        raw = raw.rsplit(" -> ", 1)[1]
    return raw.strip().strip('"')


def _git(project_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()
