#!/usr/bin/env python3
"""resources.py -- Unified resource monitoring (battery + memory + CPU).

Detects anomalies and notifies via board.

Usage:
    ./lib/resources.py              # One-shot status check
    ./lib/resources.py --watch      # Continuous monitoring (30s interval)
    ./lib/resources.py --json       # Machine-readable output
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

BATTERY_LOW = 30
BATTERY_CRITICAL = 15
MEMORY_WARN_PCT = 80
CPU_SATURATED = 90
CPU_SUSTAIN_CHECKS = 2
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BatteryInfo:
    status: str  # AC, ON_BATTERY, LOW, CRITICAL, N/A
    pct: int
    on_battery: bool
    remaining: str


@dataclass
class MemoryInfo:
    status: str  # OK, WARNING, CRITICAL
    used_pct: int
    pressure: str  # normal, warn, critical


@dataclass
class CPUInfo:
    status: str  # OK, SATURATED
    usage: int


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    user: str
    cpu: float
    rss_mb: int
    elapsed: str
    command: str
    args: str


@dataclass
class ProcessGroup:
    name: str
    kind: str
    cnb_owned: bool
    cpu: float
    rss_mb: int
    count: int
    pids: list[int]
    top_command: str
    severity: str
    recommendation: str


@dataclass
class PressureReport:
    battery: BatteryInfo
    memory: MemoryInfo
    cpu: CPUInfo
    groups: list[ProcessGroup]
    safety_note: str


# ---------------------------------------------------------------------------
# Detection helpers (macOS-specific)
# ---------------------------------------------------------------------------


def _run(cmd: str | Sequence[str], default: str = "") -> str:
    """Run a command and return stdout, or *default* on failure."""
    argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    if not argv:
        return default
    try:
        r = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else default
    except Exception:
        return default


def check_battery() -> BatteryInfo:
    if not shutil.which("pmset"):
        return BatteryInfo(status="N/A", pct=100, on_battery=False, remaining="—")

    batt_info = _run(["pmset", "-g", "batt"])
    on_battery = "Battery Power" in batt_info

    m = re.search(r"(\d+)%", batt_info)
    pct = int(m.group(1)) if m else 100

    m_rem = re.search(r"(\d+:\d+ remaining)", batt_info)
    remaining = m_rem.group(1) if m_rem else "—"

    if on_battery:
        if pct < BATTERY_CRITICAL:
            status = "CRITICAL"
        elif pct < BATTERY_LOW:
            status = "LOW"
        else:
            status = "ON_BATTERY"
    else:
        status = "AC"

    return BatteryInfo(status=status, pct=pct, on_battery=on_battery, remaining=remaining)


def check_memory() -> MemoryInfo:
    status = "OK"
    used_pct = 0
    pressure = "normal"

    if shutil.which("memory_pressure"):
        mp_out = (_run(["memory_pressure"]).splitlines() or [""])[-1]
        if "critical" in mp_out.lower():
            pressure = "critical"
            status = "CRITICAL"
        elif "warn" in mp_out.lower():
            pressure = "warn"
            status = "WARNING"

    if shutil.which("vm_stat"):
        vm_out = _run(["vm_stat"])
        lines = vm_out.splitlines()
        if lines:
            # page size
            ps_match = re.search(r"(\d+)", lines[0])
            page_size = int(ps_match.group(1)) if ps_match else 4096

            def _extract(label: str) -> int:
                for ln in lines:
                    if label in ln:
                        m = re.search(r"(\d+)", ln.split(":")[-1])
                        return int(m.group(1)) if m else 0
                return 0

            pages_free = _extract("Pages free")
            pages_speculative = _extract("Pages speculative")

            total_bytes_str = _run(["sysctl", "-n", "hw.memsize"], "0")
            total_bytes = int(total_bytes_str) if total_bytes_str.isdigit() else 0

            if total_bytes > 0:
                total_mb = total_bytes // (1024 * 1024)
                free_pages = pages_free + pages_speculative
                free_mb = (free_pages * page_size) // (1024 * 1024)
                if total_mb > 0:
                    used_pct = (total_mb - free_mb) * 100 // total_mb

    return MemoryInfo(status=status, used_pct=used_pct, pressure=pressure)


def check_cpu() -> CPUInfo:
    status = "OK"
    usage = 0

    if shutil.which("top"):
        top_out = _run(["top", "-l", "1", "-n", "0"])
        for line in top_out.splitlines():
            if "CPU usage" in line:
                m = re.search(r"([\d.]+)%\s*idle", line)
                if m:
                    idle = float(m.group(1))
                    usage = round(100 - idle)
                break

    if usage >= CPU_SATURATED:
        status = "SATURATED"

    return CPUInfo(status=status, usage=usage)


# ---------------------------------------------------------------------------
# Process grouping for read-only pressure diagnosis
# ---------------------------------------------------------------------------


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def _command_name(args: str) -> str:
    app_match = re.search(r"/([^/]+\.app)(?:/|$)", args)
    if app_match:
        return app_match.group(1).removesuffix(".app")
    first = args.split(None, 1)[0] if args.split(None, 1) else ""
    return Path(first).name or first or "unknown"


def _parse_ps_output(output: str) -> list[ProcessInfo]:
    processes: list[ProcessInfo] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("PID "):
            continue
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        pid, ppid, user, cpu, rss_kb, elapsed, args = parts[:7]
        processes.append(
            ProcessInfo(
                pid=_parse_int(pid),
                ppid=_parse_int(ppid),
                user=user,
                cpu=_parse_float(cpu),
                rss_mb=max(0, _parse_int(rss_kb) // 1024),
                elapsed=elapsed,
                command=_command_name(args),
                args=args,
            )
        )
    return processes


def collect_processes(*, limit: int = 40) -> list[ProcessInfo]:
    if not shutil.which("ps"):
        return []
    output = _run(["ps", "-axo", "pid=,ppid=,user=,pcpu=,rss=,etime=,command="])
    processes = _parse_ps_output(output)
    return sorted(processes, key=lambda p: (p.cpu, p.rss_mb), reverse=True)[:limit]


def _process_kind(proc: ProcessInfo, project_roots: list[Path] | None = None) -> tuple[str, str, bool]:
    text = f"{proc.command} {proc.args}".lower()
    cnb_owned = any(token in text for token in (" cnb", "/cnb", ".cnb", "claudes-code", "cc-"))
    for root in project_roots or []:
        if str(root).lower() in text:
            cnb_owned = True
            break
    if "xcode" in text:
        return "Xcode", "developer-tool", cnb_owned
    if "simulator" in text or "simctl" in text:
        return "Simulator", "simulator", cnb_owned
    if "docker" in text or "containerd" in text:
        return "Docker", "container", cnb_owned
    if any(token in text for token in ("google chrome", "chrome", "safari", "firefox", "arc helper")):
        return "Browser", "browser", cnb_owned
    if "codex" in text or "claude" in text:
        return "Codex/Claude agents", "agent", cnb_owned
    if "tmux" in text:
        return "tmux", "terminal", cnb_owned
    if "python" in text:
        return "Python", "runtime", cnb_owned
    if "node" in text or "npm" in text:
        return "Node/npm", "runtime", cnb_owned
    return Path(proc.command).name or proc.command or "unknown", "process", cnb_owned


def _severity(cpu: float, rss_mb: int) -> str:
    if cpu >= 80 or rss_mb >= 8192:
        return "high"
    if cpu >= 30 or rss_mb >= 2048:
        return "medium"
    return "low"


def _recommendation(name: str, kind: str, cnb_owned: bool, severity: str) -> str:
    if cnb_owned:
        return (
            "cnb-owned: inspect the related board/tmux session first; stop only clearly idle owned sessions "
            "after confirmation."
        )
    if kind in {"developer-tool", "simulator"}:
        return "external dev workload: close or pause it manually if it is not the current build/test target."
    if kind == "browser":
        return "external browser workload: review tabs/windows manually; do not terminate from cnb."
    if kind == "container":
        return "external container workload: inspect Docker manually before stopping containers."
    if severity == "high":
        return f"external {name} pressure: identify the owner before any action; no automatic termination."
    return "observe only unless the user explicitly asks for a specific action."


def group_processes(
    processes: list[ProcessInfo], *, limit: int = 8, project_roots: list[Path] | None = None
) -> list[ProcessGroup]:
    buckets: dict[str, list[ProcessInfo]] = {}
    metadata: dict[str, tuple[str, bool]] = {}
    for proc in processes:
        name, kind, cnb_owned = _process_kind(proc, project_roots)
        buckets.setdefault(name, []).append(proc)
        old_kind, old_owned = metadata.get(name, (kind, False))
        metadata[name] = (old_kind, old_owned or cnb_owned)

    groups: list[ProcessGroup] = []
    for name, members in buckets.items():
        kind, cnb_owned = metadata[name]
        cpu_total = round(sum(proc.cpu for proc in members), 1)
        rss_total = sum(proc.rss_mb for proc in members)
        top = max(members, key=lambda p: (p.cpu, p.rss_mb))
        severity = _severity(cpu_total, rss_total)
        groups.append(
            ProcessGroup(
                name=name,
                kind=kind,
                cnb_owned=cnb_owned,
                cpu=cpu_total,
                rss_mb=rss_total,
                count=len(members),
                pids=sorted(proc.pid for proc in members),
                top_command=top.args[:160],
                severity=severity,
                recommendation=_recommendation(name, kind, cnb_owned, severity),
            )
        )
    return sorted(groups, key=lambda g: (SEVERITY_RANK[g.severity], g.cpu, g.rss_mb), reverse=True)[:limit]


def build_pressure_report(*, process_limit: int = 40, group_limit: int = 8) -> PressureReport:
    batt, mem, cpu = get_all()
    project_root = Path(os.environ.get("CNB_PROJECT") or Path.cwd()).expanduser().resolve()
    groups = group_processes(collect_processes(limit=process_limit), limit=group_limit, project_roots=[project_root])
    return PressureReport(
        battery=batt,
        memory=mem,
        cpu=cpu,
        groups=groups,
        safety_note="Read-only diagnosis: cnb did not stop, kill, or pause any process.",
    )


def pressure_report_json(report: PressureReport) -> str:
    return json.dumps(
        {
            "battery": report.battery.__dict__,
            "memory": report.memory.__dict__,
            "cpu": report.cpu.__dict__,
            "groups": [group.__dict__ for group in report.groups],
            "safety_note": report.safety_note,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# State tracking for notification dedup
# ---------------------------------------------------------------------------


def _state_file() -> Path:
    try:
        from lib.common import find_claudes_dir

        return find_claudes_dir() / "resource-monitor-state"
    except Exception:
        return Path("/tmp/resource-monitor-state")


def _load_prev_state() -> str:
    sf = _state_file()
    try:
        if sf.exists():
            return sf.read_text().strip()
    except OSError:
        pass
    return "AC|normal|OK"


def _save_state(state: str) -> None:
    _state_file().write_text(state + "\n")


def notify_if_changed(batt: BatteryInfo, mem: MemoryInfo, cpu: CPUInfo, board_cmd: str | None = None) -> None:
    """Send board notifications only on state transitions."""
    current = f"{batt.status}|{mem.status}|{cpu.status}"
    prev = _load_prev_state()
    if current == prev:
        return
    _save_state(current)

    if board_cmd is None:
        return

    def _send(msg: str) -> None:
        try:
            subprocess.run(
                [board_cmd, "--as", "monitor", "send", "All", msg],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass

    # Battery transitions
    if batt.status == "CRITICAL":
        _send(f"[BATTERY CRITICAL] {batt.pct}% remaining. Suspending non-essential sessions recommended.")
    elif batt.status == "LOW":
        _send(f"[BATTERY LOW] {batt.pct}%. Consider reducing active sessions.")
    elif batt.status == "ON_BATTERY" and prev.startswith("AC"):
        _send(f"[BATTERY] Switched to battery power ({batt.pct}%).")

    # Memory transitions
    if mem.status == "CRITICAL" and "CRITICAL" not in prev:
        _send("[MEMORY CRITICAL] System under memory pressure. Save state + reduce sessions.")
    elif mem.status == "WARNING" and ("normal" in prev or "OK" in prev):
        _send("[MEMORY WARNING] Memory pressure rising. Monitor closely.")

    # CPU transitions
    if cpu.status == "SATURATED" and "SATURATED" not in prev:
        _send(f"[CPU SATURATED] CPU > {CPU_SATURATED}%. Avoid concurrent builds.")


# ---------------------------------------------------------------------------
# JSON output helper (used by dispatcher)
# ---------------------------------------------------------------------------


def to_json(batt: BatteryInfo, mem: MemoryInfo, cpu: CPUInfo) -> str:
    return json.dumps(
        {
            "battery": {
                "status": batt.status,
                "pct": batt.pct,
                "on_battery": batt.on_battery,
                "remaining": batt.remaining,
            },
            "memory": {
                "status": mem.status,
                "used_pct": mem.used_pct,
                "pressure": mem.pressure,
            },
            "cpu": {
                "status": cpu.status,
                "usage": cpu.usage,
            },
        }
    )


def get_all() -> tuple:
    """Return (BatteryInfo, MemoryInfo, CPUInfo) tuple."""
    return check_battery(), check_memory(), check_cpu()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_status(mode: str = "status") -> None:
    batt, mem, cpu = get_all()

    if mode == "json":
        print(to_json(batt, mem, cpu))
        return

    print("Resource Monitor")
    print("================")
    print()

    line = f"Battery:  {batt.status}"
    if batt.status != "N/A":
        line += f" ({batt.pct}%)"
        if batt.remaining != "—":
            line += f" {batt.remaining}"
    print(line)
    print(f"Memory:   {mem.status} ({mem.used_pct}% used, pressure: {mem.pressure})")
    print(f"CPU:      {cpu.status} ({cpu.usage}% usage)")
    print()

    has_issue = False
    if batt.status == "CRITICAL":
        print("! CRITICAL: Suspend all non-essential sessions NOW.")
        has_issue = True
    elif batt.status == "LOW":
        print("! Battery low: reduce to 2-3 sessions.")
        has_issue = True
    elif batt.status == "ON_BATTERY":
        print("* Running on battery. Monitor usage.")
        has_issue = True

    if mem.status == "CRITICAL":
        print("! CRITICAL: Memory pressure critical. Restart largest session.")
        has_issue = True
    elif mem.status == "WARNING":
        print("! Memory pressure elevated. Consider suspending idle sessions.")
        has_issue = True

    if cpu.status == "SATURATED":
        print("! CPU saturated. Avoid concurrent builds.")
        has_issue = True

    if not has_issue:
        print("All resources nominal.")


def print_pressure_report(mode: str = "status") -> None:
    report = build_pressure_report()
    if mode == "json":
        print(pressure_report_json(report))
        return

    print("Mac Resource Pressure")
    print("=====================")
    print(f"Battery: {report.battery.status} ({report.battery.pct}%)")
    print(f"Memory:  {report.memory.status} ({report.memory.used_pct}% used, pressure: {report.memory.pressure})")
    print(f"CPU:     {report.cpu.status} ({report.cpu.usage}% usage)")
    print()
    print(report.safety_note)
    print()
    if not report.groups:
        print("No process samples available.")
        return

    print("Top process groups:")
    for group in report.groups:
        ownership = "cnb-owned" if group.cnb_owned else "external"
        print(
            f"  [{group.severity}] {group.name}: cpu={group.cpu:.1f}% rss={group.rss_mb}MB "
            f"processes={group.count} {ownership}"
        )
        print(f"      pids: {', '.join(str(pid) for pid in group.pids[:8])}")
        print(f"      top: {group.top_command}")
        print(f"      next: {group.recommendation}")


def main() -> None:
    mode = "status"
    include_processes = False
    for arg in sys.argv[1:]:
        if arg == "--watch":
            mode = "watch"
        elif arg == "--json":
            mode = "json"
        elif arg in {"--processes", "--pressure"}:
            include_processes = True

    if include_processes:
        print_pressure_report(mode)
        return

    if mode == "watch":
        print("Resource monitor started (interval: 30s)")
        board_cmd = None
        try:
            from lib.common import find_claudes_dir

            bc = find_claudes_dir().parent / "board"
            if bc.exists():
                board_cmd = str(bc)
        except Exception:
            pass

        while True:
            batt, mem, cpu = get_all()
            notify_if_changed(batt, mem, cpu, board_cmd)
            time.sleep(30)
    else:
        print_status(mode)


if __name__ == "__main__":
    main()
