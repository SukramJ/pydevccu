"""
XML-RPC server for pydevccu.

This module provides the legacy XML-RPC server implementation for simulating
a HomeMatic CCU. It handles device management, parameter operations, and
event callbacks to connected clients.

Classes:
    RPCFunctions: XML-RPC method implementations for HomeMatic protocol.
    RequestHandler: HTTP request handler for XML-RPC endpoints.
    ServerThread: Threaded XML-RPC server wrapper.
"""

# ruff: noqa: N802  # XML-RPC method names must be camelCase per HomeMatic protocol
# pylint: disable=invalid-name  # Required for HomeMatic API compatibility
from __future__ import annotations

from collections.abc import Callable
import contextlib
import datetime
from functools import cache
import logging
import os
import sys
import threading
from typing import Any, Protocol, cast
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from pydevccu.converter import CONVERTABLE_PARAMETERS, convert_combined_parameter_to_paramset
from pydevccu.device_responses import compute_response_events

from . import compat, const, device_logic
from .proxy import LockingServerProxy

# Package version - used for Homegear mode version string
PYDEVCCU_VERSION = "0.2.0"


class LogicDevice(Protocol):
    """Define interface for device logic simulation classes."""

    name: str
    active: bool

    def work(self) -> None:
        """Run the main work loop for device simulation."""
        ...


class RPCError(Exception):
    """Exception raised for XML-RPC operation errors."""


LOG = logging.getLogger(__name__)
if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)


def init_paramsets() -> None:
    """Initialize an empty paramsets database file."""
    with open(const.PARAMSETS_DB, "w") as fptr:
        fptr.write("{}")


def _load_json_file(path: str) -> Any:
    """Load JSON from file efficiently, using orjson if available."""
    with open(path, "rb") as fptr:
        return compat.loads(fptr.read())


