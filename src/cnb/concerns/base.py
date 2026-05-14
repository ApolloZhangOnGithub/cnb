"""Base Concern class for dispatcher concerns."""


class Concern:
    """Base class for all dispatcher concerns.

    Each concern has an independent check interval and a tick() method
    that performs the actual work.
    """

    interval: int = 5

    def __init__(self) -> None:
        self.last_tick: int = 0

    def should_tick(self, now: int) -> bool:
        return (now - self.last_tick) >= self.interval

    def tick(self, now: int) -> None:
        raise NotImplementedError

    def maybe_tick(self, now: int) -> None:
        if self.should_tick(now):
            self.tick(now)
            self.last_tick = now
