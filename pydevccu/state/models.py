"""
Data models for pydevccu state management.

All models are dataclasses representing CCU entities like programs,
system variables, rooms, functions, and system information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class BackendInfo:
    """CCU backend information."""

    version: str = "3.87.1.20250130"
    product: str = "OpenCCU"
    hostname: str = "pydevccu"
    is_ha_addon: bool = False


@dataclass
class Program:
    """CCU program."""

    id: int
    name: str
    description: str = ""
    active: bool = True
    last_execute_time: float = 0.0


@dataclass
class SystemVariable:
    """CCU system variable."""

    id: int
    name: str
    var_type: str  # "BOOL", "FLOAT", "STRING", "ENUM"
    value: Any
    description: str = ""
    unit: str = ""
    value_list: str | None = None  # For ENUM: "val1;val2;val3"
    min_value: float = 0.0
    max_value: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class Room:
    """CCU room."""

    id: int
    name: str
    description: str = ""
    channel_ids: list[str] = field(default_factory=list)


@dataclass
class Function:
    """CCU function (Gewerk)."""

    id: int
    name: str
    description: str = ""
    channel_ids: list[str] = field(default_factory=list)


@dataclass
class ServiceMessage:
    """CCU service message."""

    id: int
    name: str
    timestamp: float
    msg_type: str  # "UNREACH", "CONFIG_PENDING", "LOWBAT", etc.
    address: str
    device_name: str


@dataclass
class InboxDevice:
    """Device in CCU inbox awaiting pairing."""

    device_id: str
    address: str
    name: str
    device_type: str
    interface: str


@dataclass
class BackupStatus:
    """Backup operation status."""

    status: str  # "idle", "running", "completed", "failed"
    pid: str = ""
    filename: str = ""
    filepath: str = ""
    size: int = 0


@dataclass
class UpdateInfo:
    """Firmware update information."""

    current_firmware: str = "3.87.1.20250130"
    available_firmware: str = "3.87.1.20250130"
    update_available: bool = False


@dataclass
class DeviceName:
    """Custom device/channel name mapping."""

    address: str
    name: str
