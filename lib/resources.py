#!/usr/bin/env python3
"""resources.py -- Unified resource monitoring (battery + memory + CPU).

Detects anomalies and notifies via board.

Usage:
    ./lib/resources.py              # One-shot status check
    ./lib/resources.py --watch      # Continuous monitoring (30s interval)
    ./lib/resources.py --json       # Machine-readable output
"""

import json
import re
import shutil
import subprocess
import sys
import time
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


# ---------------------------------------------------------------------------
# Detection helpers (macOS-specific)
# ---------------------------------------------------------------------------


def _run(cmd: str, default: str = "") -> str:
    """Run a shell command and return stdout, or *default* on failure."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else default
    except Exception:
        return default


def check_battery() -> BatteryInfo:
    if not shutil.which("pmset"):
        return BatteryInfo(status="N/A", pct=100, on_battery=False, remaining="—")

    batt_info = _run("pmset -g batt")
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
        mp_out = _run("memory_pressure 2>/dev/null | tail -1")
        if "critical" in mp_out.lower():
            pressure = "critical"
            status = "CRITICAL"
        elif "warn" in mp_out.lower():
            pressure = "warn"
            status = "WARNING"

    if shutil.which("vm_stat"):
        vm_out = _run("vm_stat")
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

            total_bytes_str = _run("sysctl -n hw.memsize", "0")
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
        top_out = _run("top -l 1 -n 0 2>/dev/null")
        for line in top_out.splitlines():
            if "CPU usage" in line:
                m = re.search(r"([\d.]+)%\s*idle", line)
                if m:
                    idle = float(m.group(1))
                    usage = int(round(100 - idle))
                break

    if usage >= CPU_SATURATED:
        status = "SATURATED"

    return CPUInfo(status=status, usage=usage)


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


def main() -> None:
    mode = "status"
    for arg in sys.argv[1:]:
        if arg == "--watch":
            mode = "watch"
        elif arg == "--json":
            mode = "json"

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
