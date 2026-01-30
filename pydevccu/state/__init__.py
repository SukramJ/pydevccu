"""
State management package for pydevccu.

Provides unified state management for devices, programs, system variables,
rooms, functions, and system information.
"""

from __future__ import annotations

from pydevccu.state.defaults import setup_default_state
from pydevccu.state.manager import StateManager
from pydevccu.state.models import (
    BackendInfo,
    BackupStatus,
    Function,
    InboxDevice,
    Program,
    Room,
    ServiceMessage,
    SystemVariable,
    UpdateInfo,
)

__all__ = [
    "BackendInfo",
    "BackupStatus",
    "Function",
    "InboxDevice",
    "Program",
    "Room",
    "ServiceMessage",
    "StateManager",
    "SystemVariable",
    "UpdateInfo",
    "setup_default_state",
]
