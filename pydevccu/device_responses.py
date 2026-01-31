"""
Device-specific response mappings for pydevccu.

Defines how devices respond to parameter changes. When a parameter is set,
the device may respond with different or additional parameters based on
the device type and the parameter that was changed.

Example: Setting LEVEL on a dimmer results in LEVEL event being sent back
         (confirming the actual level the device achieved).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParameterResponse:
    """Defines a response for a parameter change."""

    # Parameter that triggers this response
    trigger_param: str

    # Parameter(s) to send in response (can be same as trigger or different)
    response_params: list[str] = field(default_factory=list)

    # Optional value transformer: (trigger_value, current_values) -> response_value
    # If None, uses the trigger value directly
    value_transformer: Callable[[Any, dict[str, Any]], dict[str, Any]] | None = None

    # Delay in seconds before sending response (0 = immediate)
    delay: float = 0.0

    # Whether to also echo back the original parameter
    echo_trigger: bool = True


def _identity_response(trigger_param: str, trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Default response: echo the trigger parameter with its value."""
    return {trigger_param: trigger_value}


def _level_to_level_real(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Transform LEVEL to LEVEL response (dimmer confirms level)."""
    return {"LEVEL": trigger_value}


def _state_with_working(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Switch responds with STATE and clears WORKING."""
    return {"STATE": trigger_value, "WORKING": False}


def _level_with_activity(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Dimmer responds with LEVEL and activity state."""
    return {
        "LEVEL": trigger_value,
        "ACTIVITY_STATE": 0 if trigger_value == 0 else 2,  # 0=unknown, 1=up, 2=down, 3=stable
    }


def _blind_level_response(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Blind responds with LEVEL and LEVEL_2 (slat position)."""
    result = {"LEVEL": trigger_value}
    # Keep slat position if set, otherwise default
    if "LEVEL_2" in current_values:
        result["LEVEL_2"] = current_values["LEVEL_2"]
    return result


def _thermostat_setpoint_response(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Thermostat responds with set point confirmation."""
    return {
        "SET_POINT_TEMPERATURE": trigger_value,
        "CONTROL_MODE": current_values.get("CONTROL_MODE", 1),  # 0=auto, 1=manual
    }


def _window_handle_response(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Window handle responds with state."""
    return {"STATE": trigger_value}


def _smoke_detector_response(trigger_value: Any, current_values: dict[str, Any]) -> dict[str, Any]:
    """Smoke detector test command response."""
    return {
        "SMOKE_DETECTOR_ALARM_STATUS": 0,  # 0=idle
        "SMOKE_DETECTOR_TEST_RESULT": 0,  # 0=none, 1=ok, 2=failed
    }


# Device type to response mappings
# Key: Device type (or device type prefix)
# Value: Dict of parameter -> ParameterResponse
DEVICE_RESPONSE_MAPPINGS: dict[str, dict[str, ParameterResponse]] = {
    # ═══════════════════════════════════════════════════════════════════
    # Switches
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-PS": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_state_with_working,
        ),
    },
    "HmIP-PSM": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_state_with_working,
        ),
    },
    "HmIP-BSM": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_state_with_working,
        ),
    },
    "HmIP-FSM": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_state_with_working,
        ),
    },
    "HmIP-PCBS": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_state_with_working,
        ),
    },
    "HM-LC-Sw": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_state_with_working,
        ),
    },
    # ═══════════════════════════════════════════════════════════════════
    # Dimmers
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-BDT": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_level_with_activity,
        ),
    },
    "HmIP-PDT": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_level_with_activity,
        ),
    },
    "HmIP-FDT": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_level_with_activity,
        ),
    },
    "HM-LC-Dim": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_level_to_level_real,
        ),
    },
    # ═══════════════════════════════════════════════════════════════════
    # Blinds / Shutters
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-BROLL": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_blind_level_response,
        ),
        "LEVEL_2": ParameterResponse(
            trigger_param="LEVEL_2",
            echo_trigger=True,
        ),
    },
    "HmIP-FROLL": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_blind_level_response,
        ),
    },
    "HmIP-BBL": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_blind_level_response,
        ),
        "LEVEL_2": ParameterResponse(
            trigger_param="LEVEL_2",
            echo_trigger=True,
        ),
    },
    "HmIP-FBL": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_blind_level_response,
        ),
        "LEVEL_2": ParameterResponse(
            trigger_param="LEVEL_2",
            echo_trigger=True,
        ),
    },
    "HM-LC-Bl1": {
        "LEVEL": ParameterResponse(
            trigger_param="LEVEL",
            value_transformer=_level_to_level_real,
        ),
    },
    # ═══════════════════════════════════════════════════════════════════
    # Thermostats
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-eTRV": {
        "SET_POINT_TEMPERATURE": ParameterResponse(
            trigger_param="SET_POINT_TEMPERATURE",
            value_transformer=_thermostat_setpoint_response,
        ),
        "CONTROL_MODE": ParameterResponse(
            trigger_param="CONTROL_MODE",
            echo_trigger=True,
        ),
    },
    "HmIP-HEATING": {
        "SET_POINT_TEMPERATURE": ParameterResponse(
            trigger_param="SET_POINT_TEMPERATURE",
            value_transformer=_thermostat_setpoint_response,
        ),
    },
    "HmIP-WTH": {
        "SET_POINT_TEMPERATURE": ParameterResponse(
            trigger_param="SET_POINT_TEMPERATURE",
            value_transformer=_thermostat_setpoint_response,
        ),
    },
    "HmIP-BWTH": {
        "SET_POINT_TEMPERATURE": ParameterResponse(
            trigger_param="SET_POINT_TEMPERATURE",
            value_transformer=_thermostat_setpoint_response,
        ),
    },
    "HmIP-STH": {
        "SET_POINT_TEMPERATURE": ParameterResponse(
            trigger_param="SET_POINT_TEMPERATURE",
            value_transformer=_thermostat_setpoint_response,
        ),
    },
    "HM-CC-RT-DN": {
        "SET_TEMPERATURE": ParameterResponse(
            trigger_param="SET_TEMPERATURE",
            echo_trigger=True,
        ),
        "CONTROL_MODE": ParameterResponse(
            trigger_param="CONTROL_MODE",
            echo_trigger=True,
        ),
    },
    # ═══════════════════════════════════════════════════════════════════
    # Sensors (read-only, but some have test commands)
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-SWSD": {
        "SMOKE_DETECTOR_COMMAND": ParameterResponse(
            trigger_param="SMOKE_DETECTOR_COMMAND",
            value_transformer=_smoke_detector_response,
        ),
    },
    # ═══════════════════════════════════════════════════════════════════
    # Window/Door contacts
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-SWDO": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_window_handle_response,
        ),
    },
    "HmIP-SRH": {
        "STATE": ParameterResponse(
            trigger_param="STATE",
            value_transformer=_window_handle_response,
        ),
    },
    # ═══════════════════════════════════════════════════════════════════
    # Lock actuators
    # ═══════════════════════════════════════════════════════════════════
    "HmIP-DLD": {
        "LOCK_TARGET_LEVEL": ParameterResponse(
            trigger_param="LOCK_TARGET_LEVEL",
            response_params=["LOCK_STATE"],
            value_transformer=lambda v, c: {"LOCK_STATE": 1 if v == 0 else 2},  # 1=locked, 2=unlocked
        ),
    },
}


