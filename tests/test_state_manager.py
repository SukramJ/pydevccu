"""Tests for StateManager."""

from __future__ import annotations

from pydevccu import BackendMode, StateManager


class TestStateManagerInit:
    """Test StateManager initialization."""

    def test_default_mode(self) -> None:
        """Test default mode is OPENCCU."""
        state = StateManager()
        assert state.mode == BackendMode.OPENCCU

    def test_custom_mode(self) -> None:
        """Test custom mode."""
        state = StateManager(mode=BackendMode.CCU)
        assert state.mode == BackendMode.CCU

    def test_custom_serial(self) -> None:
        """Test custom serial number (last 10 chars)."""
        state = StateManager(serial="MYCCU123456")
        assert state.get_serial() == "YCCU123456"  # Last 10 chars

    def test_serial_truncation(self) -> None:
        """Test serial is truncated to 10 chars."""
        state = StateManager(serial="VERYLONGSERIAL123456")
        assert state.get_serial() == "RIAL123456"  # Last 10 chars


class TestBackendInfo:
    """Test backend info operations."""

    def test_get_backend_info(self, state_manager: StateManager) -> None:
        """Test getting backend info."""
        info = state_manager.get_backend_info()
        assert info.product == "OpenCCU"
        assert info.version is not None

    def test_set_backend_info(self, state_manager: StateManager) -> None:
        """Test setting backend info."""
        state_manager.set_backend_info(
            version="4.0.0",
            hostname="test-ccu",
            is_ha_addon=True,
        )
        info = state_manager.get_backend_info()
        assert info.version == "4.0.0"
        assert info.hostname == "test-ccu"
        assert info.is_ha_addon is True


class TestPrograms:
    """Test program operations."""

    def test_add_program(self, state_manager: StateManager) -> None:
        """Test adding a program."""
        prog = state_manager.add_program(
            name="Test Program",
            description="A test program",
            active=True,
        )
        assert prog.id >= 1000
        assert prog.name == "Test Program"
        assert prog.active is True

    def test_get_programs(self, state_manager: StateManager) -> None:
        """Test getting all programs."""
        state_manager.add_program(name="Prog1")
        state_manager.add_program(name="Prog2")

        programs = state_manager.get_programs()
        assert len(programs) == 2

    def test_get_program_by_id(self, state_manager: StateManager) -> None:
        """Test getting program by ID."""
        prog = state_manager.add_program(name="Test")
        result = state_manager.get_program(prog.id)
        assert result is not None
        assert result.name == "Test"

    def test_get_program_by_name(self, state_manager: StateManager) -> None:
        """Test getting program by name."""
        state_manager.add_program(name="FindMe")
        result = state_manager.get_program_by_name("FindMe")
        assert result is not None
        assert result.name == "FindMe"

    def test_execute_program(self, state_manager: StateManager) -> None:
        """Test executing a program."""
        prog = state_manager.add_program(name="Execute Test")
        assert prog.last_execute_time == 0.0

        result = state_manager.execute_program(prog.id)
        assert result is True
        assert prog.last_execute_time > 0

    def test_execute_inactive_program(self, state_manager: StateManager) -> None:
        """Test executing an inactive program fails."""
        prog = state_manager.add_program(name="Inactive", active=False)
        result = state_manager.execute_program(prog.id)
        assert result is False

    def test_set_program_active(self, state_manager: StateManager) -> None:
        """Test setting program active state."""
        prog = state_manager.add_program(name="Toggle", active=True)
        state_manager.set_program_active(prog.id, False)

        result = state_manager.get_program(prog.id)
        assert result is not None
        assert result.active is False

    def test_delete_program(self, state_manager: StateManager) -> None:
        """Test deleting a program."""
        prog = state_manager.add_program(name="Delete Me")
        result = state_manager.delete_program(prog.id)
        assert result is True
        assert state_manager.get_program(prog.id) is None


