"""
Pytest fixtures for pydevccu tests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from pydevccu import BackendMode, SessionManager, StateManager, VirtualCCU
from pydevccu.json_rpc.handlers import JsonRpcHandlers
from pydevccu.rega import RegaEngine
from pydevccu.state.defaults import setup_default_state


@pytest.fixture
def state_manager() -> StateManager:
    """Create a fresh StateManager for testing."""
    return StateManager(mode=BackendMode.OPENCCU)


@pytest.fixture
def state_manager_with_defaults() -> StateManager:
    """Create a StateManager with default test data."""
    state = StateManager(mode=BackendMode.OPENCCU)
    setup_default_state(state)
    return state


@pytest.fixture
def session_manager() -> SessionManager:
    """Create a SessionManager for testing."""
    return SessionManager(
        username="Admin",
        password="test123",
        auth_enabled=True,
    )


@pytest.fixture
def session_manager_no_auth() -> SessionManager:
    """Create a SessionManager with auth disabled."""
    return SessionManager(
        username="Admin",
        password="test123",
        auth_enabled=False,
    )


@pytest.fixture
def rega_engine(state_manager: StateManager) -> RegaEngine:
    """Create a ReGa engine for testing."""
    return RegaEngine(state_manager=state_manager)


@pytest.fixture
def rega_engine_with_defaults(
    state_manager_with_defaults: StateManager,
) -> RegaEngine:
    """Create a ReGa engine with default state."""
    return RegaEngine(state_manager=state_manager_with_defaults)


@pytest.fixture
def json_rpc_handlers(
    state_manager: StateManager,
    session_manager: SessionManager,
    rega_engine: RegaEngine,
) -> JsonRpcHandlers:
    """Create JSON-RPC handlers for testing."""
    return JsonRpcHandlers(
        state_manager=state_manager,
        session_manager=session_manager,
        rega_engine=rega_engine,
    )


@pytest.fixture
async def virtual_ccu_homegear() -> AsyncGenerator[VirtualCCU]:
    """Create a VirtualCCU in Homegear mode."""
    ccu = VirtualCCU(
        mode=BackendMode.HOMEGEAR,
        host="127.0.0.1",
        xml_rpc_port=12001,
        json_rpc_port=18081,
        auth_enabled=False,
        devices=["HmIP-SWSD"],  # Single device for fast startup
    )
    await ccu.start()
    yield ccu
    await ccu.stop()


@pytest.fixture
async def virtual_ccu_openccu() -> AsyncGenerator[VirtualCCU]:
    """Create a VirtualCCU in OpenCCU mode."""
    ccu = VirtualCCU(
        mode=BackendMode.OPENCCU,
        host="127.0.0.1",
        xml_rpc_port=12010,
        json_rpc_port=18080,
        username="Admin",
        password="test123",
        auth_enabled=True,
        devices=["HmIP-SWSD"],  # Single device for fast startup
        setup_defaults=True,
    )
    await ccu.start()
    yield ccu
    await ccu.stop()


@pytest.fixture
async def virtual_ccu_ccu() -> AsyncGenerator[VirtualCCU]:
    """Create a VirtualCCU in CCU mode."""
    ccu = VirtualCCU(
        mode=BackendMode.CCU,
        host="127.0.0.1",
        xml_rpc_port=12020,
        json_rpc_port=18082,
        username="Admin",
        password="test123",
        auth_enabled=True,
        devices=["HmIP-SWSD"],
        setup_defaults=True,
    )
    await ccu.start()
    yield ccu
    await ccu.stop()