def get_response_mapping(device_type: str, param: str) -> ParameterResponse | None:
    """
    Get the response mapping for a device type and parameter.

    Supports both exact matches and prefix matches (e.g., "HmIP-PS" matches "HmIP-PSM").

    Args:
        device_type: The device type (e.g., "HmIP-PSM")
        param: The parameter name (e.g., "STATE")

    Returns:
        ParameterResponse if found, None otherwise

    """
    # Try exact match first
    if device_type in DEVICE_RESPONSE_MAPPINGS:
        mappings = DEVICE_RESPONSE_MAPPINGS[device_type]
        if param in mappings:
            return mappings[param]

    # Try prefix match (sorted by length descending for longest match first)
    for prefix in sorted(DEVICE_RESPONSE_MAPPINGS.keys(), key=len, reverse=True):
        if device_type.startswith(prefix):
            mappings = DEVICE_RESPONSE_MAPPINGS[prefix]
            if param in mappings:
                return mappings[param]

    return None


def compute_response_events(
    device_type: str,
    param: str,
    value: Any,
    current_values: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute the response events for a parameter change.

    Args:
        device_type: The device type (e.g., "HmIP-PSM")
        param: The parameter that was set
        value: The value that was set
        current_values: Current paramset values for context

    Returns:
        Dictionary of parameter -> value for events to fire

    """
    response = get_response_mapping(device_type, param)

    if response is None:
        # Default: echo the parameter that was set
        return {param: value}

    events = response.value_transformer(value, current_values) if response.value_transformer else {param: value}

    # Add echo of trigger if requested and not already in events
    if response.echo_trigger and param not in events:
        events[param] = value

    return events
