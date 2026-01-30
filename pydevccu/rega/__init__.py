"""
ReGa script engine package for pydevccu.

Provides a pattern-matching based ReGa script engine that handles
common scripts used by aiohomematic without requiring a full
language interpreter.
"""

from __future__ import annotations

from pydevccu.rega.engine import RegaEngine, RegaScriptResult

__all__ = [
    "RegaEngine",
    "RegaScriptResult",
]
