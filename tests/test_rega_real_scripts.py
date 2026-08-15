"""
Run the engine against the *unmodified* ReGa scripts a real client sends.

The existing tests use hand-written script fragments, which is why six
scripts could be routed to the wrong handler without a single test going
red: set_program_state.fn and set_system_variable.fn were answered with
listings and changed nothing, accept_device_in_inbox.fn and
acknowledge_message.fn returned arrays instead of {"success": …},
create_backup_status.fn was answered with backend info, and
get_program_descriptions.fn came back in the wrong shape.

Each case asserts the way the client actually consumes the response —
the keys it indexes and the container type it iterates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import urllib.parse

import pytest

from pydevccu import BackendMode, StateManager
from pydevccu.rega import RegaEngine

SCRIPT_DIR = Path(__file__).parent / "testdata" / "rega_scripts"

# Placeholders a client substitutes before posting a script.
DEFAULT_PARAMS = {
    "interface": "HmIP-RF",
    "id": "1234",
    "state": "1",
    "name": "Var",
    "value": "text",
    "device_address": "VCU0000001",
    "message_id": "1",
}


def load_script(name: str, params: dict[str, str] | None = None) -> str:
    """Return the real script with its ##placeholders## substituted."""
    script = (SCRIPT_DIR / name).read_text(encoding="utf-8")
    for key, value in (params or {}).items():
        script = script.replace(f"##{key}##", value)
    return script


@pytest.fixture
def engine() -> RegaEngine:
    """Create an engine over an empty state."""
    return RegaEngine(state_manager=StateManager(mode=BackendMode.OPENCCU))


@pytest.fixture
def state() -> StateManager:
    """Create a fresh state manager."""
    return StateManager(mode=BackendMode.OPENCCU)


def engine_for(state: StateManager) -> RegaEngine:
    """Create an engine bound to the given state."""
    return RegaEngine(state_manager=state)


def script_names() -> list[str]:
    """List the shipped scripts."""
    return sorted(p.name for p in SCRIPT_DIR.glob("*.fn"))


class TestScriptRouting:
    """Every shipped script must reach a handler that produces its own shape."""

    @pytest.mark.parametrize("script_name", script_names())
    def test_every_script_is_routed_by_name(self, script_name: str, state: StateManager) -> None:
        """
        Regression for the whole finding class.

        An empty output means no handler claimed the script. The write
        scripts need their target to exist, otherwise they legitimately
        write nothing.
        """
        state.add_program(name="Programm", description="", active=True, program_id=1234)
        state.add_system_variable(name="Var", var_type="STRING", value="")
        engine = engine_for(state)

        result = engine.execute(load_script(script_name, DEFAULT_PARAMS))

        assert result.success is True
        assert result.output != "", f"no handler claimed {script_name}"
        json.loads(result.output)  # must be valid JSON


class TestWriteScripts:
    """The two scripts that silently changed nothing."""

    def test_set_program_state_changes_state(self, state: StateManager) -> None:
        """set_program_state.fn must flip the program and echo the new value."""
        program = state.add_program(name="Heizung", description="", active=True)
        engine = engine_for(state)

        result = engine.execute(load_script("set_program_state.fn", {"id": str(program.id), "state": "0"}))

        assert result.success is True
        assert state.get_program(program.id).active is False, "the write was swallowed"
        # The script ends in Write(program.Active()).
        assert result.output == "false"

    def test_set_system_variable_changes_value(self, state: StateManager) -> None:
        """set_system_variable.fn must write String variables."""
        state.add_system_variable(name="Statustext", var_type="STRING", value="alt")
        engine = engine_for(state)

        result = engine.execute(load_script("set_system_variable.fn", {"name": "Statustext", "value": "neu"}))

        assert result.success is True
        assert state.get_system_variable("Statustext").value == "neu", "the write was swallowed"

    def test_set_system_variable_ignores_non_string(self, state: StateManager) -> None:
        """The script only writes variables whose ValueTypeStr() is String."""
        state.add_system_variable(name="Anwesenheit", var_type="BOOL", value=False)
        engine = engine_for(state)

        result = engine.execute(load_script("set_system_variable.fn", {"name": "Anwesenheit", "value": "neu"}))

        assert result.output == ""
        assert state.get_system_variable("Anwesenheit").value is False


class TestFetchAllDeviceData:
    """The bulk fetch must be a mapping, not a list."""

    def test_result_is_a_mapping_keyed_by_datapoint_name(self, state: StateManager) -> None:
        """Clients call .items() on this — a list raises AttributeError."""
        state.set_device_value("VCU0000001:1", "STATE", True)
        state.set_device_value("VCU0000001:1", "LEVEL", 0.5)
        engine = engine_for(state)

        result = engine.execute(load_script("fetch_all_device_data.fn", {"interface": "HmIP-RF"}))
        data: dict[str, Any] = json.loads(result.output)

        assert isinstance(data, dict), "the bulk fetch must be an object"
        want = "HmIP-RF.VCU0000001:1.STATE"
        decoded = {urllib.parse.unquote(k): v for k, v in data.items()}
        assert want in decoded, f"missing key {want}: {list(decoded)}"
        assert decoded[want] is True
        for key in decoded:
            assert key.startswith("HmIP-RF."), f"key {key} lacks the interface prefix"

    def test_empty_cache_is_an_empty_object(self, engine: RegaEngine) -> None:
        """The script frames its output with Write('{') … Write('}')."""
        result = engine.execute(load_script("fetch_all_device_data.fn", {"interface": "HmIP-RF"}))
        assert json.loads(result.output) == {}


