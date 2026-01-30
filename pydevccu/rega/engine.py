"""
Simplified ReGa script engine for pydevccu.

Instead of implementing a full ReGa interpreter, this engine:
1. Recognizes common script patterns used by aiohomematic
2. Extracts parameters and returns appropriate JSON responses
3. Accesses StateManager for actual data

This covers the actual ReGa scripts in aiohomematic/rega_scripts/
without needing a full language implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import TYPE_CHECKING, Any, Final
import urllib.parse

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydevccu.ccu import RPCFunctions
    from pydevccu.state import StateManager

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegaScriptResult:
    """Result of ReGa script execution."""

    output: str
    success: bool = True
    error: str | None = None


class RegaEngine:
    """
    Simplified ReGa script engine for pydevccu.

    Uses pattern matching to handle common aiohomematic scripts.
    """

    def __init__(
        self,
        *,
        state_manager: StateManager,
        rpc_functions: RPCFunctions | None = None,
    ) -> None:
        self._state: Final = state_manager
        self._rpc: Final = rpc_functions

        # Pattern handlers: (regex pattern, handler method)
        self._patterns: list[tuple[re.Pattern[str], Callable[[str], str]]] = [
            # get_backend_info.fn - grep VERSION and PRODUCT from /VERSION
            (
                re.compile(r"system\.Exec.*cat.*/VERSION", re.DOTALL | re.IGNORECASE),
                self._handle_backend_info,
            ),
            (
                re.compile(r"grep.*VERSION.*grep.*PRODUCT", re.DOTALL | re.IGNORECASE),
                self._handle_backend_info,
            ),
            # get_serial.fn - match by name header or content pattern
            (
                re.compile(r"name:\s*get_serial\.fn", re.IGNORECASE),
                self._handle_get_serial,
            ),
            (
                re.compile(r"system\.GetVar\s*\(\s*[\"']?SERIALNO[\"']?\s*\)", re.IGNORECASE),
                self._handle_get_serial,
            ),
            # fetch_all_device_data.fn - match by name header or content pattern
            (
                re.compile(r"name:\s*fetch_all_device_data\.fn", re.IGNORECASE),
                self._handle_fetch_device_data,
            ),
            (
                re.compile(
                    r"foreach\s*\(\s*\w+\s*,\s*dom\.GetObject\s*\(\s*ID_DATAPOINTS",
                    re.DOTALL | re.IGNORECASE,
                ),
                self._handle_fetch_device_data,
            ),
            # get_program_descriptions.fn
            (
                re.compile(
                    r"dom\.GetObject\s*\(\s*ID_PROGRAMS\s*\)",
                    re.IGNORECASE,
                ),
                self._handle_get_programs,
            ),
            # get_system_variable_descriptions.fn
            (
                re.compile(
                    r"dom\.GetObject\s*\(\s*ID_SYSTEM_VARIABLES\s*\)",
                    re.IGNORECASE,
                ),
                self._handle_get_sysvars,
            ),
            # get_service_messages.fn
            (
                re.compile(
                    r"dom\.GetObject\s*\(\s*ID_SERVICES\s*\)",
                    re.IGNORECASE,
                ),
                self._handle_get_service_messages,
            ),
            # get_inbox_devices.fn - looks for INBOX
            (
                re.compile(r"INBOX", re.IGNORECASE),
                self._handle_get_inbox,
            ),
            # set_program_state.fn - Active(true/false)
            (
                re.compile(
                    r"dom\.GetObject\s*\(\s*(\d+)\s*\)\.Active\s*\(\s*(true|false)\s*\)",
                    re.IGNORECASE,
                ),
                self._handle_set_program_state,
            ),
            # set_system_variable.fn - .State("value")
            (
                re.compile(
                    r'dom\.GetObject\s*\(\s*"([^"]+)"\s*\)\.State\s*\(\s*"?([^")]*)"?\s*\)',
                    re.IGNORECASE,
                ),
                self._handle_set_sysvar,
            ),
            # create_backup_start.fn
            (
                re.compile(r"CreateBackup", re.IGNORECASE),
                self._handle_backup_start,
            ),
            # create_backup_status.fn
            (
                re.compile(r"backup\.pid|backup_status|BACKUP_STATUS", re.IGNORECASE),
                self._handle_backup_status,
            ),
            # get_system_update_info.fn
            (
                re.compile(r"checkFirmwareUpdate|CHECK_FIRMWARE_UPDATE", re.IGNORECASE),
                self._handle_update_info,
            ),
            # trigger_firmware_update.fn
            (
                re.compile(r"nohup.*checkFirmwareUpdate.*-a|TRIGGER_UPDATE", re.IGNORECASE),
                self._handle_trigger_update,
            ),
            # get_rooms.fn
            (
                re.compile(r"ID_ROOMS", re.IGNORECASE),
                self._handle_get_rooms,
            ),
            # get_functions.fn
            (
                re.compile(r"ID_FUNCTIONS", re.IGNORECASE),
                self._handle_get_functions,
            ),
            # Simple Write() pattern - just echo output
            (
                re.compile(r"^Write\s*\(\s*\"([^\"]*)\"\s*\)\s*;?\s*$", re.IGNORECASE),
                self._handle_write,
            ),
        ]

    def execute(self, script: str) -> RegaScriptResult:
        """
        Execute a ReGa script and return result.

        Args:
            script: The ReGa script source code.

        Returns:
            RegaScriptResult with output and status.

        """
        LOG.debug("ReGa execute: %s...", script[:100] if len(script) > 100 else script)

        # Try each pattern in order
        for pattern, handler in self._patterns:
            if pattern.search(script):
                try:
                    output = handler(script)
                    return RegaScriptResult(output=output, success=True)
                except Exception as ex:
                    LOG.exception("ReGa handler error")
                    return RegaScriptResult(
                        output="",
                        success=False,
                        error=str(ex),
                    )

        # Unknown script pattern - return empty success
        LOG.warning("Unknown ReGa script pattern: %s...", script[:100])
        return RegaScriptResult(
            output="",
            success=True,
            error=None,
        )

    def _handle_backend_info(self, script: str) -> str:
        """Handle get_backend_info.fn pattern."""
        info = self._state.get_backend_info()
        return json.dumps(
            {
                "version": info.version,
                "product": info.product,
                "hostname": info.hostname,
                "is_ha_addon": info.is_ha_addon,
            },
            ensure_ascii=False,
        )

    def _handle_get_serial(self, script: str) -> str:
        """
        Handle get_serial.fn pattern.

        Returns the serial as a JSON-encoded string so aiohomematic can parse it.
        """
        return json.dumps(self._state.get_serial())

    def _handle_fetch_device_data(self, script: str) -> str:
        """Handle fetch_all_device_data.fn pattern."""
        # Extract interface parameter if present (two formats)
        # Format 1: interface = "HmIP-RF"
        # Format 2: !# param: "HmIP-RF"
        interface_match = re.search(r'interface\s*=\s*"([^"]+)"', script)
        if not interface_match:
            interface_match = re.search(r'param:\s*"([^"]+)"', script)
        interface = interface_match.group(1) if interface_match else None

        # Get all device values
        data = self._state.get_all_device_values(interface=interface)

        # Format as expected by aiohomematic
        result: list[dict[str, Any]] = []
        for key, value in data.items():
            parts = key.split(":")
            if len(parts) >= 2:
                address = ":".join(parts[:-1])
                param = parts[-1]
                result.append(
                    {
                        "address": address,
                        "param": param,
                        "value": value,
                    }
                )

        return json.dumps(result, ensure_ascii=False)

    def _handle_get_programs(self, script: str) -> str:
        """Handle get_program_descriptions.fn pattern."""
        programs = self._state.get_programs()
        result = []

        for prog in programs:
            result.append(
                {
                    "id": prog.id,
                    "name": urllib.parse.quote(prog.name),
                    "description": urllib.parse.quote(prog.description or ""),
                    "isActive": prog.active,
                    "isInternal": False,
                    "lastExecuteTime": prog.last_execute_time,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_get_sysvars(self, script: str) -> str:
        """Handle get_system_variable_descriptions.fn pattern."""
        sysvars = self._state.get_system_variables()
        result = []

        for sv in sysvars:
            result.append(
                {
                    "id": sv.id,
                    "name": urllib.parse.quote(sv.name),
                    "description": urllib.parse.quote(sv.description or ""),
                    "unit": sv.unit or "",
                    "type": sv.var_type,
                    "value": sv.value,
                    "valueList": sv.value_list or "",
                    "minValue": sv.min_value,
                    "maxValue": sv.max_value,
                    "timestamp": sv.timestamp,
                    "isInternal": False,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_get_service_messages(self, script: str) -> str:
        """Handle get_service_messages.fn pattern."""
        messages = self._state.get_service_messages()
        result = []

        for msg in messages:
            result.append(
                {
                    "id": msg.id,
                    "name": msg.name,
                    "timestamp": msg.timestamp,
                    "type": msg.msg_type,
                    "address": msg.address,
                    "deviceName": msg.device_name,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_get_inbox(self, script: str) -> str:
        """Handle get_inbox_devices.fn pattern."""
        devices = self._state.get_inbox_devices()
        result = []

        for dev in devices:
            result.append(
                {
                    "deviceId": dev.device_id,
                    "address": dev.address,
                    "name": dev.name,
                    "deviceType": dev.device_type,
                    "interface": dev.interface,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_set_program_state(self, script: str) -> str:
        """Handle set_program_state.fn pattern."""
        match = re.search(
            r"dom\.GetObject\s*\(\s*(\d+)\s*\)\.Active\s*\(\s*(true|false)\s*\)",
            script,
            re.IGNORECASE,
        )
        if match:
            program_id = int(match.group(1))
            active = match.group(2).lower() == "true"
            self._state.set_program_active(program_id, active)

        return ""

    def _handle_set_sysvar(self, script: str) -> str:
        """Handle set_system_variable.fn pattern."""
        match = re.search(
            r'dom\.GetObject\s*\(\s*"([^"]+)"\s*\)\.State\s*\(\s*"?([^")]*)"?\s*\)',
            script,
            re.IGNORECASE,
        )
        if match:
            name = match.group(1)
            value = match.group(2)

            # Try to parse as number
            try:
                value = float(value) if "." in value else int(value)
            except ValueError:
                # Check for boolean
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                # Otherwise keep as string

            self._state.set_system_variable(name, value)

        return ""

    def _handle_backup_start(self, script: str) -> str:
        """Handle create_backup_start.fn pattern."""
        pid = self._state.start_backup()
        return json.dumps(
            {
                "success": True,
                "status": "started",
                "pid": pid,
            }
        )

    def _handle_backup_status(self, script: str) -> str:
        """Handle create_backup_status.fn pattern."""
        status = self._state.get_backup_status()
        return json.dumps(status)

    def _handle_update_info(self, script: str) -> str:
        """Handle get_system_update_info.fn pattern."""
        info = self._state.get_update_info()
        return json.dumps(
            {
                "currentFirmware": info.current_firmware,
                "availableFirmware": info.available_firmware,
                "updateAvailable": info.update_available,
                "checkScriptAvailable": True,
            }
        )

    def _handle_trigger_update(self, script: str) -> str:
        """Handle trigger_firmware_update.fn pattern."""
        self._state.trigger_update()
        return json.dumps({"success": True})

    def _handle_get_rooms(self, script: str) -> str:
        """Handle get_rooms pattern."""
        rooms = self._state.get_rooms()
        result = []

        for room in rooms:
            result.append(
                {
                    "id": room.id,
                    "name": urllib.parse.quote(room.name),
                    "description": urllib.parse.quote(room.description or ""),
                    "channelIds": room.channel_ids,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_get_functions(self, script: str) -> str:
        """Handle get_functions pattern."""
        functions = self._state.get_functions()
        result = []

        for func in functions:
            result.append(
                {
                    "id": func.id,
                    "name": urllib.parse.quote(func.name),
                    "description": urllib.parse.quote(func.description or ""),
                    "channelIds": func.channel_ids,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_write(self, script: str) -> str:
        """Handle simple Write() pattern."""
        match = re.search(r'Write\s*\(\s*"([^"]*)"\s*\)', script, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""
