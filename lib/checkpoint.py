"""Checkpoint dirty-worktree state before shutdown, migration, or handoff."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from lib.secret_scan_core import scan_content, scan_filename, should_skip

GENERATED_DIR_NAMES = {
    "__pycache__",
    ".build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "DerivedData",
}

LOCAL_STATE_PREFIXES = (
    ".cnb/",
    ".claudes/",
    ".claude/commands/",
    ".claude/settings.local.json",
    ".claude/worktrees/",
    "instances/",
    "npm_recovery_codes.txt",
)

MARKED_BACKUP_TOKENS = (".shit", " 2")


@dataclass(frozen=True)
class ChangeItem:
    path: str
    status: str
    staged: bool = False


@dataclass(frozen=True)
class SecretRisk:
    path: str
    reason: str
    line: int | None = None
    staged: bool = False


@dataclass(frozen=True)
class CheckpointReport:
    root: str
    git_available: bool
    code_changes: list[ChangeItem]
    generated_artifacts: list[str]
    local_state: list[str]
    marked_backups: list[str]
    secret_risks: list[SecretRisk]
    external_planning_note: str
    recommendations: list[str]

    @property
    def has_dirty_work(self) -> bool:
        return bool(
            self.code_changes
            or self.generated_artifacts
            or self.local_state
            or self.marked_backups
            or self.secret_risks
        )

    @property
    def has_important_work(self) -> bool:
        return bool(self.code_changes or self.secret_risks)

    @property
    def has_staged_secret_risk(self) -> bool:
        return any(risk.staged for risk in self.secret_risks)


def _git(root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=check,
        timeout=20,
    )


def _git_root(root: Path) -> Path | None:
    result = _git(root, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _split_nul(stdout: str) -> list[str]:
    return [item for item in stdout.split("\0") if item]


def _worktree_status(root: Path) -> list[ChangeItem]:
    raw = _split_nul(_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]).stdout)
    items: list[ChangeItem] = []
    i = 0
    while i < len(raw):
        entry = raw[i]
        status = entry[:2]
        path = entry[3:]
        if status[0] in {"R", "C"} and i + 1 < len(raw):
            path = raw[i + 1]
            i += 2
        else:
            i += 1
        staged = status[0] not in {" ", "?"}
        items.append(ChangeItem(path=path, status=status, staged=staged))
    return items


def _staged_status(root: Path) -> list[ChangeItem]:
    raw = _split_nul(_git(root, ["diff", "--cached", "--name-status", "-z", "--diff-filter=ACMR"]).stdout)
    items: list[ChangeItem] = []
    i = 0
    while i + 1 < len(raw):
        status = raw[i]
        path = raw[i + 1]
        if status.startswith(("R", "C")) and i + 2 < len(raw):
            path = raw[i + 2]
            i += 3
        else:
            i += 2
        items.append(ChangeItem(path=path, status=status, staged=True))
    return items


def _ignored_files(root: Path) -> list[str]:
    return _split_nul(_git(root, ["ls-files", "--others", "--ignored", "--exclude-standard", "-z"]).stdout)


def _is_generated(relpath: str) -> bool:
    path = Path(relpath)
    if path.name == ".DS_Store" or path.suffix == ".pyc":
        return True
    if any(part in GENERATED_DIR_NAMES for part in path.parts):
        return True
    return any(part.endswith(".egg-info") for part in path.parts)


def _is_local_state(relpath: str) -> bool:
    return any(relpath == prefix.rstrip("/") or relpath.startswith(prefix) for prefix in LOCAL_STATE_PREFIXES)


def _is_marked_backup(relpath: str) -> bool:
    return any(token in relpath for token in MARKED_BACKUP_TOKENS)


def _secret_risks(root: Path, changes: list[ChangeItem]) -> list[SecretRisk]:
    risks: list[SecretRisk] = []
    seen: set[tuple[str, str, int | None]] = set()
    for item in changes:
        if "D" in item.status and item.status != "??":
            continue

        name_issue = scan_filename(item.path)
        if name_issue:
            risks.append(SecretRisk(item.path, name_issue, staged=item.staged))
            continue

        if should_skip(item.path):
            continue

        for line, reason in scan_content(root / item.path):
            key = (item.path, reason, line)
            if key in seen:
                continue
            seen.add(key)
            risks.append(SecretRisk(item.path, reason, line=line, staged=item.staged))
    return risks


def _recommendations(report: CheckpointReport) -> list[str]:
    if not report.git_available:
        return ["Run checkpoint inside a git repository for worktree protection."]
    if not report.has_dirty_work:
        return ["Working tree is clean; shutdown or migration can proceed."]

    recommendations: list[str] = []
    if report.secret_risks:
        recommendations.append(
            "Secret-looking files or content detected; do not commit until redacted or moved to local config."
        )
    if report.code_changes:
        recommendations.append(
            "Review code/doc changes, then commit on an owned branch or stash before handoff/migration."
        )
    if report.local_state:
        recommendations.append(
            "Local runtime state should stay uncommitted; reference it in handoff notes only when needed."
        )
    if report.generated_artifacts:
        recommendations.append("Generated/cache artifacts are usually reproducible; clean only after review.")
    if report.marked_backups:
        recommendations.append("Marked backups/duplicates need owner review before removal or commit.")
    recommendations.append(
        "GitHub-only planning should be captured as issue/PR links in the handoff, not inferred from local files."
    )
    return recommendations


def build_checkpoint(root: Path, *, staged_only: bool = False) -> CheckpointReport:
    git_root = _git_root(root)
    if git_root is None:
        report = CheckpointReport(
            root=str(root),
            git_available=False,
            code_changes=[],
            generated_artifacts=[],
            local_state=[],
            marked_backups=[],
            secret_risks=[],
            external_planning_note="not checked: this is not a git repository",
            recommendations=[],
        )
        return replace(report, recommendations=_recommendations(report))

    changes = _staged_status(git_root) if staged_only else _worktree_status(git_root)
    ignored = [] if staged_only else _ignored_files(git_root)
    generated = sorted({path for path in ignored if _is_generated(path)})
    local_state = sorted({path for path in ignored if _is_local_state(path) and not _is_generated(path)})

    code_changes: list[ChangeItem] = []
    marked_backups: list[str] = []
    for item in changes:
        if _is_generated(item.path):
            generated.append(item.path)
        elif _is_local_state(item.path):
            local_state.append(item.path)
        elif _is_marked_backup(item.path):
            marked_backups.append(item.path)
        else:
            code_changes.append(item)

    secret_changes = [item for item in changes if not _is_generated(item.path)]
    risks = _secret_risks(git_root, secret_changes)
    risky_paths = {risk.path for risk in risks}
    code_changes = [item for item in code_changes if item.path not in risky_paths]

    report = CheckpointReport(
        root=str(git_root),
        git_available=True,
        code_changes=code_changes,
        generated_artifacts=sorted(set(generated)),
        local_state=sorted(set(local_state)),
        marked_backups=sorted(set(marked_backups)),
        secret_risks=risks,
        external_planning_note="not visible in git status; record issue/PR links explicitly in handoff notes",
        recommendations=[],
    )
    return replace(report, recommendations=_recommendations(report))


def checkpoint_to_json(report: CheckpointReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, sort_keys=True)


def _sample(values: list[str], *, limit: int = 12) -> list[str]:
    return values[:limit]


def print_checkpoint(report: CheckpointReport) -> None:
    print("cnb checkpoint")
    if not report.git_available:
        print(f"  not a git repository: {report.root}")
        for recommendation in report.recommendations:
            print(f"  - {recommendation}")
        return

    print(f"  root: {report.root}")
    print(f"  code/doc changes: {len(report.code_changes)}")
    print(f"  secret risks: {len(report.secret_risks)}")
    print(f"  local runtime state: {len(report.local_state)}")
    print(f"  generated/cache artifacts: {len(report.generated_artifacts)}")
    print(f"  marked backups / duplicates: {len(report.marked_backups)}")
    print(f"  external GitHub-only planning: {report.external_planning_note}")

    if report.secret_risks:
        print("\nsecret risks:")
        for risk in report.secret_risks[:20]:
            loc = f":{risk.line}" if risk.line else ""
            staged = " staged" if risk.staged else ""
            print(f"  {risk.path}{loc} - {risk.reason}{staged}")
    if report.code_changes:
        print("\ncode/doc changes:")
        for item in report.code_changes[:40]:
            staged = " staged" if item.staged else ""
            print(f"  {item.status} {item.path}{staged}")
    if report.local_state:
        print("\nlocal runtime state sample:")
        for path in _sample(report.local_state):
            print(f"  {path}")
    if report.generated_artifacts:
        print("\ngenerated/cache sample:")
        for path in _sample(report.generated_artifacts):
            print(f"  {path}")
    if report.marked_backups:
        print("\nmarked backup sample:")
        for path in _sample(report.marked_backups):
            print(f"  {path}")

    print("\nRecommended action:")
    for recommendation in report.recommendations:
        print(f"  - {recommendation}")


def shutdown_warning_lines(report: CheckpointReport) -> list[str]:
    if not report.git_available or not report.has_important_work:
        return []
    lines = ["", "[checkpoint] uncommitted important work detected before shutdown:"]
    if report.secret_risks:
        lines.append(f"  secret risks: {len(report.secret_risks)} (do not commit until reviewed)")
    if report.code_changes:
        lines.append(f"  code/doc changes: {len(report.code_changes)}")
    lines.append("  Run: cnb checkpoint")
    return lines
