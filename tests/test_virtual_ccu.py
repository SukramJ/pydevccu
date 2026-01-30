"""Tests for VirtualCCU orchestrator."""

from __future__ import annotations

import pytest

from pydevccu import BackendMode, VirtualCCU


class TestVirtualCCUInit:
    """Test VirtualCCU initialization."""

    def test_default_mode(self) -> None:
        """Test default mode is OPENCCU."""
        ccu = VirtualCCU()
        assert ccu.mode == BackendMode.OPENCCU

    def test_custom_mode(self) -> None:
        """Test custom mode."""
        ccu = VirtualCCU(mode=BackendMode.HOMEGEAR)
        assert ccu.mode == BackendMode.HOMEGEAR

    def test_ports(self) -> None:
        """Test port configuration."""
        ccu = VirtualCCU(
            xml_rpc_port=12345,
            json_rpc_port=54321,
        )
        assert ccu.xml_rpc_port == 12345
        assert ccu.json_rpc_port == 54321

    def test_host(self) -> None:
        """Test host configuration."""
        ccu = VirtualCCU(host="0.0.0.0")
        assert ccu.host == "0.0.0.0"


class TestVirtualCCUStartStop:
    """Test VirtualCCU start/stop."""

    @pytest.mark.asyncio
    async def test_start_stop_homegear(self, virtual_ccu_homegear: VirtualCCU) -> None:
        """Test starting VirtualCCU in Homegear mode."""
        assert virtual_ccu_homegear.is_running is True
        assert virtual_ccu_homegear.mode == BackendMode.HOMEGEAR

    @pytest.mark.asyncio
    async def test_start_stop_openccu(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test starting VirtualCCU in OpenCCU mode."""
        assert virtual_ccu_openccu.is_running is True
        assert virtual_ccu_openccu.mode == BackendMode.OPENCCU

    @pytest.mark.asyncio
    async def test_start_stop_ccu(self, virtual_ccu_ccu: VirtualCCU) -> None:
        """Test starting VirtualCCU in CCU mode."""
        assert virtual_ccu_ccu.is_running is True
        assert virtual_ccu_ccu.mode == BackendMode.CCU

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        async with VirtualCCU(
            mode=BackendMode.HOMEGEAR,
            xml_rpc_port=12099,
            devices=["HmIP-SWSD"],
        ) as ccu:
            assert ccu.is_running is True

        assert ccu.is_running is False


class TestVirtualCCUState:
    """Test VirtualCCU state access."""

    @pytest.mark.asyncio
    async def test_state_manager_access(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test accessing state manager."""
        state = virtual_ccu_openccu.state_manager
        assert state is not None

        # Default state should be set up
        programs = state.get_programs()
        assert len(programs) >= 1

    @pytest.mark.asyncio
    async def test_session_manager_access(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test accessing session manager."""
        session = virtual_ccu_openccu.session_manager
        assert session is not None
        assert session.auth_enabled is True


class TestVirtualCCUConvenienceMethods:
    """Test VirtualCCU convenience methods."""

    @pytest.mark.asyncio
    async def test_add_program(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test adding a program."""
        virtual_ccu_openccu.add_program(
            name="Convenience Test",
            description="Test program",
        )

        programs = virtual_ccu_openccu.state_manager.get_programs()
        names = [p.name for p in programs]
        assert "Convenience Test" in names

    @pytest.mark.asyncio
    async def test_add_system_variable(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test adding a system variable."""
        virtual_ccu_openccu.add_system_variable(
            name="ConvVar",
            var_type="BOOL",
            value=True,
        )

        sv = virtual_ccu_openccu.state_manager.get_system_variable("ConvVar")
        assert sv is not None
        assert sv.value is True

    @pytest.mark.asyncio
    async def test_add_room(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test adding a room."""
        virtual_ccu_openccu.add_room(
            name="New Room",
            description="A new room",
        )

        rooms = virtual_ccu_openccu.state_manager.get_rooms()
        names = [r.name for r in rooms]
        assert "New Room" in names

    @pytest.mark.asyncio
    async def test_add_function(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test adding a function."""
        virtual_ccu_openccu.add_function(
            name="New Function",
            description="A new function",
        )

        functions = virtual_ccu_openccu.state_manager.get_functions()
        names = [f.name for f in functions]
        assert "New Function" in names


class TestVirtualCCUDevices:
    """Test VirtualCCU device operations."""

    @pytest.mark.asyncio
    async def test_list_devices(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test listing devices."""
        devices = virtual_ccu_openccu.list_devices()
        assert isinstance(devices, list)
        # Should have at least one device (HmIP-SWSD)
        assert len(devices) >= 1

    @pytest.mark.asyncio
    async def test_supported_devices(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test getting supported devices."""
        supported = virtual_ccu_openccu.supported_devices()
        assert isinstance(supported, dict)
        assert "HmIP-SWSD" in supported

    @pytest.mark.asyncio
    async def test_get_xml_rpc_functions(self, virtual_ccu_openccu: VirtualCCU) -> None:
        """Test getting XML-RPC functions object."""
        rpc = virtual_ccu_openccu.get_xml_rpc_functions()
        assert rpc is not None


class TestVirtualCCUDefaults:
    """Test VirtualCCU with default state."""

    @pytest.mark.asyncio
    async def test_setup_defaults_flag(self) -> None:
        """Test setup_defaults flag."""
        ccu = VirtualCCU(
            mode=BackendMode.OPENCCU,
            xml_rpc_port=12098,
            json_rpc_port=18098,
            devices=["HmIP-SWSD"],
            setup_defaults=True,
        )

        await ccu.start()
        try:
            # Should have default programs
            programs = ccu.state_manager.get_programs()
            assert len(programs) >= 1

            # Should have default sysvars
            sysvars = ccu.state_manager.get_system_variables()
            assert len(sysvars) >= 1

            # Should have default rooms
            rooms = ccu.state_manager.get_rooms()
            assert len(rooms) >= 1

            # Should have default functions
            functions = ccu.state_manager.get_functions()
            assert len(functions) >= 1
        finally:
            await ccu.stop()

    @pytest.mark.asyncio
    async def test_setup_default_state_method(self, virtual_ccu_homegear: VirtualCCU) -> None:
        """Test setup_default_state method."""
        # Initially no programs (Homegear mode, no setup_defaults)
        programs_before = virtual_ccu_homegear.state_manager.get_programs()

        virtual_ccu_homegear.setup_default_state()

        programs_after = virtual_ccu_homegear.state_manager.get_programs()
        assert len(programs_after) > len(programs_before)
