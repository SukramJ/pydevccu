"""
Unified state management for pydevccu.

Manages all CCU state including devices, programs, system variables,
rooms, functions, and system information with thread-safety.
"""

from __future__ import annotations

import contextlib
import secrets
import threading
import time
from typing import TYPE_CHECKING, Any, Final

from pydevccu.const import BackendMode
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

if TYPE_CHECKING:
    from collections.abc import Callable


class StateManager:
    """
    Unified state management for pydevccu.

    Manages all CCU state including devices, programs, system variables,
    rooms, functions, and system information. All public methods are
    thread-safe.
    """

    def __init__(
        self,
        *,
        mode: BackendMode = BackendMode.OPENCCU,
        serial: str = "PYDEVCCU0001",
    ) -> None:
        self._mode: Final = mode
        self._serial: Final = serial
        self._lock = threading.RLock()

        # Backend info
        self._backend_info = BackendInfo(
            product="OpenCCU" if mode == BackendMode.OPENCCU else "CCU",
        )

        # Programs (indexed by ID)
        self._programs: dict[int, Program] = {}
        self._next_program_id: int = 1000

        # System variables (indexed by ID and name)
        self._sysvars: dict[int, SystemVariable] = {}
        self._sysvar_by_name: dict[str, SystemVariable] = {}
        self._next_sysvar_id: int = 2000

        # Rooms and functions
        self._rooms: dict[int, Room] = {}
        self._next_room_id: int = 3000
        self._functions: dict[int, Function] = {}
        self._next_function_id: int = 4000

        # Service messages
        self._service_messages: list[ServiceMessage] = []
        self._next_service_msg_id: int = 5000

        # Inbox devices
        self._inbox_devices: list[InboxDevice] = []

        # Backup state
        self._backup_status = BackupStatus(status="idle")
        self._backup_data: bytes = b""

        # Update info
        self._update_info = UpdateInfo()

        # Device values cache (for fetch_all_device_data)
        self._device_values: dict[str, Any] = {}

        # Device/Channel names
        self._device_names: dict[str, str] = {}

        # Event callbacks
        self._sysvar_callbacks: list[Callable[[str, Any], None]] = []
        self._program_callbacks: list[Callable[[int, bool], None]] = []

    @property
    def mode(self) -> BackendMode:
        """Get current backend mode."""
        return self._mode

    # ─────────────────────────────────────────────────────────────────
    # Backend Info
    # ─────────────────────────────────────────────────────────────────

    def get_backend_info(self) -> BackendInfo:
        """Get backend information."""
        with self._lock:
            return BackendInfo(
                version=self._backend_info.version,
                product=self._backend_info.product,
                hostname=self._backend_info.hostname,
                is_ha_addon=self._backend_info.is_ha_addon,
            )

    def set_backend_info(
        self,
        *,
        version: str | None = None,
        product: str | None = None,
        hostname: str | None = None,
        is_ha_addon: bool | None = None,
    ) -> None:
        """Update backend information."""
        with self._lock:
            if version is not None:
                self._backend_info.version = version
            if product is not None:
                self._backend_info.product = product
            if hostname is not None:
                self._backend_info.hostname = hostname
            if is_ha_addon is not None:
                self._backend_info.is_ha_addon = is_ha_addon

    def get_serial(self) -> str:
        """Get CCU serial number (last 10 chars)."""
        return self._serial[-10:]

    # ─────────────────────────────────────────────────────────────────
    # Programs
    # ─────────────────────────────────────────────────────────────────

    def add_program(
        self,
        *,
        name: str,
        description: str = "",
        active: bool = True,
        program_id: int | None = None,
    ) -> Program:
        """Add a new program."""
        with self._lock:
            if program_id is None:
                program_id = self._next_program_id
                self._next_program_id += 1
            program = Program(
                id=program_id,
                name=name,
                description=description,
                active=active,
            )
            self._programs[program.id] = program
            return program

    def get_programs(self) -> list[Program]:
        """Get all programs."""
        with self._lock:
            return list(self._programs.values())

    def get_program(self, program_id: int) -> Program | None:
        """Get program by ID."""
        with self._lock:
            return self._programs.get(program_id)

    def get_program_by_name(self, name: str) -> Program | None:
        """Get program by name."""
        with self._lock:
            for prog in self._programs.values():
                if prog.name == name:
                    return prog
            return None

    def execute_program(self, program_id: int) -> bool:
        """Execute a program."""
        with self._lock:
            program = self._programs.get(program_id)
            if program and program.active:
                program.last_execute_time = time.time()
                for callback in self._program_callbacks:
                    with contextlib.suppress(Exception):
                        callback(program_id, True)
                return True
            return False

    def set_program_active(self, program_id: int, active: bool) -> bool:
        """Enable/disable a program."""
        with self._lock:
            if program := self._programs.get(program_id):
                program.active = active
                return True
            return False

    def delete_program(self, program_id: int) -> bool:
        """Delete a program."""
        with self._lock:
            if program_id in self._programs:
                del self._programs[program_id]
                return True
            return False

    # ─────────────────────────────────────────────────────────────────
    # System Variables
    # ─────────────────────────────────────────────────────────────────

    def add_system_variable(
        self,
        *,
        name: str,
        var_type: str,
        value: Any,
        description: str = "",
        unit: str = "",
        value_list: str | None = None,
        min_value: float = 0.0,
        max_value: float = 100.0,
        sysvar_id: int | None = None,
    ) -> SystemVariable:
        """Add a new system variable."""
        with self._lock:
            if sysvar_id is None:
                sysvar_id = self._next_sysvar_id
                self._next_sysvar_id += 1
            sysvar = SystemVariable(
                id=sysvar_id,
                name=name,
                var_type=var_type,
                value=value,
                description=description,
                unit=unit,
                value_list=value_list,
                min_value=min_value,
                max_value=max_value,
            )
            self._sysvars[sysvar.id] = sysvar
            self._sysvar_by_name[name] = sysvar
            return sysvar

    def get_system_variables(self) -> list[SystemVariable]:
        """Get all system variables."""
        with self._lock:
            return list(self._sysvars.values())

    def get_system_variable(self, name: str) -> SystemVariable | None:
        """Get system variable by name."""
        with self._lock:
            return self._sysvar_by_name.get(name)

    def get_system_variable_by_id(self, sysvar_id: int) -> SystemVariable | None:
        """Get system variable by ID."""
        with self._lock:
            return self._sysvars.get(sysvar_id)

    def set_system_variable(self, name: str, value: Any) -> bool:
        """Set system variable value."""
        with self._lock:
            if sysvar := self._sysvar_by_name.get(name):
                sysvar.value = value
                sysvar.timestamp = time.time()
                for callback in self._sysvar_callbacks:
                    with contextlib.suppress(Exception):
                        callback(name, value)
                return True
            return False

    def set_system_variable_by_id(self, sysvar_id: int, value: Any) -> bool:
        """Set system variable value by ID."""
        with self._lock:
            if sysvar := self._sysvars.get(sysvar_id):
                sysvar.value = value
                sysvar.timestamp = time.time()
                for callback in self._sysvar_callbacks:
                    with contextlib.suppress(Exception):
                        callback(sysvar.name, value)
                return True
            return False

    def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable."""
        with self._lock:
            if sysvar := self._sysvar_by_name.get(name):
                del self._sysvars[sysvar.id]
                del self._sysvar_by_name[name]
                return True
            return False

    # ─────────────────────────────────────────────────────────────────
    # Rooms & Functions
    # ─────────────────────────────────────────────────────────────────

    def add_room(
        self,
        *,
        name: str,
        description: str = "",
        channel_ids: list[str] | None = None,
        room_id: int | None = None,
    ) -> Room:
        """Add a new room."""
        with self._lock:
            if room_id is None:
                room_id = self._next_room_id
                self._next_room_id += 1
            room = Room(
                id=room_id,
                name=name,
                description=description,
                channel_ids=channel_ids or [],
            )
            self._rooms[room_id] = room
            return room

    def get_rooms(self) -> list[Room]:
        """Get all rooms."""
        with self._lock:
            return list(self._rooms.values())

    def get_room(self, room_id: int) -> Room | None:
        """Get room by ID."""
        with self._lock:
            return self._rooms.get(room_id)

    def add_channel_to_room(self, room_id: int, channel_id: str) -> bool:
        """Add a channel to a room."""
        with self._lock:
            if room := self._rooms.get(room_id):
                if channel_id not in room.channel_ids:
                    room.channel_ids.append(channel_id)
                return True
            return False

    def remove_channel_from_room(self, room_id: int, channel_id: str) -> bool:
        """Remove a channel from a room."""
        with self._lock:
            if room := self._rooms.get(room_id):
                if channel_id in room.channel_ids:
                    room.channel_ids.remove(channel_id)
                return True
            return False

    def add_function(
        self,
        *,
        name: str,
        description: str = "",
        channel_ids: list[str] | None = None,
        function_id: int | None = None,
    ) -> Function:
        """Add a new function (Gewerk)."""
        with self._lock:
            if function_id is None:
                function_id = self._next_function_id
                self._next_function_id += 1
            func = Function(
                id=function_id,
                name=name,
                description=description,
                channel_ids=channel_ids or [],
            )
            self._functions[function_id] = func
            return func

    def get_functions(self) -> list[Function]:
        """Get all functions."""
        with self._lock:
            return list(self._functions.values())

    def get_function(self, function_id: int) -> Function | None:
        """Get function by ID."""
        with self._lock:
            return self._functions.get(function_id)

    def add_channel_to_function(self, function_id: int, channel_id: str) -> bool:
        """Add a channel to a function."""
        with self._lock:
            if func := self._functions.get(function_id):
                if channel_id not in func.channel_ids:
                    func.channel_ids.append(channel_id)
                return True
            return False

    # ─────────────────────────────────────────────────────────────────
    # Service Messages
    # ─────────────────────────────────────────────────────────────────

    def add_service_message(
        self,
        *,
        name: str,
        msg_type: str,
        address: str,
        device_name: str,
    ) -> ServiceMessage:
        """Add a service message."""
        with self._lock:
            msg = ServiceMessage(
                id=self._next_service_msg_id,
                name=name,
                timestamp=time.time(),
                msg_type=msg_type,
                address=address,
                device_name=device_name,
            )
            self._next_service_msg_id += 1
            self._service_messages.append(msg)
            return msg

    def get_service_messages(self) -> list[ServiceMessage]:
        """Get all active service messages."""
        with self._lock:
            return list(self._service_messages)

    def clear_service_message(self, msg_id: int) -> bool:
        """Remove a service message."""
        with self._lock:
            for i, msg in enumerate(self._service_messages):
                if msg.id == msg_id:
                    self._service_messages.pop(i)
                    return True
            return False

    def clear_all_service_messages(self) -> int:
        """Clear all service messages. Returns count of cleared messages."""
        with self._lock:
            count = len(self._service_messages)
            self._service_messages.clear()
            return count

    # ─────────────────────────────────────────────────────────────────
    # Inbox Devices
    # ─────────────────────────────────────────────────────────────────

    def add_inbox_device(
        self,
        *,
        address: str,
        name: str,
        device_type: str,
        interface: str,
    ) -> InboxDevice:
        """Add device to inbox."""
        with self._lock:
            device = InboxDevice(
                device_id=secrets.token_hex(8),
                address=address,
                name=name,
                device_type=device_type,
                interface=interface,
            )
            self._inbox_devices.append(device)
            return device

    def get_inbox_devices(self) -> list[InboxDevice]:
        """Get all inbox devices."""
        with self._lock:
            return list(self._inbox_devices)

    def accept_inbox_device(self, address: str) -> bool:
        """Accept device from inbox."""
        with self._lock:
            for i, dev in enumerate(self._inbox_devices):
                if dev.address == address:
                    self._inbox_devices.pop(i)
                    return True
            return False

    def reject_inbox_device(self, address: str) -> bool:
        """Reject device from inbox."""
        return self.accept_inbox_device(address)  # Same operation

    # ─────────────────────────────────────────────────────────────────
    # Backup
    # ─────────────────────────────────────────────────────────────────

    def start_backup(self) -> str:
        """Start backup operation. Returns PID."""
        with self._lock:
            pid = secrets.token_hex(4)
            self._backup_status = BackupStatus(status="running", pid=pid)
            return pid

    def complete_backup(self, data: bytes, filename: str) -> None:
        """Complete backup with data."""
        with self._lock:
            self._backup_data = data
            self._backup_status = BackupStatus(
                status="completed",
                filename=filename,
                filepath=f"/tmp/{filename}",  # noqa: S108  # nosec B108
                size=len(data),
            )

    def fail_backup(self, error: str = "Backup failed") -> None:
        """Mark backup as failed."""
        with self._lock:
            self._backup_status = BackupStatus(status="failed")

    def get_backup_status(self) -> dict[str, Any]:
        """Get current backup status."""
        with self._lock:
            status = self._backup_status
            return {
                "status": status.status,
                "pid": status.pid,
                "filename": status.filename,
                "filepath": status.filepath,
                "size": status.size,
            }

    def get_backup_data(self) -> bytes:
        """Get backup file data."""
        with self._lock:
            return self._backup_data

    def reset_backup(self) -> None:
        """Reset backup state to idle."""
        with self._lock:
            self._backup_status = BackupStatus(status="idle")
            self._backup_data = b""

    # ─────────────────────────────────────────────────────────────────
    # Firmware Update
    # ─────────────────────────────────────────────────────────────────

    def set_update_info(
        self,
        *,
        current: str,
        available: str,
    ) -> None:
        """Set firmware update information."""
        with self._lock:
            self._update_info = UpdateInfo(
                current_firmware=current,
                available_firmware=available,
                update_available=(current != available),
            )

    def get_update_info(self) -> UpdateInfo:
        """Get firmware update information."""
        with self._lock:
            return UpdateInfo(
                current_firmware=self._update_info.current_firmware,
                available_firmware=self._update_info.available_firmware,
                update_available=self._update_info.update_available,
            )

    def trigger_update(self) -> bool:
        """Trigger firmware update (simulation)."""
        with self._lock:
            if not self._update_info.update_available:
                return False
            self._update_info.current_firmware = self._update_info.available_firmware
            self._update_info.update_available = False
            return True

    # ─────────────────────────────────────────────────────────────────
    # Device Values (for fetch_all_device_data)
    # ─────────────────────────────────────────────────────────────────

    def set_device_value(self, address: str, value_key: str, value: Any) -> None:
        """Set device value in cache."""
        with self._lock:
            key = f"{address}:{value_key}"
            self._device_values[key] = value

    def get_device_value(self, address: str, value_key: str) -> Any | None:
        """Get device value from cache."""
        with self._lock:
            key = f"{address}:{value_key}"
            return self._device_values.get(key)

    def get_all_device_values(self, *, interface: str | None = None) -> dict[str, Any]:
        """Get all device values."""
        with self._lock:
            # In full impl, would filter by interface
            return dict(self._device_values)

    def clear_device_values(self) -> None:
        """Clear all cached device values."""
        with self._lock:
            self._device_values.clear()

    # ─────────────────────────────────────────────────────────────────
    # Device/Channel Names
    # ─────────────────────────────────────────────────────────────────

    def set_device_name(self, address: str, name: str) -> None:
        """Set custom device/channel name."""
        with self._lock:
            self._device_names[address.upper()] = name

    def get_device_name(self, address: str) -> str | None:
        """Get custom device/channel name."""
        with self._lock:
            return self._device_names.get(address.upper())

    def get_all_device_names(self) -> dict[str, str]:
        """Get all custom device/channel names."""
        with self._lock:
            return dict(self._device_names)

    # ─────────────────────────────────────────────────────────────────
    # Callbacks
    # ─────────────────────────────────────────────────────────────────

    def register_sysvar_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Register callback for system variable changes."""
        with self._lock:
            self._sysvar_callbacks.append(callback)

    def unregister_sysvar_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Unregister system variable callback."""
        with self._lock:
            if callback in self._sysvar_callbacks:
                self._sysvar_callbacks.remove(callback)

    def register_program_callback(self, callback: Callable[[int, bool], None]) -> None:
        """Register callback for program execution."""
        with self._lock:
            self._program_callbacks.append(callback)

    def unregister_program_callback(self, callback: Callable[[int, bool], None]) -> None:
        """Unregister program callback."""
        with self._lock:
            if callback in self._program_callbacks:
                self._program_callbacks.remove(callback)

    # ─────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────

    def clear_all(self) -> None:
        """Clear all state (for testing)."""
        with self._lock:
            self._programs.clear()
            self._sysvars.clear()
            self._sysvar_by_name.clear()
            self._rooms.clear()
            self._functions.clear()
            self._service_messages.clear()
            self._inbox_devices.clear()
            self._device_values.clear()
            self._device_names.clear()
            self._backup_status = BackupStatus(status="idle")
            self._backup_data = b""
            self._update_info = UpdateInfo()
