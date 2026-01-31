"""
VirtualCCU orchestrator for pydevccu.

Coordinates XML-RPC, JSON-RPC, and HTTP servers to provide
a complete CCU/OpenCCU simulation for testing.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Final

from pydevccu.ccu import ServerThread as XmlRpcServer
from pydevccu.const import BackendMode
from pydevccu.json_rpc.handlers import JsonRpcHandlers
from pydevccu.json_rpc.server import JsonRpcServer
from pydevccu.rega import RegaEngine
from pydevccu.session import SessionManager
from pydevccu.state import StateManager
from pydevccu.state.defaults import setup_default_state

if TYPE_CHECKING:
    pass

LOG = logging.getLogger(__name__)


class VirtualCCU:
    """
    Complete virtual CCU/OpenCCU server.

    Orchestrates XML-RPC, JSON-RPC, and HTTP servers to provide
    a complete CCU simulation for testing.

    Example usage::

        >>> ccu = VirtualCCU(
        ...     mode=BackendMode.OPENCCU,
        ...     xml_rpc_port=2010,
        ...     json_rpc_port=8080,
        ... )
        >>> await ccu.start()
        >>> # ... run tests ...
        >>> await ccu.stop()

    Or as async context manager::

        >>> async with VirtualCCU() as ccu:
        ...     # ... run tests ...
    """

    def __init__(
        self,
        *,
        mode: BackendMode = BackendMode.OPENCCU,
        host: str = "127.0.0.1",
        xml_rpc_port: int = 2010,
        json_rpc_port: int = 80,
        username: str = "Admin",
        password: str = "",
        auth_enabled: bool = True,
        devices: list[str] | None = None,
        persistence: bool = False,
        serial: str = "PYDEVCCU0001",
        setup_defaults: bool = False,
    ) -> None:
        """
        Initialize VirtualCCU.

        Args:
            mode: Backend mode (HOMEGEAR, CCU, or OPENCCU).
            host: Host address to bind servers to.
            xml_rpc_port: Port for XML-RPC server.
            json_rpc_port: Port for JSON-RPC/HTTP server.
            username: Username for authentication.
            password: Password for authentication.
            auth_enabled: Whether to require authentication.
            devices: List of device types to load (None = all).
            persistence: Whether to persist paramsets to disk.
            serial: CCU serial number.
            setup_defaults: Whether to populate default state.

        """
        self._mode: Final = mode
        self._host: Final = host
        self._xml_rpc_port: Final = xml_rpc_port
        self._json_rpc_port: Final = json_rpc_port

        # Shared state
        self._state_manager = StateManager(mode=mode, serial=serial)
        self._session_manager = SessionManager(
            username=username,
            password=password,
            auth_enabled=auth_enabled,
        )

        # Servers (initialized on start)
        self._xml_rpc_server: XmlRpcServer | None = None
        self._json_rpc_server: JsonRpcServer | None = None
        self._rega_engine: RegaEngine | None = None
        self._handlers: JsonRpcHandlers | None = None

        # Configuration
        self._devices = devices
        self._persistence = persistence
        self._setup_defaults = setup_defaults

        # Runtime state
        self._running = False
        self._lock = threading.RLock()

    @property
    def state_manager(self) -> StateManager:
        """Access state manager for test setup."""
        return self._state_manager

    @property
    def session_manager(self) -> SessionManager:
        """Access session manager."""
        return self._session_manager

    @property
    def mode(self) -> BackendMode:
        """Get current backend mode."""
        return self._mode

    @property
    def is_running(self) -> bool:
        """Check if servers are running."""
        return self._running

    @property
    def xml_rpc_port(self) -> int:
        """Get XML-RPC server port."""
        return self._xml_rpc_port

    @property
    def json_rpc_port(self) -> int:
        """Get JSON-RPC server port."""
        return self._json_rpc_port

    @property
    def host(self) -> str:
        """Get server host address."""
        return self._host

    async def start(self) -> None:
        """Start all servers."""
        with self._lock:
            if self._running:
                LOG.warning("VirtualCCU already running")
                return

            LOG.info("Starting VirtualCCU in %s mode", self._mode.name)

            # Set up default state if requested
            if self._setup_defaults:
                setup_default_state(self._state_manager)

            # Start XML-RPC server (runs in thread)
            # In CCU/OpenCCU mode, return real CCU version string
            # In Homegear mode, return pydevccu version (default)
            ccu_version = "3.87.1.20250130" if self._mode in (BackendMode.CCU, BackendMode.OPENCCU) else None
            self._xml_rpc_server = XmlRpcServer(
                addr=(self._host, self._xml_rpc_port),
                devices=self._devices,
                persistence=self._persistence,
                version=ccu_version,
            )
            self._xml_rpc_server.start()

            # Create ReGa engine
            self._rega_engine = RegaEngine(
                state_manager=self._state_manager,
                rpc_functions=self._xml_rpc_server._rpcfunctions,
            )

            # Start JSON-RPC server (for CCU/OpenCCU modes)
            if self._mode in (BackendMode.CCU, BackendMode.OPENCCU):
                self._handlers = JsonRpcHandlers(
                    state_manager=self._state_manager,
                    session_manager=self._session_manager,
                    rega_engine=self._rega_engine,
                    rpc_functions=self._xml_rpc_server._rpcfunctions,
                )
                self._json_rpc_server = JsonRpcServer(
                    handlers=self._handlers,
                    session_manager=self._session_manager,
                    host=self._host,
                    port=self._json_rpc_port,
                )
                await self._json_rpc_server.start()

            self._running = True
            LOG.info(
                "VirtualCCU started - XML-RPC: %s:%d, JSON-RPC: %s:%d",
                self._host,
                self._xml_rpc_port,
                self._host,
                self._json_rpc_port if self._json_rpc_server else 0,
            )

    async def stop(self) -> None:
        """Stop all servers."""
        with self._lock:
            if not self._running:
                return

            LOG.info("Stopping VirtualCCU")

            # Stop JSON-RPC server
            if self._json_rpc_server:
                await self._json_rpc_server.stop()
                self._json_rpc_server = None

            # Stop XML-RPC server
            if self._xml_rpc_server:
                # Clear remotes before stopping to prevent callback errors
                self._xml_rpc_server._rpcfunctions.remotes.clear()
                self._xml_rpc_server.stop()
                self._xml_rpc_server = None

            self._handlers = None
            self._rega_engine = None
            self._running = False

            LOG.info("VirtualCCU stopped")

    async def __aenter__(self) -> VirtualCCU:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()

    # ─────────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────────

    def setup_default_state(self) -> None:
        """Set up default programs, sysvars, rooms for testing."""
        setup_default_state(self._state_manager)

    def get_xml_rpc_functions(self) -> Any:
        """Get XML-RPC functions object for direct access."""
        if self._xml_rpc_server:
            return self._xml_rpc_server._rpcfunctions
        return None

    def list_devices(self) -> list[dict[str, Any]]:
        """List all available devices."""
        if self._xml_rpc_server:
            return self._xml_rpc_server.listDevices()
        return []

    def supported_devices(self) -> dict[str, str]:
        """Get dict of supported device types to addresses."""
        if self._xml_rpc_server:
            return self._xml_rpc_server.supportedDevices()
        return {}

    def add_devices(self, devices: list[str] | None = None) -> None:
        """Add devices dynamically."""
        if self._xml_rpc_server:
            self._xml_rpc_server.addDevices(devices)

    def remove_devices(self, devices: list[str] | None = None) -> None:
        """Remove devices dynamically."""
        if self._xml_rpc_server:
            self._xml_rpc_server.removeDevices(devices)

    def set_value(
        self,
        address: str,
        value_key: str,
        value: Any,
        *,
        force: bool = False,
    ) -> None:
        """Set a device parameter value."""
        if self._xml_rpc_server:
            self._xml_rpc_server.setValue(address, value_key, value, force)

    def get_value(self, address: str, value_key: str) -> Any:
        """Get a device parameter value."""
        if self._xml_rpc_server:
            return self._xml_rpc_server.getValue(address, value_key)
        return None

    def get_paramset(self, address: str, paramset_key: str = "VALUES") -> dict[str, Any]:
        """Get device paramset."""
        if self._xml_rpc_server:
            return self._xml_rpc_server.getParamset(address, paramset_key)
        return {}

    def put_paramset(
        self,
        address: str,
        paramset_key: str,
        paramset: dict[str, Any],
        *,
        force: bool = False,
    ) -> None:
        """Set device paramset."""
        if self._xml_rpc_server:
            self._xml_rpc_server.putParamset(address, paramset_key, paramset, force)

    # ─────────────────────────────────────────────────────────────────
    # State Shortcuts
    # ─────────────────────────────────────────────────────────────────

    def add_program(
        self,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> None:
        """Add a program."""
        self._state_manager.add_program(
            name=name,
            description=description,
            active=active,
        )

    def add_system_variable(
        self,
        name: str,
        var_type: str,
        value: Any,
        **kwargs: Any,
    ) -> None:
        """Add a system variable."""
        self._state_manager.add_system_variable(
            name=name,
            var_type=var_type,
            value=value,
            **kwargs,
        )

    def add_room(self, name: str, description: str = "") -> None:
        """Add a room."""
        self._state_manager.add_room(name=name, description=description)

    def add_function(self, name: str, description: str = "") -> None:
        """Add a function (Gewerk)."""
        self._state_manager.add_function(name=name, description=description)
