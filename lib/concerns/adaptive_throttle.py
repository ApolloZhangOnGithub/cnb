"""AdaptiveThrottle — slow down main loop when CPU is high."""

from lib.resources import check_cpu

from .base import Concern
from .helpers import log


class AdaptiveThrottle(Concern):
    interval = 10
    HIGH = 80
    LOW = 60
    MAX_MULT = 4

    def __init__(self) -> None:
        super().__init__()
        self.multiplier: int = 1

    def tick(self, now: int) -> None:
        cpu = check_cpu()
        if cpu.usage > self.HIGH and self.multiplier < self.MAX_MULT:
            self.multiplier = min(self.multiplier * 2, self.MAX_MULT)
            log(f"THROTTLE: CPU={cpu.usage}% > {self.HIGH}%, interval x{self.multiplier}")
        elif cpu.usage < self.LOW and self.multiplier > 1:
            self.multiplier = 1
            log(f"THROTTLE: CPU={cpu.usage}% < {self.LOW}%, restored normal interval")
