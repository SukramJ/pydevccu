"""
Default state factory for pydevccu testing.

Provides pre-configured programs, system variables, rooms, and
functions for quick test setup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydevccu.state.manager import StateManager


def setup_default_programs(state: StateManager) -> None:
    """Add default programs for testing."""
    state.add_program(
        name="Heating Morning",
        description="Start heating at 6:00",
        active=True,
    )
    state.add_program(
        name="Lights Off",
        description="Turn off all lights at 23:00",
        active=True,
    )
    state.add_program(
        name="Vacation Mode",
        description="Simulate presence when away",
        active=False,
    )
    state.add_program(
        name="Security Alert",
        description="Triggered on intrusion detection",
        active=True,
    )


def setup_default_sysvars(state: StateManager) -> None:
    """Add default system variables for testing."""
    state.add_system_variable(
        name="Presence",
        var_type="BOOL",
        value=True,
        description="Someone is home",
    )
    state.add_system_variable(
        name="AlarmLevel",
        var_type="ENUM",
        value=0,
        description="Current alarm level",
        value_list="Off;Armed;Triggered",
        min_value=0,
        max_value=2,
    )
    state.add_system_variable(
        name="TargetTemperature",
        var_type="FLOAT",
        value=21.5,
        description="Target room temperature",
        unit="°C",
        min_value=5.0,
        max_value=30.0,
    )
    state.add_system_variable(
        name="LastMotion",
        var_type="STRING",
        value="",
        description="Last motion sensor triggered",
    )
    state.add_system_variable(
        name="EnergyToday",
        var_type="FLOAT",
        value=0.0,
        description="Energy consumed today",
        unit="kWh",
        min_value=0.0,
        max_value=1000.0,
    )


def setup_default_rooms(state: StateManager) -> None:
    """Add default rooms for testing."""
    state.add_room(
        name="Living Room",
        description="Main living area",
    )
    state.add_room(
        name="Bedroom",
        description="Master bedroom",
    )
    state.add_room(
        name="Kitchen",
        description="Kitchen area",
    )
    state.add_room(
        name="Bathroom",
        description="Main bathroom",
    )
    state.add_room(
        name="Office",
        description="Home office",
    )


def setup_default_functions(state: StateManager) -> None:
    """Add default functions (Gewerke) for testing."""
    state.add_function(
        name="Lights",
        description="All lighting devices",
    )
    state.add_function(
        name="Heating",
        description="All heating devices",
    )
    state.add_function(
        name="Security",
        description="Security devices",
    )
    state.add_function(
        name="Shutters",
        description="Shutter and blind controls",
    )
    state.add_function(
        name="Weather",
        description="Weather sensors",
    )


def setup_default_state(state: StateManager) -> None:
    """
    Set up all default state for testing.

    This includes programs, system variables, rooms, and functions.
    Call this after creating a StateManager to populate it with
    realistic test data.
    """
    setup_default_programs(state)
    setup_default_sysvars(state)
    setup_default_rooms(state)
    setup_default_functions(state)
