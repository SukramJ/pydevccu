# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring
"""
Compatibility layer for free-threading support and conditional JSON backend.

This module provides:
- Detection of free-threaded Python builds
- Conditional JSON serialization (orjson for GIL builds, stdlib json for free-threaded)

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import json as _stdlib_json
import sys
import sysconfig
from typing import TYPE_CHECKING, Any, Final

# =============================================================================
# Free-Threading Detection
# =============================================================================


def is_free_threaded_build() -> bool:
    """
    Return True if Python was built with free-threading support.

    This checks the build configuration, not the runtime GIL state.
    Use this for decisions about which libraries to load.
    """
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def is_gil_enabled() -> bool:
    """
    Return True if the GIL is currently enabled at runtime.

    On standard Python builds, always returns True.
    On free-threaded builds, returns False unless GIL was re-enabled via PYTHON_GIL=1.
    """
    if hasattr(sys, "_is_gil_enabled"):
        return sys._is_gil_enabled()  # pylint: disable=protected-access
    return True  # Standard build - GIL always enabled


# Cache the build type at import time (immutable)
FREE_THREADED_BUILD: Final[bool] = is_free_threaded_build()

# =============================================================================
# Conditional JSON Backend
# =============================================================================

# Try to import orjson, but only use it if NOT in free-threaded mode
_USE_ORJSON: bool = False

if TYPE_CHECKING:
    import orjson as _orjson
else:
    _orjson: Any = None
    if not FREE_THREADED_BUILD:
        try:
            import orjson as _orjson

            _USE_ORJSON = True
        except ImportError:
            pass


class JSONDecodeError(Exception):
    """Unified JSON decode error that wraps backend-specific errors."""


def dumps(obj: Any) -> bytes:
    """
    Serialize obj to JSON bytes.

    Args:
        obj: Object to serialize

    Returns:
        JSON as bytes (UTF-8 encoded)

    """
    if _USE_ORJSON and _orjson is not None:
        result: bytes = _orjson.dumps(obj)
        return result

    # Stdlib json fallback
    return _stdlib_json.dumps(obj, ensure_ascii=False).encode("utf-8")


def loads(data: bytes | str) -> Any:
    """
    Deserialize JSON bytes/string to Python object.

    Args:
        data: JSON data as bytes or string

    Returns:
        Deserialized Python object

    Raises:
        JSONDecodeError: If data is not valid JSON

    """
    if _USE_ORJSON and _orjson is not None:
        try:
            return _orjson.loads(data)
        except _orjson.JSONDecodeError as exc:
            raise JSONDecodeError(str(exc)) from exc

    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return _stdlib_json.loads(data)
    except _stdlib_json.JSONDecodeError as exc:
        raise JSONDecodeError(str(exc)) from exc


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "FREE_THREADED_BUILD",
    "JSONDecodeError",
    "dumps",
    "is_free_threaded_build",
    "is_gil_enabled",
    "loads",
]