class TestSystemVariables:
    """Test system variable operations."""

    def test_add_sysvar_bool(self, state_manager: StateManager) -> None:
        """Test adding a boolean sysvar."""
        sv = state_manager.add_system_variable(
            name="TestBool",
            var_type="BOOL",
            value=True,
        )
        assert sv.name == "TestBool"
        assert sv.var_type == "BOOL"
        assert sv.value is True

    def test_add_sysvar_float(self, state_manager: StateManager) -> None:
        """Test adding a float sysvar."""
        sv = state_manager.add_system_variable(
            name="Temperature",
            var_type="FLOAT",
            value=21.5,
            unit="°C",
            min_value=5.0,
            max_value=30.0,
        )
        assert sv.value == 21.5
        assert sv.unit == "°C"

    def test_add_sysvar_enum(self, state_manager: StateManager) -> None:
        """Test adding an enum sysvar."""
        sv = state_manager.add_system_variable(
            name="AlarmLevel",
            var_type="ENUM",
            value=0,
            value_list="Off;Armed;Triggered",
        )
        assert sv.value_list == "Off;Armed;Triggered"

    def test_get_sysvars(self, state_manager: StateManager) -> None:
        """Test getting all sysvars."""
        state_manager.add_system_variable(name="Var1", var_type="BOOL", value=True)
        state_manager.add_system_variable(name="Var2", var_type="BOOL", value=False)

        sysvars = state_manager.get_system_variables()
        assert len(sysvars) == 2

    def test_get_sysvar_by_name(self, state_manager: StateManager) -> None:
        """Test getting sysvar by name."""
        state_manager.add_system_variable(name="FindMe", var_type="STRING", value="test")
        result = state_manager.get_system_variable("FindMe")
        assert result is not None
        assert result.value == "test"

    def test_set_sysvar(self, state_manager: StateManager) -> None:
        """Test setting sysvar value."""
        state_manager.add_system_variable(name="Counter", var_type="FLOAT", value=0.0)
        result = state_manager.set_system_variable("Counter", 42.0)
        assert result is True

        sv = state_manager.get_system_variable("Counter")
        assert sv is not None
        assert sv.value == 42.0

    def test_delete_sysvar(self, state_manager: StateManager) -> None:
        """Test deleting sysvar."""
        state_manager.add_system_variable(name="DeleteMe", var_type="BOOL", value=True)
        result = state_manager.delete_system_variable("DeleteMe")
        assert result is True
        assert state_manager.get_system_variable("DeleteMe") is None


class TestRoomsAndFunctions:
    """Test room and function operations."""

    def test_add_room(self, state_manager: StateManager) -> None:
        """Test adding a room."""
        room = state_manager.add_room(
            name="Living Room",
            description="Main living area",
        )
        assert room.name == "Living Room"
        assert room.id >= 3000

    def test_get_rooms(self, state_manager: StateManager) -> None:
        """Test getting all rooms."""
        state_manager.add_room(name="Room1")
        state_manager.add_room(name="Room2")

        rooms = state_manager.get_rooms()
        assert len(rooms) == 2

    def test_add_channel_to_room(self, state_manager: StateManager) -> None:
        """Test adding channel to room."""
        room = state_manager.add_room(name="Test Room")
        result = state_manager.add_channel_to_room(room.id, "ABC123:1")
        assert result is True

        updated = state_manager.get_room(room.id)
        assert updated is not None
        assert "ABC123:1" in updated.channel_ids

    def test_add_function(self, state_manager: StateManager) -> None:
        """Test adding a function."""
        func = state_manager.add_function(
            name="Lights",
            description="Lighting devices",
        )
        assert func.name == "Lights"
        assert func.id >= 4000

    def test_get_functions(self, state_manager: StateManager) -> None:
        """Test getting all functions."""
        state_manager.add_function(name="Func1")
        state_manager.add_function(name="Func2")

        functions = state_manager.get_functions()
        assert len(functions) == 2


class TestServiceMessages:
    """Test service message operations."""

    def test_add_service_message(self, state_manager: StateManager) -> None:
        """Test adding a service message."""
        msg = state_manager.add_service_message(
            name="Low Battery",
            msg_type="LOWBAT",
            address="ABC123:0",
            device_name="Test Sensor",
        )
        assert msg.msg_type == "LOWBAT"
        assert msg.timestamp > 0

    def test_get_service_messages(self, state_manager: StateManager) -> None:
        """Test getting service messages."""
        state_manager.add_service_message(
            name="Msg1",
            msg_type="UNREACH",
            address="A:0",
            device_name="Dev1",
        )
        state_manager.add_service_message(
            name="Msg2",
            msg_type="LOWBAT",
            address="B:0",
            device_name="Dev2",
        )

        messages = state_manager.get_service_messages()
        assert len(messages) == 2

    def test_clear_service_message(self, state_manager: StateManager) -> None:
        """Test clearing a service message."""
        msg = state_manager.add_service_message(
            name="Clear Me",
            msg_type="CONFIG_PENDING",
            address="X:0",
            device_name="Test",
        )
        result = state_manager.clear_service_message(msg.id)
        assert result is True
        assert len(state_manager.get_service_messages()) == 0


