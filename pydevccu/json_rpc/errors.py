"""
JSON-RPC error codes and exceptions for pydevccu.

Implements standard JSON-RPC 2.0 error codes plus CCU-specific errors.
"""

from __future__ import annotations

from typing import Any, Final


class JsonRpcError:
    """JSON-RPC 2.0 error codes."""

    # Standard JSON-RPC 2.0 errors
    PARSE_ERROR: Final = -32700
    INVALID_REQUEST: Final = -32600
    METHOD_NOT_FOUND: Final = -32601
    INVALID_PARAMS: Final = -32602
    INTERNAL_ERROR: Final = -32603

    # Server errors (-32000 to -32099)
    SERVER_ERROR: Final = -32000

    # CCU-specific errors
    AUTH_REQUIRED: Final = -32001
    SESSION_EXPIRED: Final = -32002
    PERMISSION_DENIED: Final = -32003
    OBJECT_NOT_FOUND: Final = -32004
    INVALID_OPERATION: Final = -32005


class JsonRpcException(Exception):
    """
    JSON-RPC exception with error code and message.

    Can be raised in handlers to return a specific error response.
    """

    def __init__(
        self,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC error object."""
        error: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            error["data"] = self.data
        return error


# Pre-built exceptions for common errors
class ParseError(JsonRpcException):
    """JSON parse error."""

    def __init__(self, message: str = "Parse error") -> None:
        super().__init__(JsonRpcError.PARSE_ERROR, message)


class InvalidRequest(JsonRpcException):
    """Invalid JSON-RPC request."""

    def __init__(self, message: str = "Invalid request") -> None:
        super().__init__(JsonRpcError.INVALID_REQUEST, message)


class MethodNotFound(JsonRpcException):
    """Method not found."""

    def __init__(self, method: str) -> None:
        super().__init__(
            JsonRpcError.METHOD_NOT_FOUND,
            f"Method not found: {method}",
        )


class InvalidParams(JsonRpcException):
    """Invalid method parameters."""

    def __init__(self, message: str = "Invalid params") -> None:
        super().__init__(JsonRpcError.INVALID_PARAMS, message)


class InternalError(JsonRpcException):
    """Internal server error."""

    def __init__(self, message: str = "Internal error") -> None:
        super().__init__(JsonRpcError.INTERNAL_ERROR, message)


class AuthRequired(JsonRpcException):
    """Authentication required."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(JsonRpcError.AUTH_REQUIRED, message)


class SessionExpired(JsonRpcException):
    """Session expired or invalid."""

    def __init__(self, message: str = "Session expired or invalid") -> None:
        super().__init__(JsonRpcError.SESSION_EXPIRED, message)


class PermissionDenied(JsonRpcException):
    """Permission denied."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(JsonRpcError.PERMISSION_DENIED, message)


class ObjectNotFound(JsonRpcException):
    """Object not found."""

    def __init__(self, obj_type: str, identifier: str | int) -> None:
        super().__init__(
            JsonRpcError.OBJECT_NOT_FOUND,
            f"{obj_type} not found: {identifier}",
        )


class InvalidOperation(JsonRpcException):
    """Invalid operation."""

    def __init__(self, message: str = "Invalid operation") -> None:
        super().__init__(JsonRpcError.INVALID_OPERATION, message)
