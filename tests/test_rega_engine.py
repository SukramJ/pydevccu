"""Tests for ReGa script engine."""

from __future__ import annotations

import json

from pydevccu.rega import RegaEngine
from pydevccu.state import StateManager


class TestRegaBackendInfo:
    """Test backend info script patterns."""

    def test_get_backend_info_version_pattern(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test VERSION pattern matching."""
        script = 'system.Exec("cat /VERSION | grep VERSION");'
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert "version" in data
        assert "product" in data

    def test_get_backend_info_grep_pattern(self, rega_engine: RegaEngine) -> None:
        """Test grep VERSION/PRODUCT pattern."""
        script = "grep VERSION /etc/config | grep PRODUCT"
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert data["product"] == "OpenCCU"


class TestRegaSerial:
    """Test serial number script pattern."""

    def test_get_serial(self, rega_engine: RegaEngine) -> None:
        """Test SERIALNO pattern.

        Returns JSON-encoded serial for aiohomematic compatibility.
        """
        script = 'var serial = system.GetVar("SERIALNO");'
        result = rega_engine.execute(script)

        assert result.success is True
        # Output is JSON-encoded string (e.g., '"DEVCCU0001"')
        serial = json.loads(result.output)
        assert isinstance(serial, str)
        assert len(serial) <= 10


class TestRegaPrograms:
    """Test program script patterns."""

    def test_get_programs(self, rega_engine_with_defaults: RegaEngine) -> None:
        """Test ID_PROGRAMS pattern."""
        script = "var progs = dom.GetObject(ID_PROGRAMS);"
        result = rega_engine_with_defaults.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_set_program_state(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test setting program active state."""
        prog = state_manager.add_program(name="Test", active=True)

        script = f"dom.GetObject({prog.id}).Active(false);"
        result = rega_engine.execute(script)

        assert result.success is True
        updated = state_manager.get_program(prog.id)
        assert updated is not None
        assert updated.active is False


class TestRegaSysvars:
    """Test system variable script patterns."""

    def test_get_sysvars(self, rega_engine_with_defaults: RegaEngine) -> None:
        """Test ID_SYSTEM_VARIABLES pattern."""
        script = "var sysvars = dom.GetObject(ID_SYSTEM_VARIABLES);"
        result = rega_engine_with_defaults.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_set_sysvar_string(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test setting sysvar with string value."""
        state_manager.add_system_variable(name="TestVar", var_type="STRING", value="")

        script = 'dom.GetObject("TestVar").State("new value");'
        result = rega_engine.execute(script)

        assert result.success is True
        sv = state_manager.get_system_variable("TestVar")
        assert sv is not None
        assert sv.value == "new value"

    def test_set_sysvar_number(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test setting sysvar with numeric value."""
        state_manager.add_system_variable(name="Counter", var_type="FLOAT", value=0.0)

        script = 'dom.GetObject("Counter").State(42.5);'
        result = rega_engine.execute(script)

        assert result.success is True
        sv = state_manager.get_system_variable("Counter")
        assert sv is not None
        assert sv.value == 42.5

    def test_set_sysvar_bool(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test setting sysvar with boolean value."""
        state_manager.add_system_variable(name="Flag", var_type="BOOL", value=False)

        script = 'dom.GetObject("Flag").State(true);'
        result = rega_engine.execute(script)

        assert result.success is True
        sv = state_manager.get_system_variable("Flag")
        assert sv is not None
        assert sv.value is True


class TestRegaServiceMessages:
    """Test service message script patterns."""

    def test_get_service_messages(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test ID_SERVICES pattern."""
        state_manager.add_service_message(
            name="Test Message",
            msg_type="LOWBAT",
            address="ABC:0",
            device_name="Test Device",
        )

        script = "var msgs = dom.GetObject(ID_SERVICES);"
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["type"] == "LOWBAT"


class TestRegaInbox:
    """Test inbox device script patterns."""

    def test_get_inbox(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test INBOX pattern."""
        state_manager.add_inbox_device(
            address="NEW123",
            name="New Device",
            device_type="HmIP-SWSD",
            interface="HmIP-RF",
        )

        script = "var inbox = INBOX.GetDevices();"
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["address"] == "NEW123"


class TestRegaBackup:
    """Test backup script patterns."""

    def test_backup_start(self, rega_engine: RegaEngine) -> None:
        """Test CreateBackup pattern."""
        script = "system.CreateBackup();"
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["status"] == "started"

    def test_backup_status(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test backup_status pattern."""
        state_manager.start_backup()
        state_manager.complete_backup(b"data", "backup.sbk")

        script = "var status = backup_status;"
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert data["status"] == "completed"


class TestRegaUpdate:
    """Test firmware update script patterns."""

    def test_get_update_info(self, rega_engine: RegaEngine) -> None:
        """Test checkFirmwareUpdate pattern."""
        script = 'system.Exec("checkFirmwareUpdate");'
        result = rega_engine.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert "currentFirmware" in data
        assert "updateAvailable" in data

    def test_trigger_update(self, rega_engine: RegaEngine, state_manager: StateManager) -> None:
        """Test trigger update pattern."""
        state_manager.set_update_info(current="3.75", available="3.76")

        # Use pattern that matches TRIGGER_UPDATE
        script = "TRIGGER_UPDATE();"
        result = rega_engine.execute(script)

        assert result.success is True
        info = state_manager.get_update_info()
        assert info.current_firmware == "3.76"


class TestRegaRooms:
    """Test room script patterns."""

    def test_get_rooms(self, rega_engine_with_defaults: RegaEngine) -> None:
        """Test ID_ROOMS pattern."""
        script = "var rooms = dom.GetObject(ID_ROOMS);"
        result = rega_engine_with_defaults.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1


class TestRegaFunctions:
    """Test function script patterns."""

    def test_get_functions(self, rega_engine_with_defaults: RegaEngine) -> None:
        """Test ID_FUNCTIONS pattern."""
        script = "var funcs = dom.GetObject(ID_FUNCTIONS);"
        result = rega_engine_with_defaults.execute(script)

        assert result.success is True
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1


class TestRegaWrite:
    """Test simple Write() pattern."""

    def test_write_string(self, rega_engine: RegaEngine) -> None:
        """Test Write() pattern."""
        script = 'Write("Hello World");'
        result = rega_engine.execute(script)

        assert result.success is True
        assert result.output == "Hello World"


class TestRegaUnknownPattern:
    """Test unknown script patterns."""

    def test_unknown_script(self, rega_engine: RegaEngine) -> None:
        """Test unknown script returns empty success."""
        script = "some.Unknown.Method();"
        result = rega_engine.execute(script)

        # Unknown patterns return empty success (not error)
        assert result.success is True
        assert result.output == ""
