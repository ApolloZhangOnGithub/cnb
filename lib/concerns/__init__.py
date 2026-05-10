"""Dispatcher concerns package.

Each concern is a self-contained module with its own check interval.
"""

from .adaptive_throttle import AdaptiveThrottle
from .base import Concern
from .config import DispatcherConfig
from .coral import CoralManager, CoralPoker
from .health import HealthChecker, ResourceMonitor, SessionKeepAlive
from .helpers import log, tmux_ok, warn
from .idle import IdleDetector, IdleKiller
from .notifications import BugSLAChecker, TimeAnnouncer
from .nudge_coordinator import NudgeCoordinator

__all__ = [
    "AdaptiveThrottle",
    "BugSLAChecker",
    "Concern",
    "CoralManager",
    "CoralPoker",
    "DispatcherConfig",
    "HealthChecker",
    "IdleDetector",
    "IdleKiller",
    "NudgeCoordinator",
    "ResourceMonitor",
    "SessionKeepAlive",
    "TimeAnnouncer",
    "log",
    "tmux_ok",
    "warn",
]
