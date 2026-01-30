"""
JSON-RPC 2.0 server for pydevccu.

Provides an aiohttp-based server implementing the CCU/OpenCCU
JSON-RPC API at /api/homematic.cgi.
"""

from __future__ import annotations

import ast
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohttp import web

from pydevccu.json_rpc.errors import (
    InternalError,
    InvalidRequest,
    JsonRpcException,
    MethodNotFound,
    ParseError,
    SessionExpired,
)

if TYPE_CHECKING:
    from pydevccu.json_rpc.handlers import JsonRpcHandlers
    from pydevccu.session import SessionManager

LOG = logging.getLogger(__name__)

# Type alias for handler functions
HandlerFunc = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class JsonRpcRequest:
    """Parsed JSON-RPC 2.0 request."""

    jsonrpc: str
    method: str
    params: dict[str, Any] | list[Any] | None
    id: str | int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JsonRpcRequest:
        """Parse request from dictionary."""
        if not isinstance(data, dict):
            raise InvalidRequest("Request must be an object")

        jsonrpc = data.get("jsonrpc", "")
        # Accept both JSON-RPC 1.1 (CCU/aiohomematic) and 2.0
        if jsonrpc not in ("1.1", "2.0"):
            raise InvalidRequest("Invalid JSON-RPC version")

        method = data.get("method")
        if not isinstance(method, str):
            raise InvalidRequest("Method must be a string")

        params = data.get("params")
        if params is not None and not isinstance(params, (dict, list)):
            raise InvalidRequest("Params must be an object or array")

        return cls(
            jsonrpc=jsonrpc,
            method=method,
            params=params,
            id=data.get("id"),
        )


