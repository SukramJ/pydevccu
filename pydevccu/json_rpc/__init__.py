"""
JSON-RPC server package for pydevccu.

Provides an aiohttp-based JSON-RPC 2.0 server implementing the
CCU/OpenCCU API endpoints.
"""

from __future__ import annotations

from pydevccu.json_rpc.errors import JsonRpcError, JsonRpcException
from pydevccu.json_rpc.server import JsonRpcServer

__all__ = [
    "JsonRpcError",
    "JsonRpcException",
    "JsonRpcServer",
]
