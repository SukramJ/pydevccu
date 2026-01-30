"""
pydevccu - Virtual HomeMatic CCU XML-RPC and JSON-RPC backend.

This package provides a complete CCU/OpenCCU simulation for testing
HomeMatic integrations without real hardware.

Basic usage (XML-RPC only, Homegear mode)::

    from pydevccu import Server
    server = Server(addr=("127.0.0.1", 2010))
    server.start()

Full VirtualCCU with JSON-RPC (OpenCCU mode)::

    from pydevccu import VirtualCCU, BackendMode

    async with VirtualCCU(mode=BackendMode.OPENCCU) as ccu:
        # ... run tests ...
"""

from __future__ import annotations

from pydevccu.ccu import ServerThread as Server
from pydevccu.const import BackendMode
from pydevccu.server import VirtualCCU
from pydevccu.session import SessionManager
from pydevccu.state import StateManager

__all__ = [
    "BackendMode",
    "Server",
    "SessionManager",
    "StateManager",
    "VirtualCCU",
]
