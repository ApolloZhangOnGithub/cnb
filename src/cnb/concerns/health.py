"""Health monitoring: session keepalive, periodic health checks, resource monitoring."""

import time

from lib.common import date_to_epoch, is_suspended
from lib.resources import check_battery, check_cpu, check_memory

from .base import Concern
from .config import DispatcherConfig
from .coral import CoralManager, CoralPoker
from .helpers import (
    board_send,
    db,
    get_dev_sessions,
    is_claude_running,
    log,
    tmux_ok,
    tmux_send,
)


class SessionKeepAlive(Concern):
    interval = 5

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            if is_suspended(name, self.cfg.suspended_file):
                continue
            sess = f"{self.cfg.prefix}-{name}"
            if tmux_ok("has-session", "-t", sess) and not is_claude_running(sess):
                log(f"{name}: 同学已退出, NOT restarting (idle policy)")


class HealthChecker(Concern):
    INITIAL = 600
    MAX = 3600
    IDLE_THRESHOLD = 1800

    def __init__(self, cfg: DispatcherConfig, poker: CoralPoker, coral: CoralManager) -> None:
        super().__init__()
        self.cfg = cfg
        self.interval = self.INITIAL
        self.poker = poker
        self.coral = coral
        self.last_idle_alert: int = 0

    def tick(self, now: int) -> None:
        parts = []
        for name in get_dev_sessions(self.cfg):
            on = "on" if tmux_ok("has-session", "-t", f"{self.cfg.prefix}-{name}") else "off"
            parts.append(f"{name}:{on}")
        status = " ".join(parts)

        log(f"Health check (interval:{self.interval}s): {status}")
        self.poker.poke(f"[Dispatcher] 健康巡检 {time.strftime('%H:%M:%S')}: {status}")
        self.interval = min(self.interval * 2, self.MAX)
        self._check_team_idle(now)

    def _check_team_idle(self, now: int) -> None:
        if not self.cfg.board_db.exists():
            return
        idle_list: list[str] = []
        total = 0
        d = db(self.cfg)

        for name in get_dev_sessions(self.cfg):
            if is_suspended(name, self.cfg.suspended_file):
                continue
            sess = f"{self.cfg.prefix}-{name}"
            if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
                continue
            if self.coral.in_grace_period(name, now):
                continue

            total += 1
            try:
                updated = d.scalar("SELECT updated_at FROM sessions WHERE name=?", (name,)) or ""
            except Exception:
                continue
            if updated:
                age = now - date_to_epoch(updated)
                if age > self.IDLE_THRESHOLD:
                    idle_list.append(f"{name}({age}s)")

        if idle_list and len(idle_list) == total and (now - self.last_idle_alert) > 3600:
            log(f"All sessions idle: {' '.join(idle_list)}")
            board_send(
                self.cfg,
                "lead",
                f"[Dispatcher] 全员空闲超过 {self.IDLE_THRESHOLD // 60} 分钟:{' '.join(idle_list)}。可能需要分配工作。",
            )
            self.last_idle_alert = now


class ResourceMonitor(Concern):
    interval = 60

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.last_state = ""

    def tick(self, now: int) -> None:
        batt = check_battery()
        mem = check_memory()
        cpu = check_cpu()

        state = f"{batt.status}|{batt.pct}|{mem.status}|{mem.pressure}|{cpu.status}|{cpu.usage}"
        if state == self.last_state:
            return
        self.last_state = state

        if batt.status == "CRITICAL":
            log(f"RESOURCE: Battery CRITICAL ({batt.pct}%)")
            board_send(self.cfg, "All", f"[Resource] 电池严重不足 ({batt.pct}%)，暂停非关键 session。")
            for name in get_dev_sessions(self.cfg):
                sess = f"{self.cfg.prefix}-{name}"
                if is_claude_running(sess):
                    tmux_send(sess, "[系统] 电池严重不足，请立即保存状态。")
        elif batt.status == "LOW":
            log(f"RESOURCE: Battery LOW ({batt.pct}%)")
            board_send(self.cfg, "All", f"[Resource] 电池低 ({batt.pct}%)，建议减少活跃 session 到 2-3 个。")

        if mem.status == "CRITICAL":
            log("RESOURCE: Memory pressure CRITICAL")
            board_send(self.cfg, "All", "[Resource] 内存压力严重！建议重启最大的 session 释放内存。")
        elif mem.status == "WARNING":
            log("RESOURCE: Memory pressure WARNING")
            board_send(self.cfg, "All", "[Resource] 内存压力升高，关注中。")

        if cpu.status == "SATURATED":
            log(f"RESOURCE: CPU saturated ({cpu.usage}%)")
