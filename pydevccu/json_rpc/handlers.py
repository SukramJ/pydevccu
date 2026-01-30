"""
JSON-RPC method handlers for pydevccu.

Implements all CCU/OpenCCU JSON-RPC methods organized by namespace.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohttp import web

from pydevccu.json_rpc.errors import InvalidParams, ObjectNotFound

if TYPE_CHECKING:
    from pydevccu.ccu import RPCFunctions
    from pydevccu.rega import RegaEngine
    from pydevccu.session import SessionManager
    from pydevccu.state import StateManager

LOG = logging.getLogger(__name__)

# Type alias for handler functions
HandlerFunc = Callable[[dict[str, Any]], Awaitable[Any]]


class JsonRpcHandlers:
    """
    JSON-RPC method handlers for CCU/OpenCCU API.

    Provides all method implementations organized by namespace:
    - Session: login, logout, renew
    - CCU: getAuthEnabled, getHttpsRedirectEnabled
    - Interface: device operations
    - Device/Channel: metadata operations
    - Program: program management
    - SysVar: system variable management
    - Room/Subsection: room and function management
    - ReGa: script execution
    """

    def __init__(
        self,
        *,
        state_manager: StateManager,
        session_manager: SessionManager,
        rega_engine: RegaEngine | None = None,
        rpc_functions: RPCFunctions | None = None,
    ) -> None:
        self._state: Final = state_manager
        self._session: Final = session_manager
        self._rega: Final = rega_engine
        self._rpc: Final = rpc_functions

    def get_methods(self) -> dict[str, HandlerFunc]:
        """Build method name -> handler mapping."""
        return {
            # Session Management
            "Session.login": self._handle_session_login,
            "Session.logout": self._handle_session_logout,
            "Session.renew": self._handle_session_renew,
            # System
            "CCU.getAuthEnabled": self._handle_get_auth_enabled,
            "CCU.getHttpsRedirectEnabled": self._handle_get_https_redirect,
            "system.listMethods": self._handle_list_methods,
            # Interface Operations
            "Interface.listInterfaces": self._handle_list_interfaces,
            "Interface.listDevices": self._handle_list_devices,
            "Interface.getDeviceDescription": self._handle_get_device_description,
            "Interface.getParamset": self._handle_get_paramset,
            "Interface.getParamsetDescription": self._handle_get_paramset_description,
            "Interface.getValue": self._handle_get_value,
            "Interface.setValue": self._handle_set_value,
            "Interface.putParamset": self._handle_put_paramset,
            "Interface.isPresent": self._handle_is_present,
            "Interface.getInstallMode": self._handle_get_install_mode,
            "Interface.setInstallMode": self._handle_set_install_mode,
            "Interface.setInstallModeHMIP": self._handle_set_install_mode_hmip,
            "Interface.getMasterValue": self._handle_get_master_value,
            "Interface.ping": self._handle_ping,
            "Interface.init": self._handle_interface_init,
            # Device/Channel
            "Device.listAllDetail": self._handle_device_list_all_detail,
            "Device.get": self._handle_device_get,
            "Device.setName": self._handle_device_set_name,
            "Channel.setName": self._handle_channel_set_name,
            "Channel.hasProgramIds": self._handle_channel_has_program_ids,
            # Programs
            "Program.getAll": self._handle_program_get_all,
            "Program.execute": self._handle_program_execute,
            "Program.setActive": self._handle_program_set_active,
            # System Variables
            "SysVar.getAll": self._handle_sysvar_get_all,
            "SysVar.getValueByName": self._handle_sysvar_get_value_by_name,
            "SysVar.setBool": self._handle_sysvar_set_bool,
            "SysVar.setFloat": self._handle_sysvar_set_float,
            "SysVar.setString": self._handle_sysvar_set_string,
            "SysVar.deleteSysVarByName": self._handle_sysvar_delete,
            # Rooms & Functions
            "Room.getAll": self._handle_room_get_all,
            "Room.listAll": self._handle_room_get_all,  # Alias
            "Subsection.getAll": self._handle_subsection_get_all,
            # ReGa Script Execution
            "ReGa.runScript": self._handle_rega_run_script,
        }

    def get_http_routes(self) -> list[tuple[str, tuple[str, Any]]]:
        """Get HTTP routes for non-JSON-RPC endpoints."""
        return [
            ("/config/cp_security.cgi", ("GET", self._handle_backup_download)),
            ("/config/cp_maintenance.cgi", ("POST", self._handle_maintenance)),
            ("/VERSION", ("GET", self._handle_version)),
        ]

    # ─────────────────────────────────────────────────────────────────
    # Session Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_session_login(self, params: dict[str, Any]) -> Any:
        """Handle Session.login."""
        username = params.get("username", "")
        password = params.get("password", "")

        session_id = self._session.login(username, password)
        if session_id is None:
            return {"_session_id_": "", "error": "Invalid credentials"}

        return {"_session_id_": session_id}

    async def _handle_session_logout(self, params: dict[str, Any]) -> Any:
        """Handle Session.logout."""
        session_id = params.get("_session_id_", "")
        success = self._session.logout(session_id)
        return {"success": success}

    async def _handle_session_renew(self, params: dict[str, Any]) -> Any:
        """Handle Session.renew."""
        session_id = params.get("_session_id_", "")
        new_session_id = self._session.renew(session_id)
        if new_session_id is None:
            return {"_session_id_": "", "error": "Session expired"}
        return {"_session_id_": new_session_id}

    # ─────────────────────────────────────────────────────────────────
    # CCU Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_get_auth_enabled(self, params: dict[str, Any]) -> Any:
        """Handle CCU.getAuthEnabled."""
        return self._session.auth_enabled

    async def _handle_get_https_redirect(self, params: dict[str, Any]) -> Any:
        """Handle CCU.getHttpsRedirectEnabled."""
        return False

    async def _handle_list_methods(self, params: dict[str, Any]) -> Any:
        """Handle system.listMethods."""
        # Return list of dicts with "name" key (aiohomematic expects this format)
        return [{"name": method} for method in self.get_methods()]

    # ─────────────────────────────────────────────────────────────────
    # Interface Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_list_interfaces(self, params: dict[str, Any]) -> Any:
        """Handle Interface.listInterfaces."""
        # Both interfaces use the same XML-RPC server port (2010)
        xml_rpc_port = 2010

        interfaces = [
            {
                "name": "HmIP-RF",
                "port": xml_rpc_port,
                "info": "HomeMatic IP RF Interface",
                "type": "HmIP-RF",
                "available": True,
            },
            {
                "name": "BidCos-RF",
                "port": xml_rpc_port,
                "info": "HomeMatic RF Interface",
                "type": "BidCos-RF",
                "available": True,
            },
        ]

        return interfaces

    async def _handle_list_devices(self, params: dict[str, Any]) -> Any:
        """Handle Interface.listDevices."""
        # interface = params.get("interface", "") - reserved for future use
        if self._rpc is None:
            return []

        return self._rpc.listDevices()

    async def _handle_get_device_description(self, params: dict[str, Any]) -> Any:
        """Handle Interface.getDeviceDescription."""
        address = params.get("address", "")

        if not address:
            raise InvalidParams("Missing address parameter")

        if self._rpc is None:
            raise ObjectNotFound("Device", address)

        try:
            return self._rpc.getDeviceDescription(address)
        except Exception as ex:
            raise ObjectNotFound("Device", address) from ex

    async def _handle_get_paramset(self, params: dict[str, Any]) -> Any:
        """Handle Interface.getParamset."""
        address = params.get("address", "")
        paramset_key = params.get("paramsetKey", params.get("paramset_key", "VALUES"))

        if not address:
            raise InvalidParams("Missing address parameter")

        if self._rpc is None:
            return {}

        try:
            return self._rpc.getParamset(address, paramset_key)
        except Exception as ex:
            LOG.warning("getParamset failed for %s: %s", address, ex)
            return {}

    async def _handle_get_paramset_description(self, params: dict[str, Any]) -> Any:
        """Handle Interface.getParamsetDescription."""
        address = params.get("address", "")
        paramset_key = params.get("paramsetKey", params.get("paramset_key", "VALUES"))

        if not address:
            raise InvalidParams("Missing address parameter")

        if self._rpc is None:
            return {}

        try:
            return self._rpc.getParamsetDescription(address, paramset_key)
        except Exception as ex:
            LOG.warning("getParamsetDescription failed for %s: %s", address, ex)
            return {}

    async def _handle_get_value(self, params: dict[str, Any]) -> Any:
        """Handle Interface.getValue."""
        address = params.get("address", "")
        value_key = params.get("valueKey", params.get("value_key", ""))

        if not address or not value_key:
            raise InvalidParams("Missing address or valueKey parameter")

        if self._rpc is None:
            return None

        try:
            return self._rpc.getValue(address, value_key)
        except Exception:
            return None

    async def _handle_set_value(self, params: dict[str, Any]) -> Any:
        """Handle Interface.setValue."""
        address = params.get("address", "")
        value_key = params.get("valueKey", params.get("value_key", ""))
        value = params.get("value")

        if not address or not value_key:
            raise InvalidParams("Missing address or valueKey parameter")

        if self._rpc is None:
            return False

        try:
            self._rpc.setValue(address, value_key, value)
            return True
        except Exception as ex:
            LOG.warning("setValue failed for %s.%s: %s", address, value_key, ex)
            return False

    async def _handle_put_paramset(self, params: dict[str, Any]) -> Any:
        """Handle Interface.putParamset."""
        address = params.get("address", "")
        paramset_key = params.get("paramsetKey", params.get("paramset_key", "VALUES"))
        paramset = params.get("set", params.get("paramset", {}))

        if not address:
            raise InvalidParams("Missing address parameter")

        if self._rpc is None:
            return False

        try:
            self._rpc.putParamset(address, paramset_key, paramset)
            return True
        except Exception as ex:
            LOG.warning("putParamset failed for %s: %s", address, ex)
            return False

    async def _handle_is_present(self, params: dict[str, Any]) -> Any:
        """Handle Interface.isPresent."""
        address = params.get("address", "")

        if self._rpc is None:
            return False

        try:
            self._rpc.getDeviceDescription(address)
            return True
        except Exception:
            return False

    async def _handle_get_install_mode(self, params: dict[str, Any]) -> Any:
        """Handle Interface.getInstallMode."""
        return 0  # 0 = not in install mode

    async def _handle_set_install_mode(self, params: dict[str, Any]) -> Any:
        """Handle Interface.setInstallMode."""
        # mode = params.get("mode", 0)
        return True

    async def _handle_set_install_mode_hmip(self, params: dict[str, Any]) -> Any:
        """Handle Interface.setInstallModeHMIP."""
        # Similar to setInstallMode but for HmIP devices
        return True

    async def _handle_get_master_value(self, params: dict[str, Any]) -> Any:
        """Handle Interface.getMasterValue."""
        # Returns master paramset value for a device
        # For now, return empty/default value
        return ""

    async def _handle_ping(self, params: dict[str, Any]) -> Any:
        """Handle Interface.ping."""
        return True

    async def _handle_interface_init(self, params: dict[str, Any]) -> Any:
        """Handle Interface.init."""
        url = params.get("url", "")
        interface_id = params.get("interfaceId", params.get("interface_id"))

        if self._rpc is None:
            return ""

        return self._rpc.init(url, interface_id)

    # ─────────────────────────────────────────────────────────────────
    # Device/Channel Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_device_list_all_detail(self, params: dict[str, Any]) -> Any:
        """Handle Device.listAllDetail."""
        if self._rpc is None:
            return []

        all_devices = self._rpc.listDevices()
        result = []

        # First pass: identify parent devices and their channels
        parent_devices: dict[str, dict[str, Any]] = {}
        channels_by_parent: dict[str, list[dict[str, Any]]] = {}

        for device in all_devices:
            address = device.get("ADDRESS", "")
            if ":" in address:
                # This is a channel - extract parent address
                parent_address = address.split(":")[0]
                if parent_address not in channels_by_parent:
                    channels_by_parent[parent_address] = []
                channels_by_parent[parent_address].append(
                    {
                        "id": address,
                        "address": address,
                        "type": device.get("TYPE", ""),
                        "name": self._state.get_device_name(address) or address,
                        "interface": device.get("INTERFACE", "HmIP-RF"),
                    }
                )
            else:
                # This is a parent device
                parent_devices[address] = device

        # Build result with channels included
        for address, device in parent_devices.items():
            device_info = {
                "id": address,
                "address": address,
                "type": device.get("TYPE", ""),
                "name": self._state.get_device_name(address) or device.get("TYPE", ""),
                "interface": device.get("INTERFACE", "HmIP-RF"),
                "channels": channels_by_parent.get(address, []),
            }
            result.append(device_info)

        return result

    async def _handle_device_get(self, params: dict[str, Any]) -> Any:
        """Handle Device.get."""
        address = params.get("address", params.get("id", ""))

        if not address:
            raise InvalidParams("Missing address parameter")

        if self._rpc is None:
            raise ObjectNotFound("Device", address)

        try:
            device = self._rpc.getDeviceDescription(address)
            return {
                "id": address,
                "address": address,
                "type": device.get("TYPE", ""),
                "name": self._state.get_device_name(address) or device.get("TYPE", ""),
            }
        except Exception as ex:
            raise ObjectNotFound("Device", address) from ex

    async def _handle_device_set_name(self, params: dict[str, Any]) -> Any:
        """Handle Device.setName."""
        address = params.get("address", params.get("id", ""))
        name = params.get("name", "")

        if not address:
            raise InvalidParams("Missing address parameter")

        self._state.set_device_name(address, name)
        return True

    async def _handle_channel_set_name(self, params: dict[str, Any]) -> Any:
        """Handle Channel.setName."""
        address = params.get("address", params.get("id", ""))
        name = params.get("name", "")

        if not address:
            raise InvalidParams("Missing address parameter")

        self._state.set_device_name(address, name)
        return True

    async def _handle_channel_has_program_ids(self, params: dict[str, Any]) -> Any:
        """Handle Channel.hasProgramIds."""
        # Returns program IDs associated with a channel
        # For simulation, return empty list
        return []

    # ─────────────────────────────────────────────────────────────────
    # Program Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_program_get_all(self, params: dict[str, Any]) -> Any:
        """Handle Program.getAll."""
        programs = self._state.get_programs()
        result = []

        for prog in programs:
            result.append(
                {
                    "id": str(prog.id),
                    "name": prog.name,
                    "description": prog.description,
                    "isActive": prog.active,
                    "isInternal": False,
                    "lastExecuteTime": prog.last_execute_time,
                }
            )

        return result

    async def _handle_program_execute(self, params: dict[str, Any]) -> Any:
        """Handle Program.execute."""
        program_id = params.get("id", params.get("programId"))

        if program_id is None:
            raise InvalidParams("Missing id parameter")

        try:
            program_id = int(program_id)
        except (ValueError, TypeError) as ex:
            raise InvalidParams("Invalid program id") from ex

        success = self._state.execute_program(program_id)
        return {"success": success}

    async def _handle_program_set_active(self, params: dict[str, Any]) -> Any:
        """Handle Program.setActive."""
        program_id = params.get("id", params.get("programId"))
        active = params.get("active", params.get("isActive", True))

        if program_id is None:
            raise InvalidParams("Missing id parameter")

        try:
            program_id = int(program_id)
        except (ValueError, TypeError) as ex:
            raise InvalidParams("Invalid program id") from ex

        success = self._state.set_program_active(program_id, bool(active))
        return {"success": success}

    # ─────────────────────────────────────────────────────────────────
    # SysVar Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_sysvar_get_all(self, params: dict[str, Any]) -> Any:
        """Handle SysVar.getAll."""
        sysvars = self._state.get_system_variables()
        result = []

        for sv in sysvars:
            result.append(
                {
                    "id": str(sv.id),
                    "name": sv.name,
                    "description": sv.description,
                    "type": sv.var_type,
                    "value": sv.value,
                    "unit": sv.unit,
                    "valueList": sv.value_list or "",
                    "minValue": sv.min_value,
                    "maxValue": sv.max_value,
                    "timestamp": sv.timestamp,
                    "isInternal": False,
                }
            )

        return result

    async def _handle_sysvar_get_value_by_name(self, params: dict[str, Any]) -> Any:
        """Handle SysVar.getValueByName."""
        name = params.get("name", "")

        if not name:
            raise InvalidParams("Missing name parameter")

        sysvar = self._state.get_system_variable(name)
        if sysvar is None:
            raise ObjectNotFound("SystemVariable", name)

        return sysvar.value

    async def _handle_sysvar_set_bool(self, params: dict[str, Any]) -> Any:
        """Handle SysVar.setBool."""
        name = params.get("name", "")
        value = params.get("value", False)

        if not name:
            raise InvalidParams("Missing name parameter")

        success = self._state.set_system_variable(name, bool(value))
        return {"success": success}

    async def _handle_sysvar_set_float(self, params: dict[str, Any]) -> Any:
        """Handle SysVar.setFloat."""
        name = params.get("name", "")
        value = params.get("value", 0.0)

        if not name:
            raise InvalidParams("Missing name parameter")

        try:
            value = float(value)
        except (ValueError, TypeError) as ex:
            raise InvalidParams("Invalid float value") from ex

        success = self._state.set_system_variable(name, value)
        return {"success": success}

    async def _handle_sysvar_set_string(self, params: dict[str, Any]) -> Any:
        """Handle SysVar.setString."""
        name = params.get("name", "")
        value = params.get("value", "")

        if not name:
            raise InvalidParams("Missing name parameter")

        success = self._state.set_system_variable(name, str(value))
        return {"success": success}

    async def _handle_sysvar_delete(self, params: dict[str, Any]) -> Any:
        """Handle SysVar.deleteSysVarByName."""
        name = params.get("name", "")

        if not name:
            raise InvalidParams("Missing name parameter")

        success = self._state.delete_system_variable(name)
        return {"success": success}

    # ─────────────────────────────────────────────────────────────────
    # Room & Subsection Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_room_get_all(self, params: dict[str, Any]) -> Any:
        """Handle Room.getAll / Room.listAll."""
        rooms = self._state.get_rooms()
        result = []

        for room in rooms:
            result.append(
                {
                    "id": str(room.id),
                    "name": room.name,
                    "description": room.description,
                    "channelIds": room.channel_ids,
                }
            )

        return result

    async def _handle_subsection_get_all(self, params: dict[str, Any]) -> Any:
        """Handle Subsection.getAll (functions/Gewerke)."""
        functions = self._state.get_functions()
        result = []

        for func in functions:
            result.append(
                {
                    "id": str(func.id),
                    "name": func.name,
                    "description": func.description,
                    "channelIds": func.channel_ids,
                }
            )

        return result

    # ─────────────────────────────────────────────────────────────────
    # ReGa Namespace
    # ─────────────────────────────────────────────────────────────────

    async def _handle_rega_run_script(self, params: dict[str, Any]) -> Any:
        """
        Handle ReGa.runScript.

        Returns the script output directly as a string. aiohomematic expects
        the result to be a JSON string that it will parse.
        """
        script = params.get("script", "")

        if not script:
            raise InvalidParams("Missing script parameter")

        if self._rega is None:
            return ""

        result = self._rega.execute(script)
        # Return output directly - aiohomematic will parse the JSON string
        return result.output

    # ─────────────────────────────────────────────────────────────────
    # HTTP Endpoints
    # ─────────────────────────────────────────────────────────────────

    async def _handle_backup_download(self, request: web.Request) -> web.Response:
        """Handle backup file download."""
        # Check session from query parameter
        session_id = request.query.get("sid", "")
        if self._session.auth_enabled and not self._session.validate(session_id):
            return web.Response(status=401, text="Unauthorized")

        status = self._state.get_backup_status()
        if status["status"] != "completed":
            return web.Response(status=404, text="No backup available")

        data = self._state.get_backup_data()
        filename = status["filename"]

        return web.Response(
            body=data,
            content_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(data)),
            },
        )

    async def _handle_maintenance(self, request: web.Request) -> web.Response:
        """Handle maintenance operations (firmware update, etc.)."""
        # Check session
        session_id = request.query.get("sid", "")
        if self._session.auth_enabled and not self._session.validate(session_id):
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            data = await request.json()
        except Exception:
            data = {}

        action = data.get("action", "")

        if action == "checkUpdate":
            info = self._state.get_update_info()
            return web.json_response(
                {
                    "currentFirmware": info.current_firmware,
                    "availableFirmware": info.available_firmware,
                    "updateAvailable": info.update_available,
                }
            )
        if action == "triggerUpdate":
            success = self._state.trigger_update()
            return web.json_response({"success": success})
        return web.json_response({"error": "Unknown action"}, status=400)

    async def _handle_version(self, request: web.Request) -> web.Response:
        """Handle /VERSION endpoint."""
        info = self._state.get_backend_info()
        return web.Response(
            text=f"VERSION={info.version}\nPRODUCT={info.product}\n",
            content_type="text/plain",
        )