# Note: This class needs many attributes for device/paramset management and caching.
# XML-RPC methods must be instance methods for register_instance() discovery.
# pylint: disable=too-many-instance-attributes,no-self-use
class RPCFunctions:
    """
    XML-RPC method implementations for HomeMatic CCU simulation.

    This class provides all XML-RPC methods that a HomeMatic CCU exposes,
    including device management, parameter operations, and system functions.

    Attributes:
        remotes: Dictionary of registered callback clients.
        devices: List of all device descriptions.
        paramset_descriptions: Parameter set schemas per device address.
        paramsets: Current parameter values per device address.
        device_by_address: Fast lookup index for devices by address.

    """

    def _dispatch(self, method: str, params: tuple[Any, ...]) -> Any:
        """Dispatch XML-RPC method calls with logging."""
        LOG.debug("XML-RPC dispatch: method=%s, params=%s", method, params)
        func = getattr(self, method, None)
        if func is None:
            LOG.warning("XML-RPC method not found: %s", method)
            raise AttributeError(f"Method {method} not found")
        return func(*params)

    def __init__(
        self,
        devices: list[str] | None,
        persistence: bool,
        logic: dict[str, Any] | bool,
        version: str | None = None,
    ) -> None:
        """
        Initialize RPCFunctions with device configuration.

        Args:
            devices: List of device type names to load, or None for all.
            persistence: Whether to persist paramsets to disk.
            logic: Device logic configuration dict or False to disable.
            version: Version string to return from getVersion. Defaults to pydevccu version.

        """
        LOG.debug("RPCFunctions.__init__")
        self.remotes: dict[str, LockingServerProxy] = {}
        self._version = version or f"pydevccu-{PYDEVCCU_VERSION}"
        try:
            self.active: bool = False
            self.known_devices: list[dict[str, Any]] = []
            self.interface_id: str = "pydevccu"
            self.persistence: bool = persistence
            self.devices: list[dict[str, Any]] = []
            self.paramset_descriptions: dict[str, Any] = {}
            self.supported_devices: dict[str, str] = {}
            self.paramsets: dict[str, Any] = {}
            self.paramset_callbacks: list[Callable[..., Any]] = []
            self.active_devices: list[str] = []
            self.logic: dict[str, Any] | bool = logic
            self.logic_devices: list[LogicDevice] = []
            # Index for fast address-based lookups to avoid O(n) scans
            self.device_by_address: dict[str, dict[str, Any]] = {}
            # Caches for paramset handling
            self._paramset_defaults: dict[tuple[str, str], dict[str, Any]] = {}
            self._paramset_compiled: dict[tuple[str, str], dict[str, Any]] = {}
            self._paramset_dirty: set[tuple[str, str]] = set()
            self._load_devices(devices)
            if not os.path.exists(const.PARAMSETS_DB) and persistence:
                init_paramsets()
            self._load_paramsets()
        except (OSError, ValueError, KeyError) as err:
            LOG.debug("RPCFunctions.__init__: Exception: %s", err)
            self.devices = []

    def _start_logic_device(self, devname: str) -> None:
        """Start logic simulation for a device type if configured."""
        if not self.logic or devname not in device_logic.DEVICE_MAP:
            return
        logic_cls = device_logic.DEVICE_MAP[devname]
        logic_config = self.logic if isinstance(self.logic, dict) else {}
        logic_device = cast(LogicDevice, logic_cls(self, **logic_config))
        logic_device.active = True
        self.logic_devices.append(logic_device)
        thread = threading.Thread(name=logic_device.name, target=logic_device.work, daemon=True)
        thread.start()

    def _load_devices(self, devices: list[str] | None = None) -> list[dict[str, Any]]:
        added_devices = []
        if devices is not None:
            LOG.info("RPCFunctions._load_devices: Limiting to devices: %s", devices)
        script_dir = os.path.dirname(__file__)
        dd_path = os.path.join(script_dir, const.DEVICE_DESCRIPTIONS)
        pd_path = os.path.join(script_dir, const.PARAMSET_DESCRIPTIONS)
        for filename in os.listdir(dd_path):
            devname = filename.split(".")[0].replace("_", " ")
            if devname in self.active_devices:
                continue
            if devices is not None and devname not in devices:
                continue
            dd = _load_json_file(os.path.join(dd_path, filename))
            self.devices.extend(dd)
            added_devices.extend(dd)
            for device in dd:
                d_addr = device.get(const.ATTR_ADDRESS)
                if isinstance(d_addr, str):
                    self.device_by_address[d_addr.upper()] = device
                if ":" not in d_addr:
                    self.supported_devices[devname] = d_addr
                    break
            pd = _load_json_file(os.path.join(pd_path, filename))
            self.paramset_descriptions.update(pd)
            self._start_logic_device(devname)
            self.active_devices.append(devname)
        return added_devices

    def _clear_address_caches(self, address: str) -> None:
        """Clear all caches for a device address."""
        addr_upper = address.upper()
        self.device_by_address.pop(addr_upper, None)
        self.paramset_descriptions.pop(address, None)
        self.paramsets.pop(address, None)
        for paramset_key in (const.PARAMSET_ATTR_VALUES, const.PARAMSET_ATTR_MASTER):
            key = (addr_upper, paramset_key)
            self._paramset_defaults.pop(key, None)
            self._paramset_compiled.pop(key, None)
            self._paramset_dirty.discard(key)

    def _device_matches_type(self, device: dict[str, Any], devname: str) -> bool:
        """Check if a device or channel belongs to a device type."""
        address = device.get(const.ATTR_ADDRESS, "")
        if ":" not in address:
            return device.get(const.ATTR_TYPE) == devname
        return device.get(const.ATTR_PARENT_TYPE) == devname

    def _remove_devices(self, devices: list[str] | None = None) -> None:
        remove_devices = devices if devices is not None else self.active_devices[:]
        addresses = []
        for devname in remove_devices:
            self.active_devices = [d for d in self.active_devices if d != devname]
            self.supported_devices.pop(devname, None)
            for dd in self.devices:
                if not self._device_matches_type(dd, devname):
                    continue
                address = dd.get(const.ATTR_ADDRESS)
                if address is not None:
                    addresses.append(address)
                    self._clear_address_caches(address)
            for logic_device in self.logic_devices[:]:
                if logic_device.name == devname:
                    logic_device.active = False
                    self.logic_devices.remove(logic_device)
        self.devices = [d for d in self.devices if d.get(const.ATTR_ADDRESS) not in addresses]
        self._clear_method_caches()
        for interface_id, proxy in self.remotes.items():
            proxy.deleteDevices(interface_id, addresses)

    def _clear_method_caches(self) -> None:
        """Clear function-level caches after device set changes."""
        for cache_method in (self.getDeviceDescription, self.getParamsetDescription, self.getMetadata):
            with contextlib.suppress(AttributeError):
                cache_method.cache_clear()

    def _load_paramsets(self) -> None:
        if self.persistence:
            self.paramsets = _load_json_file(const.PARAMSETS_DB)

    def _save_paramsets(self) -> None:
        LOG.debug("Saving paramsets")
        if self.persistence:
            with open(const.PARAMSETS_DB, "wb") as fptr:
                fptr.write(compat.dumps(self.paramsets))

    def _ask_devices(self, interface_id: str) -> None:
        self.known_devices = self.remotes[interface_id].listDevices(interface_id)
        LOG.debug("RPCFunctions._ask_devices: %s", self.known_devices)
        t = threading.Thread(name="_push_devices", target=self._push_devices, args=(interface_id,))
        t.start()

    def _push_devices(self, interface_id: str) -> None:
        """Push new and deleted devices to a registered client."""
        new_device_list = []
        delete_device_list = []
        known_addresses = set()
        for device in self.known_devices:
            if device[const.ATTR_ADDRESS] not in self.paramset_descriptions:
                delete_device_list.append(device[const.ATTR_ADDRESS])
            else:
                known_addresses.add(device[const.ATTR_ADDRESS])
        for device in self.devices:
            if device[const.ATTR_ADDRESS] not in known_addresses:
                new_device_list.append(device)
        if new_device_list:
            self.remotes[interface_id].newDevices(interface_id, new_device_list)
        if delete_device_list:
            self.remotes[interface_id].deleteDevices(interface_id, delete_device_list)
        LOG.debug(
            "RPCFunctions._push_devices: pushed new: %i, deleted: %i",
            len(new_device_list),
            len(delete_device_list),
        )

    def _fire_event(self, interface_id: str, address: str, value_key: str, value: Any) -> None:
        address = address.upper()
        LOG.debug("RPCFunctions._fire_event: %s, %s, %s, %s", interface_id, address, value_key, value)
        for callback in self.paramset_callbacks:
            callback(interface_id, address, value_key, value)
        delete_clients: list[str] = []
        for pinterface_id, proxy in self.remotes.items():
            try:
                proxy.event(pinterface_id, address, value_key, value)
            except (ConnectionError, TimeoutError, OSError):
                delete_clients.append(pinterface_id)
        for client in delete_clients:
            LOG.exception("RPCFunctions._fire_event: Exception. Deleting client: %s", client)
            del self.remotes[client]

    def listDevices(self, interface_id: str | None = None) -> list[dict[str, Any]]:
        LOG.debug("RPCFunctions.listDevices: interface_id = %s", interface_id)
        return self.devices

    def getServiceMessages(self) -> list[list[Any]]:
        LOG.debug("RPCFunctions.getServiceMessages")
        return [["VCU0000001:1", const.ATTR_ERROR, 7]]

    def ping(self, caller_id: str | None = None) -> bool:
        """Handle ping request from client."""
        LOG.debug("RPCFunctions.ping: caller_id=%s", caller_id)
        return True

    def getAllSystemVariables(self) -> dict[str, Any]:
        LOG.debug("RPCFunctions.getAllSystemVariables")
        return {"sys_var1": "str_var", "sys_var2": 13}

    def getSystemVariable(self, name: str) -> str:
        LOG.debug("RPCFunctions.getSystemVariable %s", name)
        return str(datetime.datetime.now())

    def deleteSystemVariable(self, name: str) -> None:
        LOG.debug("RPCFunctions.deleteSystemVariable %s", name)

    def setSystemVariable(self, name: str, value: Any) -> None:
        LOG.debug("RPCFunctions.setSystemVariable %s: %s", name, value)

    def getValue(self, address: str, value_key: str) -> Any:
        address = address.upper()
        LOG.debug("RPCFunctions.getValue: address=%s, value_key=%s", address, value_key)
        return self.getParamset(address, const.PARAMSET_ATTR_VALUES)[value_key]

    def setValue(self, address: str, value_key: str, value: Any, force: bool = False) -> str:
        address = address.upper()
        LOG.debug(
            "RPCFunctions.setValue: address=%s, value_key=%s, value=%s, force=%s", address, value_key, value, force
        )
        if value_key in CONVERTABLE_PARAMETERS:
            paramset = convert_combined_parameter_to_paramset(value_key, value)
        else:
            paramset = {value_key: value}
        self.putParamset(address, const.PARAMSET_ATTR_VALUES, paramset, force=force)
        return ""

    def _convert_param_value(self, value: Any, param_type: str) -> Any:
        """Convert value to the appropriate type for the parameter."""
        if param_type == const.PARAMSET_TYPE_BOOL:
            return bool(value)
        if param_type == const.PARAMSET_TYPE_STRING:
            return str(value)
        if param_type in (const.PARAMSET_TYPE_INTEGER, const.PARAMSET_TYPE_ENUM):
            return int(float(value))
        if param_type == const.PARAMSET_TYPE_FLOAT:
            return float(value)
        return value

    def _validate_enum_bounds(self, value: int, param_data: dict[str, Any], address: str, value_key: str) -> None:
        """Validate enum value is within bounds, raise RPCError if not."""
        if isinstance(param_data[const.PARAMSET_ATTR_MAX], str):
            return
        if value > float(param_data[const.PARAMSET_ATTR_MAX]):
            LOG.warning("putParamset: address=%s, value_key=%s: value too high", address, value_key)
            raise RPCError
        if value < float(param_data[const.PARAMSET_ATTR_MIN]):
            LOG.warning("putParamset: address=%s, value_key=%s: value too low", address, value_key)
            raise RPCError

    def _clamp_numeric_value(self, value: Any, param_data: dict[str, Any], param_type: str) -> int | float:
        """Clamp numeric value to bounds, respecting special values."""
        special_values: set[Any] = set()
        for entry in param_data.get(const.PARAMSET_ATTR_SPECIAL, []):
            for _, v in entry:
                special_values.add(v)
        value = int(value) if param_type == const.PARAMSET_TYPE_INTEGER else float(value)
        if value in special_values:
            return value
        max_val = param_data[const.PARAMSET_ATTR_MAX]
        min_val = param_data[const.PARAMSET_ATTR_MIN]
        if param_type == const.PARAMSET_TYPE_INTEGER:
            return max(int(min_val), min(int(max_val), value))
        return max(float(min_val), min(float(max_val), value))

    def putParamset(self, address: str, paramset_key: str, paramset: dict[str, Any], force: bool = False) -> None:
        address = address.upper()
        LOG.debug(
            "RPCFunctions.putParamset: address=%s, paramset_key=%s, paramset=%s, force=%s",
            address,
            paramset_key,
            paramset,
            force,
        )
        param_descriptions = self.paramset_descriptions[address][paramset_key]
        device_type = self._get_device_type(address)

        for value_key, value in paramset.items():
            param_data = param_descriptions[value_key]
            param_type = param_data[const.ATTR_TYPE]

            if not (force or const.PARAMSET_OPERATIONS_WRITE & param_data[const.PARAMSET_ATTR_OPERATIONS]):
                LOG.warning("putParamset: address=%s, value_key=%s: write not allowed", address, value_key)
                raise RPCError

            if param_type == const.PARAMSET_TYPE_ACTION:
                self._fire_event(self.interface_id, address, value_key, True)
                return

            value = self._convert_param_value(value, param_type)
            if param_type == const.PARAMSET_TYPE_ENUM:
                self._validate_enum_bounds(value, param_data, address, value_key)
            elif param_type in (const.PARAMSET_TYPE_FLOAT, const.PARAMSET_TYPE_INTEGER):
                value = self._clamp_numeric_value(value, param_data, param_type)

            self.paramsets.setdefault(address, {}).setdefault(paramset_key, {})[value_key] = value
            self._paramset_dirty.add((address, paramset_key))

            current_values = self.paramsets[address].get(paramset_key, {})
            response_events = compute_response_events(device_type, value_key, value, current_values)
            for resp_key, resp_value in response_events.items():
                self.paramsets[address][paramset_key][resp_key] = resp_value
                self._fire_event(self.interface_id, address, resp_key, resp_value)

    def _get_device_type(self, address: str) -> str:
        """Get the device type for an address (device or channel)."""
        device = self.device_by_address.get(address.upper())
        if device is None:
            return ""

        # If it's a channel, get parent type
        parent_type = device.get(const.ATTR_PARENT_TYPE)
        if parent_type:
            return parent_type

        # It's a device, return its type
        return device.get(const.ATTR_TYPE, "")

    @cache  # noqa: B019 - cache cleared in _clear_method_caches
    def getDeviceDescription(self, address: str) -> dict[str, Any]:
        address = address.upper()
        LOG.debug("RPCFunctions.getDeviceDescription: address=%s", address)
        device = self.device_by_address.get(address)
        if device is not None:
            return device
        raise RPCError

    @cache  # noqa: B019 - cache cleared in _clear_method_caches
    def getParamsetDescription(self, address: str, paramset_type: str) -> dict[str, Any]:
        address = address.upper()
        LOG.debug("RPCFunctions.getParamsetDescription: address=%s, paramset_type=%s", address, paramset_type)
        return self.paramset_descriptions[address][paramset_type]

    def getParamset(self, address: str, paramset_key: str, mode: str | None = None) -> dict[str, Any]:
        address = address.upper()
        LOG.debug("RPCFunctions.getParamset: address=%s, paramset_key=%s", address, paramset_key)
        if mode is not None:
            LOG.debug("RPCFunctions.getParamset: mode argument not supported")
            raise RPCError
        if paramset_key not in [const.PARAMSET_ATTR_MASTER, const.PARAMSET_ATTR_VALUES]:
            raise RPCError
        key = (address, paramset_key)
        # Return cached compiled paramset if available and not dirty
        if key in self._paramset_compiled and key not in self._paramset_dirty:
            return self._paramset_compiled[key]
        # Build defaults lazily
        defaults = self._paramset_defaults.get(key)
        if defaults is None:
            pd = self.paramset_descriptions[address][paramset_key]
            built = {}
            for parameter, pdata in pd.items():
                if pdata[const.ATTR_FLAGS] & const.PARAMSET_FLAG_INTERNAL:
                    continue
                value = pdata[const.PARAMSET_ATTR_DEFAULT]
                if pdata[const.ATTR_TYPE] == const.PARAMSET_TYPE_ENUM and not isinstance(value, int):
                    value = pdata[const.PARAMSET_ATTR_VALUE_LIST].index(value)
                built[parameter] = value
            defaults = built
            self._paramset_defaults[key] = defaults
        # Compose result as defaults + current overrides
        result = defaults.copy()
        try:
            overrides = self.paramsets[address][paramset_key]
            result.update(overrides)
        except KeyError:
            pass  # No overrides stored for this address/paramset
        # Store compiled and mark clean
        self._paramset_compiled[key] = result
        if key in self._paramset_dirty:
            self._paramset_dirty.discard(key)
        return result

    def init(self, url: str, interface_id: str | None = None) -> str:
        LOG.debug("RPCFunctions.init: url=%s, interface_id=%s", url, interface_id)
        if interface_id is not None:
            try:
                self.remotes[interface_id] = LockingServerProxy(url)
                t = threading.Thread(name="_ask_devices", target=self._ask_devices, args=(interface_id,))
                t.start()
            except (OSError, ValueError, ConnectionError) as err:
                LOG.debug("RPCFunctions.init: Exception: %s", err)
        else:
            deletedremote: str | None = None
            for remote, proxy in self.remotes.items():
                if proxy.uri in url or url in proxy.uri:
                    deletedremote = remote
                    break
            if deletedremote is not None:
                del self.remotes[deletedremote]
        return ""

    def getVersion(self) -> str:
        LOG.debug("RPCFunctions.getVersion")
        return self._version

    @cache  # noqa: B019 - cache cleared in _clear_method_caches
    def getMetadata(self, object_id: str, data_id: str) -> Any:
        LOG.debug("RPCFunctions.getMetadata: object_id=%s, data_id=%s", object_id, data_id)
        address = object_id.upper().partition(":")[0]
        if (device := self.device_by_address.get(address)) is None:
            raise RPCError
        if data_id in device:
            return device.get(data_id)
        if data_id == const.ATTR_NAME:
            if device.get(const.ATTR_CHILDREN):
                return f"{device.get(const.ATTR_TYPE)} {device.get(const.ATTR_ADDRESS)}"
            return f"{device.get(const.ATTR_PARENT_TYPE)} {device.get(const.ATTR_ADDRESS)}"
        return None

    def setMetadata(self, address: str, data_id: str, value: Any) -> bool:
        """Set metadata for a device."""
        LOG.debug("RPCFunctions.setMetadata: address=%s, data_id=%s, value=%s", address, data_id, value)
        # Store metadata (simplified implementation)
        return True

    def addLink(self, sender_address: str, receiver_address: str, name: str, description: str) -> bool:
        """Add a link between devices."""
        LOG.debug("RPCFunctions.addLink: %s -> %s, name=%s", sender_address, receiver_address, name)
        return True

    def removeLink(self, sender_address: str, receiver_address: str) -> bool:
        """Remove a link between devices."""
        LOG.debug("RPCFunctions.removeLink: %s -> %s", sender_address, receiver_address)
        return True

    def getLinkPeers(self, channel_address: str) -> list[str]:
        """Return link peers for a channel."""
        LOG.debug("RPCFunctions.getLinkPeers: %s", channel_address)
        return []

    def getLinks(self, channel_address: str, flags: int) -> list[dict[str, Any]]:
        """Return links for a channel."""
        LOG.debug("RPCFunctions.getLinks: %s, flags=%s", channel_address, flags)
        return []

    def getInstallMode(self) -> int:
        """Return remaining install mode time."""
        LOG.debug("RPCFunctions.getInstallMode")
        return 0

    def setInstallMode(self, on: bool = True, time: int = 60, mode: int = 1, device_address: str | None = None) -> bool:
        """Set install mode."""
        LOG.debug("RPCFunctions.setInstallMode: on=%s, time=%s, mode=%s, device=%s", on, time, mode, device_address)
        return True

    def reportValueUsage(self, channel_address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage to the backend."""
        LOG.debug("RPCFunctions.reportValueUsage: %s, %s, %s", channel_address, value_id, ref_counter)
        return True

    def installFirmware(self, device_address: str) -> bool:
        """Install firmware on a device."""
        LOG.debug("RPCFunctions.installFirmware: %s", device_address)
        return True

    def updateFirmware(self, device_address: str) -> bool:
        """Update firmware on a device."""
        LOG.debug("RPCFunctions.updateFirmware: %s", device_address)
        return True

    def clientServerInitialized(self, interface_id: str) -> bool:
        LOG.debug("RPCFunctions.clientServerInitialized")
        LOG.debug(self.remotes)
        return interface_id in self.remotes


class RequestHandler(SimpleXMLRPCRequestHandler):
    """We handle requests to / and /RPC2."""

    rpc_paths = (
        "/",
        "/RPC2",
    )


class ServerThread(threading.Thread):
    """XML-RPC server thread to handle messages from CCU / Homegear."""

    def __init__(
        self,
        addr: tuple[str, int] = (const.IP_LOCALHOST_V4, const.PORT_RF),
        devices: list[str] | None = None,
        persistence: bool = False,
        logic: dict[str, Any] | bool = False,
        version: str | None = None,
    ) -> None:
        LOG.debug("ServerThread.__init__")
        threading.Thread.__init__(self)
        self.addr = addr
        LOG.debug("__init__: Registering RPC methods")
        self._rpcfunctions = RPCFunctions(devices, persistence, logic, version=version)
        LOG.debug("ServerThread.__init__: Setting up server")
        self.server = SimpleXMLRPCServer(addr, requestHandler=RequestHandler, logRequests=True, allow_none=True)
        self.server.register_introspection_functions()
        self.server.register_multicall_functions()
        LOG.debug("ServerThread.__init__: Registering RPC functions")
        self.server.register_instance(self._rpcfunctions, allow_dotted_names=True)

        # Override system.listMethods to include instance methods
        # Python's register_introspection_functions() doesn't list instance methods
        rpc_instance = self._rpcfunctions

        def list_methods_with_instance() -> list[str]:
            # Get system methods from funcs
            methods = set(self.server.funcs.keys())
            # Add all public methods from RPCFunctions instance
            for name in dir(rpc_instance):
                if not name.startswith("_") and callable(getattr(rpc_instance, name, None)):
                    methods.add(name)
            result = sorted(methods)
            LOG.debug("system.listMethods returning: %s", result)
            return result

        self.server.register_function(list_methods_with_instance, "system.listMethods")

    def run(self) -> None:
        LOG.info("Starting server at http://%s:%i", self.addr[0], self.addr[1])
        self._rpcfunctions.active = True
        self.server.serve_forever()

    def stop(self) -> None:
        """Shut down our XML-RPC server."""
        self._rpcfunctions.active = False
        for logic_device in self._rpcfunctions.logic_devices:
            logic_device.active = False
        self._rpcfunctions._save_paramsets()
        LOG.info("Shutting down server")
        self.server.shutdown()
        LOG.debug("ServerThread.stop: Stopping ServerThread")
        self.server.server_close()
        LOG.info("Server stopped")

    # Convenience methods at server scope
    def setValue(self, address: str, value_key: str, value: Any, force: bool = False) -> str:
        return self._rpcfunctions.setValue(address, value_key, value, force)

    def getValue(self, address: str, value_key: str) -> Any:
        return self._rpcfunctions.getValue(address, value_key)

    def getDeviceDescription(self, address: str) -> dict[str, Any]:
        return self._rpcfunctions.getDeviceDescription(address)

    def getParamsetDescription(self, address: str, paramset: str) -> dict[str, Any]:
        return self._rpcfunctions.getParamsetDescription(address, paramset)

    def getParamset(self, address: str, paramset: str) -> dict[str, Any]:
        return self._rpcfunctions.getParamset(address, paramset)

    def putParamset(self, address: str, paramset_key: str, paramset: dict[str, Any], force: bool = False) -> None:
        return self._rpcfunctions.putParamset(address, paramset_key, paramset, force)

    def listDevices(self) -> list[dict[str, Any]]:
        return self._rpcfunctions.listDevices()

    def getServiceMessages(self) -> list[list[Any]]:
        return self._rpcfunctions.getServiceMessages()

    def supportedDevices(self) -> dict[str, str]:
        return self._rpcfunctions.supported_devices

    def addDevices(self, devices: list[str] | None = None) -> None:
        loaded_devices = self._rpcfunctions._load_devices(devices=devices)
        for interface_id, proxy in self._rpcfunctions.remotes.items():
            LOG.debug("addDevices: Pushing new devices to %s", interface_id)
            proxy.newDevices(interface_id, loaded_devices)

    def removeDevices(self, devices: list[str] | None = None) -> None:
        self._rpcfunctions._remove_devices(devices)