class TestBackup:
    """Test backup operations."""

    def test_start_backup(self, state_manager: StateManager) -> None:
        """Test starting backup."""
        pid = state_manager.start_backup()
        assert len(pid) > 0

        status = state_manager.get_backup_status()
        assert status["status"] == "running"
        assert status["pid"] == pid

    def test_complete_backup(self, state_manager: StateManager) -> None:
        """Test completing backup."""
        state_manager.start_backup()
        state_manager.complete_backup(b"backup data", "backup.sbk")

        status = state_manager.get_backup_status()
        assert status["status"] == "completed"
        assert status["filename"] == "backup.sbk"
        assert status["size"] == 11

    def test_get_backup_data(self, state_manager: StateManager) -> None:
        """Test getting backup data."""
        state_manager.complete_backup(b"test backup", "test.sbk")
        data = state_manager.get_backup_data()
        assert data == b"test backup"


class TestUpdateInfo:
    """Test firmware update operations."""

    def test_set_update_info(self, state_manager: StateManager) -> None:
        """Test setting update info."""
        state_manager.set_update_info(
            current="3.75.6",
            available="3.76.0",
        )
        info = state_manager.get_update_info()
        assert info.current_firmware == "3.75.6"
        assert info.available_firmware == "3.76.0"
        assert info.update_available is True

    def test_trigger_update(self, state_manager: StateManager) -> None:
        """Test triggering update."""
        state_manager.set_update_info(current="3.75.6", available="3.76.0")
        result = state_manager.trigger_update()
        assert result is True

        info = state_manager.get_update_info()
        assert info.current_firmware == "3.76.0"
        assert info.update_available is False


class TestDeviceValues:
    """Test device value operations."""

    def test_set_device_value(self, state_manager: StateManager) -> None:
        """Test setting device value."""
        state_manager.set_device_value("ABC123:1", "STATE", True)
        value = state_manager.get_device_value("ABC123:1", "STATE")
        assert value is True

    def test_get_all_device_values(self, state_manager: StateManager) -> None:
        """Test getting all device values."""
        state_manager.set_device_value("A:1", "STATE", True)
        state_manager.set_device_value("A:1", "LEVEL", 0.5)

        values = state_manager.get_all_device_values()
        assert "A:1:STATE" in values
        assert "A:1:LEVEL" in values


class TestDeviceNames:
    """Test device name operations."""

    def test_set_device_name(self, state_manager: StateManager) -> None:
        """Test setting device name."""
        state_manager.set_device_name("ABC123:1", "My Light")
        name = state_manager.get_device_name("ABC123:1")
        assert name == "My Light"

    def test_case_insensitive(self, state_manager: StateManager) -> None:
        """Test name lookup is case-insensitive."""
        state_manager.set_device_name("abc123:1", "Test")
        name = state_manager.get_device_name("ABC123:1")
        assert name == "Test"


class TestCallbacks:
    """Test callback registration."""

    def test_sysvar_callback(self, state_manager: StateManager) -> None:
        """Test sysvar change callback."""
        changes: list[tuple[str, object]] = []

        def callback(name: str, value: object) -> None:
            changes.append((name, value))

        state_manager.register_sysvar_callback(callback)
        state_manager.add_system_variable(name="Watched", var_type="BOOL", value=False)
        state_manager.set_system_variable("Watched", True)

        assert len(changes) == 1
        assert changes[0] == ("Watched", True)

    def test_program_callback(self, state_manager: StateManager) -> None:
        """Test program execution callback."""
        executions: list[tuple[int, bool]] = []

        def callback(prog_id: int, executed: bool) -> None:
            executions.append((prog_id, executed))

        state_manager.register_program_callback(callback)
        prog = state_manager.add_program(name="Watched")
        state_manager.execute_program(prog.id)

        assert len(executions) == 1
        assert executions[0] == (prog.id, True)


class TestClearAll:
    """Test clear_all operation."""

    def test_clear_all(self, state_manager: StateManager) -> None:
        """Test clearing all state."""
        state_manager.add_program(name="Prog")
        state_manager.add_system_variable(name="Var", var_type="BOOL", value=True)
        state_manager.add_room(name="Room")
        state_manager.add_function(name="Func")

        state_manager.clear_all()

        assert len(state_manager.get_programs()) == 0
        assert len(state_manager.get_system_variables()) == 0
        assert len(state_manager.get_rooms()) == 0
        assert len(state_manager.get_functions()) == 0
