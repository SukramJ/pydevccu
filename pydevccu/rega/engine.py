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


# _SCRIPT_NAME extracts the script identity from the header comment that
# clients ship verbatim ("!# name: fetch_all_device_data.fn").
_SCRIPT_NAME: Final = re.compile(r"^\s*!#\s*name:\s*([A-Za-z0-9_.-]+)", re.IGNORECASE | re.MULTILINE)


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

        # Name dispatch takes precedence over the pattern list below.
        # Clients ship their scripts verbatim, header included, and only
        # substitute "##var##" placeholders — so the header is a reliable
        # identity. Without it the generic patterns shadow the specific
        # scripts: set_program_state.fn contains "dom.GetObject(
        # ID_PROGRAMS)" and was answered with a program listing,
        # set_system_variable.fn with a sysvar listing,
        # accept_device_in_inbox.fn was caught by the "INBOX" catch-all
        # and create_backup_status.fn by the "/VERSION" pattern — all
        # four reported success while changing nothing.
        self._by_name: Final[dict[str, Callable[[str], str]]] = {
            "get_backend_info.fn": self._handle_backend_info,
            "get_serial.fn": self._handle_get_serial,
            "fetch_all_device_data.fn": self._handle_fetch_device_data,
            "get_alarm_messages.fn": self._handle_get_alarm_messages,
            "get_service_messages.fn": self._handle_get_service_messages,
            "get_inbox_devices.fn": self._handle_get_inbox,
            "accept_device_in_inbox.fn": self._handle_accept_inbox_device,
            "acknowledge_message.fn": self._handle_acknowledge_message,
            "set_program_state.fn": self._handle_set_program_state,
            "set_system_variable.fn": self._handle_set_sysvar,
            "get_program_descriptions.fn": self._handle_get_program_descriptions,
            "get_system_variable_descriptions.fn": self._handle_get_sysvars,
            "create_backup_start.fn": self._handle_backup_start,
            "create_backup_status.fn": self._handle_backup_status,
            "get_system_update_info.fn": self._handle_update_info,
            "trigger_firmware_update.fn": self._handle_trigger_update,
        }

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

        # Dispatch by script name first; fall back to content patterns
        # for clients that send scripts without the header.
        if (name_match := _SCRIPT_NAME.search(script)) and (
            named_handler := self._by_name.get(name_match.group(1).lower())
        ):
            try:
                return RegaScriptResult(output=named_handler(script), success=True)
            except Exception as ex:
                LOG.exception("ReGa handler error")
                return RegaScriptResult(output="", success=False, error=str(ex))

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
                # get_backend_info.fn writes "is_ha_app"; clients read the
                # script's key, so "is_ha_addon" silently degraded to the
                # client-side default.
                "is_ha_app": info.is_ha_addon,
            },
            ensure_ascii=False,
        )

    def _handle_get_serial(self, script: str) -> str:
        """
        Handle get_serial.fn.

        The script's final line is
        WriteLine('{"serial": "'# serial #'"}'), so the answer is an
        object — not a bare string. Clients cope with both, but only the
        object matches what a CCU sends.
        """
        return json.dumps({"serial": self._state.get_serial()}, ensure_ascii=False)

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

        # The script emits a JSON *object* keyed by the ReGa datapoint
        # name — Write('"'), the UriEncode()d oDP.Name(), Write('":'),
        # the value. Clients index it as
        # "<interface>.<channel_address>.<parameter>" and iterate it as a
        # mapping, so an array of {address,param,value} records made the
        # whole bulk fetch unusable.
        result: dict[str, Any] = {}
        for key, value in data.items():
            address, _, param = key.rpartition(":")
            if not address or not param:
                continue
            name = f"{address}.{param}"
            if interface:
                name = f"{interface}.{name}"
            result[urllib.parse.quote(name)] = _encode_device_value(value)

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
                    # get_inbox_devices.fn writes "id" and "type";
                    # "deviceId"/"deviceType" raised a KeyError on the
                    # client's very first inbox device.
                    "id": dev.device_id,
                    "address": dev.address,
                    "name": urllib.parse.quote(dev.name or ""),
                    "type": dev.device_type,
                    "interface": dev.interface,
                }
            )

        return json.dumps(result, ensure_ascii=False)

    def _handle_set_program_state(self, script: str) -> str:
        """
        Handle set_program_state.fn.

        The script resolves the program via
        dom.GetObject(ID_PROGRAMS).Get(p_id), flips Active(p_state) and
        writes back the resulting Active() value. The substituted script
        never matches the inline dom.GetObject(<id>).Active(<bool>)
        pattern, so this handler was dead code and the script fell
        through to the program *listing* — reporting success while the
        state never changed.
        """
        parsed = _parse_program_state(script)
        if parsed is None:
            return ""
        program_id, active = parsed
        if not self._state.set_program_active(program_id, active):
            # Unknown program: the script's "if (program)" guard fails
            # and nothing is written.
            return ""
        return "true" if active else "false"

    def _handle_set_sysvar(self, script: str) -> str:
        """
        Handle set_system_variable.fn.

        The script resolves the variable via
        dom.GetObject(ID_SYSTEM_VARIABLES).Get(sv_name) and writes
        sv_value only when the variable is of type String. The
        substituted script never matched the inline .State() pattern, so
        it fell through to the sysvar *listing* and the write was
        silently dropped.
        """
        if (name_match := re.search(r'sv_name\s*=\s*"([^"]*)"', script, re.IGNORECASE)) and (
            value_match := re.search(r'sv_value\s*=\s*"([^"]*)"', script, re.IGNORECASE)
        ):
            name = name_match.group(1)
            sysvar = self._state.get_system_variable(name)
            # The script guards on "if (target_sv)" and
            # ValueTypeStr() == "String": anything else writes nothing.
            if sysvar is None or (sysvar.var_type or "").upper() != "STRING":
                return ""
            return "true" if self._state.set_system_variable(name, value_match.group(1)) else "false"
        return self._set_sysvar_inline(script)

    def _set_sysvar_inline(self, script: str) -> str:
        """Handle the legacy dom.GetObject("name").State(value) one-liner."""
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
        # Only a completed backup carries the file details, and the key
        # is "file" (the path on the CCU) — "filepath" plus an
        # always-present "pid" never existed in the script's output.
        if status.get("status") != "completed":
            return json.dumps({"status": status.get("status")})
        return json.dumps(
            {
                "status": status["status"],
                "file": status["filepath"],
                "filename": status["filename"],
                "size": status["size"],
            }
        )

    def _handle_update_info(self, script: str) -> str:
        """Handle get_system_update_info.fn pattern."""
        info = self._state.get_update_info()
        return json.dumps(
            {
                # get_system_update_info.fn writes snake_case keys; the
                # camelCase spelling meant every client fell back to its
                # defaults — empty versions and "no update".
                "current_firmware": info.current_firmware,
                "available_firmware": info.available_firmware,
                "update_available": info.update_available,
                "check_script_available": True,
            }
        )

    def _handle_trigger_update(self, script: str) -> str:
        """Handle trigger_firmware_update.fn pattern."""
        success = self._state.trigger_update()
        return json.dumps(
            {
                "success": success,
                "script_available": True,
                "message": (
                    "Firmware update triggered, system will reboot when ready"
                    if success
                    else "No firmware update available"
                ),
            }
        )

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

    def _handle_get_alarm_messages(self, script: str) -> str:
        """
        Handle get_alarm_messages.fn.

        The script lists ID_SYSTEM_VARIABLES entries of TypeName ALARMDP
        with an active AlState. No alarm datapoints are modelled, so the
        active-alarm list is always empty — matching a CCU without
        pending alarms. Without its own handler the script's
        ID_SYSTEM_VARIABLES body is misrouted to the sysvar listing,
        whose entries lack the keys the alarm parser requires.
        """
        return "[]"

    def _handle_accept_inbox_device(self, script: str) -> str:
        """
        Handle accept_device_in_inbox.fn.

        Sets ReadyConfig on the matching device and answers with
        {"success": bool, "error": str}. The generic "INBOX" pattern used
        to return the inbox *listing* — a JSON array on which the
        client's .get("success") raises AttributeError.
        """
        match = re.search(r'sDeviceAddress\s*=\s*"([^"]*)"', script, re.IGNORECASE)
        if not match or not match.group(1):
            return _rega_result(success=False, error="Device not found")
        if not self._state.accept_inbox_device(match.group(1)):
            return _rega_result(success=False, error="Device not found")
        return _rega_result(success=True, error="")

    def _handle_acknowledge_message(self, script: str) -> str:
        """
        Handle acknowledge_message.fn.

        Receipts the service message with the given id. Previously the
        script's ID_SERVICES loop routed it to the service-message
        listing.
        """
        match = re.search(r'sMessageId\s*=\s*"([^"]*)"', script, re.IGNORECASE)
        if not match:
            return _rega_result(success=False, error="Message not found")
        try:
            message_id = int(match.group(1))
        except ValueError:
            return _rega_result(success=False, error="Message not found")
        if not self._state.clear_service_message(message_id):
            return _rega_result(success=False, error="Message not found")
        return _rega_result(success=True, error="")

    def _handle_get_program_descriptions(self, script: str) -> str:
        """
        Handle get_program_descriptions.fn.

        Emits {"id": "<string>", "description": "<uri-encoded>"} per
        program. The generic ID_PROGRAMS pattern used to answer it with
        the full Program.getAll shape, whose integer ids the client
        cannot match against its string program ids.
        """
        return json.dumps(
            [
                {
                    "id": str(prog.id),
                    "description": urllib.parse.quote(prog.description or ""),
                }
                for prog in self._state.get_programs()
            ],
            ensure_ascii=False,
        )

    def _handle_write(self, script: str) -> str:
        """Handle simple Write() pattern."""
        match = re.search(r'Write\s*\(\s*"([^"]*)"\s*\)', script, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""


def _rega_result(*, success: bool, error: str) -> str:
    """Render the {"success": …, "error": …} object the inbox and acknowledge scripts assemble."""
    return json.dumps({"success": success, "error": error})


def _encode_device_value(value: Any) -> Any:
    """
    Mirror the value branches of fetch_all_device_data.fn.

    Strings are URI-encoded, an empty string collapses to 0, everything
    else goes out as its native JSON type.
    """
    if not isinstance(value, str):
        return value
    if not value:
        return 0
    return urllib.parse.quote(value)


def _parse_program_state(script: str) -> tuple[int, bool] | None:
    """
    Read the parameters out of set_program_state.fn.

    Handles the substituted form (p_id / p_state, where the client sends
    "1" or "0") as well as the legacy inline
    dom.GetObject(<id>).Active(<bool>) one-liner.
    """
    if id_match := re.search(r'p_id\s*=\s*"([^"]*)"', script, re.IGNORECASE):
        state_match = re.search(r"p_state\s*=\s*([A-Za-z0-9]+)", script, re.IGNORECASE)
        if state_match is None:
            return None
        try:
            program_id = int(id_match.group(1))
        except ValueError:
            return None
        raw = state_match.group(1)
        return program_id, raw == "1" or raw.lower() == "true"

    if inline := re.search(
        r"dom\.GetObject\s*\(\s*(\d+)\s*\)\.Active\s*\(\s*(true|false)\s*\)",
        script,
        re.IGNORECASE,
    ):
        return int(inline.group(1)), inline.group(2).lower() == "true"

    return None
