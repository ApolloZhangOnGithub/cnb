"""Dispatcher concerns package.

Each concern is a self-contained module with its own check interval.
"""

from .adaptive_throttle import AdaptiveThrottle
from .base import Concern
from .config import DispatcherConfig
from .coral import CoralManager, CoralPoker
from .health import HealthChecker, ResourceMonitor, SessionKeepAlive
from .helpers import log, tmux_ok, warn
from .idle import IdleDetector, IdleKiller, IdleNudger
from .notifications import BugSLAChecker, InboxNudger, ManagerCloseoutEscalator, QueuedMessageFlusher, TimeAnnouncer
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
    "IdleNudger",
    "InboxNudger",
    "ManagerCloseoutEscalator",
    "NudgeCoordinator",
    "QueuedMessageFlusher",
    "ResourceMonitor",
    "SessionKeepAlive",
    "TimeAnnouncer",
    "log",
    "tmux_ok",
    "warn",
]