class TestInboxScripts:
    """Listing shape plus the accept script the INBOX catch-all swallowed."""

    def test_listing_uses_the_scripts_keys(self, state: StateManager) -> None:
        """get_inbox_devices.fn writes id/type, not deviceId/deviceType."""
        state.add_inbox_device(address="VCU0000009", name="Neuer Schalter", device_type="HmIP-PS", interface="HmIP-RF")
        engine = engine_for(state)

        devices = json.loads(engine.execute(load_script("get_inbox_devices.fn")).output)

        assert len(devices) == 1
        for key in ("id", "address", "name", "type", "interface"):
            assert key in devices[0], f"inbox entry missing {key}"
        assert "deviceType" not in devices[0]

    def test_accept_returns_a_success_object(self, state: StateManager) -> None:
        """The client calls .get("success") — an array raises AttributeError."""
        state.add_inbox_device(address="VCU0000009", name="Neuer Schalter", device_type="HmIP-PS", interface="HmIP-RF")
        engine = engine_for(state)

        result = json.loads(
            engine.execute(load_script("accept_device_in_inbox.fn", {"device_address": "VCU0000009"})).output
        )

        assert isinstance(result, dict)
        assert result["success"] is True
        assert state.get_inbox_devices() == []

    def test_accept_unknown_device_reports_error(self, engine: RegaEngine) -> None:
        """An unknown address answers with success=false and a reason."""
        result = json.loads(
            engine.execute(load_script("accept_device_in_inbox.fn", {"device_address": "VCU0000404"})).output
        )

        assert result["success"] is False
        assert result["error"] == "Device not found"


class TestAcknowledgeMessage:
    """The second {"success": …} script."""

    def test_acknowledge_clears_the_message(self, state: StateManager) -> None:
        """acknowledge_message.fn receipts the service message."""
        message = state.add_service_message(
            name="UNREACH", msg_type="UNREACH", address="VCU0000001:0", device_name="Schalter"
        )
        engine = engine_for(state)

        result = json.loads(
            engine.execute(load_script("acknowledge_message.fn", {"message_id": str(message.id)})).output
        )

        assert result["success"] is True
        assert state.get_service_messages() == []


class TestBackupAndUpdateShapes:
    """Scripts whose keys the generic patterns replaced."""

    def test_backup_status_reports_status_only_while_unfinished(self, engine: RegaEngine) -> None:
        """create_backup_status.fn was answered with backend info."""
        status = json.loads(engine.execute(load_script("create_backup_status.fn")).output)

        assert status["status"] == "idle", "got backend info instead of the backup status"
        assert list(status) == ["status"], "an unfinished backup reports nothing else"

    def test_backend_info_uses_is_ha_app(self, engine: RegaEngine) -> None:
        """get_backend_info.fn writes is_ha_app, not is_ha_addon."""
        info = json.loads(engine.execute(load_script("get_backend_info.fn")).output)

        assert "is_ha_app" in info
        assert info["product"] == "OpenCCU"

    def test_update_scripts_use_snake_case(self, state: StateManager) -> None:
        """Both firmware scripts write snake_case keys."""
        state.set_update_info(current="3.87.0", available="3.87.1")
        engine = engine_for(state)

        info = json.loads(engine.execute(load_script("get_system_update_info.fn")).output)
        for key in (
            "current_firmware",
            "available_firmware",
            "update_available",
            "check_script_available",
        ):
            assert key in info

        trigger = json.loads(engine.execute(load_script("trigger_firmware_update.fn")).output)
        for key in ("success", "script_available", "message"):
            assert key in trigger

    def test_program_descriptions_shape(self, state: StateManager) -> None:
        """get_program_descriptions.fn emits {id: string, description}."""
        state.add_program(name="Heizung", description="Beschreibung mit Leerzeichen", active=True)
        engine = engine_for(state)

        entries = json.loads(engine.execute(load_script("get_program_descriptions.fn")).output)

        assert len(entries) == 1
        assert isinstance(entries[0]["id"], str)
        assert urllib.parse.unquote(entries[0]["description"]) == "Beschreibung mit Leerzeichen"

    def test_alarm_messages_are_empty(self, engine: RegaEngine) -> None:
        """get_alarm_messages.fn must not fall through to the sysvar listing."""
        assert engine.execute(load_script("get_alarm_messages.fn")).output == "[]"