class JsonRpcServer:
    """
    aiohttp-based JSON-RPC 2.0 server simulating CCU/OpenCCU API.

    Implements the /api/homematic.cgi endpoint with full
    CCU-compatible JSON-RPC 2.0 protocol.
    """

    # Methods that don't require authentication
    PUBLIC_METHODS: Final = frozenset(
        {
            "Session.login",
            "CCU.getAuthEnabled",
            "CCU.getHttpsRedirectEnabled",
            "system.listMethods",
        }
    )

    def __init__(
        self,
        *,
        handlers: JsonRpcHandlers,
        session_manager: SessionManager,
        host: str = "127.0.0.1",
        port: int = 80,
    ) -> None:
        self._handlers: Final = handlers
        self._session_manager: Final = session_manager
        self._host: Final = host
        self._port: Final = port

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

        # Build method registry
        self._methods: dict[str, HandlerFunc] = {}

    async def start(self) -> None:
        """Start the JSON-RPC server."""
        if self._runner is not None:
            return

        # Build method registry from handlers
        self._methods = self._handlers.get_methods()

        self._app = web.Application()
        self._app.router.add_post("/api/homematic.cgi", self._handle_jsonrpc)
        self._app.router.add_get("/api/homematic.cgi", self._handle_jsonrpc_get)

        # Add HTTP endpoints that handlers provide
        for path, handler in self._handlers.get_http_routes():
            if handler[0] == "GET":
                self._app.router.add_get(path, handler[1])
            elif handler[0] == "POST":
                self._app.router.add_post(path, handler[1])

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()

        LOG.info("JSON-RPC server started at http://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the JSON-RPC server."""
        if self._runner is None:
            return

        await self._runner.cleanup()
        self._runner = None
        self._site = None
        self._app = None

        LOG.info("JSON-RPC server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._runner is not None

    async def _handle_jsonrpc_get(self, request: web.Request) -> web.Response:
        """Handle GET request (not supported, return method hint)."""
        return web.json_response(
            {
                "error": "Use POST to call JSON-RPC methods",
                "endpoint": "/api/homematic.cgi",
            },
            status=405,
        )

    async def _handle_jsonrpc(self, request: web.Request) -> web.Response:
        """Handle JSON-RPC POST request."""
        try:
            # Parse JSON body
            try:
                data = await request.json()
            except Exception as ex:
                raise ParseError(f"Invalid JSON: {ex}") from ex

            # Handle batch requests
            if isinstance(data, list):
                if not data:
                    raise InvalidRequest("Empty batch request")
                responses = []
                for item in data:
                    response = await self._process_single_request(item)
                    if response is not None:
                        responses.append(response)
                if not responses:
                    return web.Response(status=204)
                return web.json_response(responses)

            # Handle single request
            response = await self._process_single_request(data)
            if response is None:
                # Notification - no response
                return web.Response(status=204)
            return web.json_response(response)

        except JsonRpcException as ex:
            return web.json_response(self._error_response(None, ex))
        except Exception as ex:
            LOG.exception("Unexpected error in JSON-RPC handler")
            return web.json_response(self._error_response(None, InternalError(str(ex))))

    async def _process_single_request(self, data: Any) -> dict[str, Any] | None:
        """Process a single JSON-RPC request."""
        rpc_request: JsonRpcRequest | None = None

        try:
            # Parse request
            rpc_request = JsonRpcRequest.from_dict(data)

            # Check authentication for protected methods
            if self._requires_auth(rpc_request.method):
                session_id = self._extract_session_id(data)
                if not self._session_manager.validate(session_id):
                    raise SessionExpired

            # Find handler
            handler = self._methods.get(rpc_request.method)
            if handler is None:
                raise MethodNotFound(rpc_request.method)

            # Prepare params
            params = rpc_request.params
            if params is None:
                params = {}
            elif isinstance(params, list):
                # Convert positional params to dict if possible
                # This is a simplified approach - real impl would inspect handler signature
                params = {"args": params}

            # Call handler
            result = await handler(params)

            # Check if notification (no id)
            if rpc_request.id is None:
                return None

            return self._success_response(rpc_request.id, result)

        except JsonRpcException as ex:
            request_id = rpc_request.id if rpc_request else None
            return self._error_response(request_id, ex)
        except Exception as ex:
            LOG.exception("Handler error for method: %s", rpc_request.method if rpc_request else "unknown")
            request_id = rpc_request.id if rpc_request else None
            return self._error_response(request_id, InternalError(str(ex)))

    def _requires_auth(self, method: str) -> bool:
        """Check if method requires authentication."""
        if not self._session_manager.auth_enabled:
            return False
        return method not in self.PUBLIC_METHODS

    def _extract_session_id(self, data: dict[str, Any]) -> str | None:
        """Extract session ID from request."""
        # CCU sends session ID in _session_id_ field
        session_id = data.get("_session_id_")

        # Also check params for session_id
        if not session_id:
            params = data.get("params", {})
            if isinstance(params, dict):
                session_id = params.get("_session_id_")

        # Handle nested dict format (aiohomematic sends {"_session_id_": "xxx"})
        if isinstance(session_id, dict):
            session_id = session_id.get("_session_id_")

        # Handle stringified dict format (aiohomematic sends "{'_session_id_': 'xxx'}")
        if isinstance(session_id, str) and session_id.startswith("{"):
            try:
                parsed = ast.literal_eval(session_id)
                if isinstance(parsed, dict):
                    session_id = parsed.get("_session_id_")
            except (ValueError, SyntaxError):
                pass

        return session_id if isinstance(session_id, str) else None

    @staticmethod
    def _success_response(
        request_id: str | int | None,
        result: Any,
    ) -> dict[str, Any]:
        """Build success response."""
        # Use JSON-RPC 1.1 to match CCU behavior (aiohomematic expects this)
        # JSON-RPC 1.1 requires both result and error in response
        return {
            "jsonrpc": "1.1",
            "result": result,
            "error": None,
            "id": request_id,
        }

    @staticmethod
    def _error_response(
        request_id: str | int | None,
        error: JsonRpcException,
    ) -> dict[str, Any]:
        """Build error response."""
        # Use JSON-RPC 1.1 to match CCU behavior (aiohomematic expects this)
        # JSON-RPC 1.1 requires both result and error in response
        return {
            "jsonrpc": "1.1",
            "result": None,
            "error": error.to_dict(),
            "id": request_id,
        }
