"""ResourceMonitor — battery/memory/CPU."""

from lib.resources import check_battery, check_cpu, check_memory

from .base import Concern
from .config import DispatcherConfig
from .helpers import board_send, get_dev_sessions, is_claude_running, log, tmux_send


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
