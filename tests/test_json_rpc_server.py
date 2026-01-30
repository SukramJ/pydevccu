"""Tests for JSON-RPC server and handlers."""

from __future__ import annotations

import pytest

from pydevccu.json_rpc.errors import InvalidParams, InvalidRequest, MethodNotFound, ObjectNotFound, ParseError
from pydevccu.json_rpc.handlers import JsonRpcHandlers
from pydevccu.json_rpc.server import JsonRpcRequest


class TestJsonRpcRequest:
    """Test JSON-RPC request parsing."""

    def test_parse_valid_request_v20(self) -> None:
        """Test parsing a valid JSON-RPC 2.0 request."""
        data = {
            "jsonrpc": "2.0",
            "method": "test.method",
            "params": {"key": "value"},
            "id": 1,
        }
        request = JsonRpcRequest.from_dict(data)

        assert request.jsonrpc == "2.0"
        assert request.method == "test.method"
        assert request.params == {"key": "value"}
        assert request.id == 1

    def test_parse_valid_request_v11(self) -> None:
        """Test parsing a valid JSON-RPC 1.1 request (aiohomematic compatibility)."""
        data = {
            "jsonrpc": "1.1",
            "method": "Session.login",
            "params": {"username": "Admin", "password": "test"},
            "id": 0,
        }
        request = JsonRpcRequest.from_dict(data)

        assert request.jsonrpc == "1.1"
        assert request.method == "Session.login"
        assert request.params == {"username": "Admin", "password": "test"}
        assert request.id == 0

    def test_parse_notification(self) -> None:
        """Test parsing a notification (no id)."""
        data = {
            "jsonrpc": "2.0",
            "method": "notify",
        }
        request = JsonRpcRequest.from_dict(data)

        assert request.id is None

    def test_parse_invalid_version(self) -> None:
        """Test parsing with invalid version."""
        data = {
            "jsonrpc": "1.0",
            "method": "test",
        }
        with pytest.raises(InvalidRequest):
            JsonRpcRequest.from_dict(data)

    def test_parse_missing_method(self) -> None:
        """Test parsing with missing method."""
        data = {
            "jsonrpc": "2.0",
        }
        with pytest.raises(InvalidRequest):
            JsonRpcRequest.from_dict(data)

    def test_parse_invalid_params(self) -> None:
        """Test parsing with invalid params type."""
        data = {
            "jsonrpc": "2.0",
            "method": "test",
            "params": "not-valid",
        }
        with pytest.raises(InvalidRequest):
            JsonRpcRequest.from_dict(data)


class TestJsonRpcErrors:
    """Test JSON-RPC error classes."""

    def test_parse_error(self) -> None:
        """Test ParseError."""
        error = ParseError("Bad JSON")
        assert error.code == -32700
        assert "Bad JSON" in error.message

    def test_method_not_found(self) -> None:
        """Test MethodNotFound."""
        error = MethodNotFound("Unknown.method")
        assert error.code == -32601
        assert "Unknown.method" in error.message

    def test_object_not_found(self) -> None:
        """Test ObjectNotFound."""
        error = ObjectNotFound("Device", "ABC123")
        assert error.code == -32004
        assert "Device" in error.message
        assert "ABC123" in error.message

    def test_error_to_dict(self) -> None:
        """Test error serialization."""
        error = InvalidParams("Missing param")
        d = error.to_dict()

        assert d["code"] == -32602
        assert d["message"] == "Missing param"


class TestHandlersSession:
    """Test session-related handlers."""

    @pytest.mark.asyncio
    async def test_session_login(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Session.login handler."""
        result = await json_rpc_handlers._handle_session_login(
            {
                "username": "Admin",
                "password": "test123",
            }
        )

        assert "_session_id_" in result
        assert len(result["_session_id_"]) == 32

    @pytest.mark.asyncio
    async def test_session_login_invalid(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Session.login with invalid credentials."""
        result = await json_rpc_handlers._handle_session_login(
            {
                "username": "Admin",
                "password": "wrong",
            }
        )

        assert result["_session_id_"] == ""
        assert "error" in result

    @pytest.mark.asyncio
    async def test_session_logout(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Session.logout handler."""
        # First login
        login_result = await json_rpc_handlers._handle_session_login(
            {
                "username": "Admin",
                "password": "test123",
            }
        )
        session_id = login_result["_session_id_"]

        # Then logout
        result = await json_rpc_handlers._handle_session_logout(
            {
                "_session_id_": session_id,
            }
        )

        assert result["success"] is True


class TestHandlersCCU:
    """Test CCU namespace handlers."""

    @pytest.mark.asyncio
    async def test_get_auth_enabled(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test CCU.getAuthEnabled handler."""
        result = await json_rpc_handlers._handle_get_auth_enabled({})
        assert result is True

    @pytest.mark.asyncio
    async def test_get_https_redirect(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test CCU.getHttpsRedirectEnabled handler."""
        result = await json_rpc_handlers._handle_get_https_redirect({})
        assert result is False

    @pytest.mark.asyncio
    async def test_list_methods(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test system.listMethods handler."""
        result = await json_rpc_handlers._handle_list_methods({})
        assert isinstance(result, list)
        # Result is list of dicts with "name" key (aiohomematic format)
        method_names = [m["name"] for m in result]
        assert "Session.login" in method_names
        assert "Program.getAll" in method_names


class TestHandlersPrograms:
    """Test program handlers."""

    @pytest.mark.asyncio
    async def test_program_get_all(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Program.getAll handler."""
        # Add a program first
        json_rpc_handlers._state.add_program(name="Test Prog")

        result = await json_rpc_handlers._handle_program_get_all({})

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "Test Prog"

    @pytest.mark.asyncio
    async def test_program_execute(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Program.execute handler."""
        prog = json_rpc_handlers._state.add_program(name="Exec Test")

        result = await json_rpc_handlers._handle_program_execute(
            {
                "id": str(prog.id),
            }
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_program_set_active(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Program.setActive handler."""
        prog = json_rpc_handlers._state.add_program(name="Active Test", active=True)

        result = await json_rpc_handlers._handle_program_set_active(
            {
                "id": prog.id,
                "active": False,
            }
        )

        assert result["success"] is True
        updated = json_rpc_handlers._state.get_program(prog.id)
        assert updated is not None
        assert updated.active is False


class TestHandlersSysvars:
    """Test system variable handlers."""

    @pytest.mark.asyncio
    async def test_sysvar_get_all(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test SysVar.getAll handler."""
        json_rpc_handlers._state.add_system_variable(
            name="TestVar",
            var_type="BOOL",
            value=True,
        )

        result = await json_rpc_handlers._handle_sysvar_get_all({})

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "TestVar"

    @pytest.mark.asyncio
    async def test_sysvar_get_value_by_name(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test SysVar.getValueByName handler."""
        json_rpc_handlers._state.add_system_variable(
            name="GetMe",
            var_type="FLOAT",
            value=42.5,
        )

        result = await json_rpc_handlers._handle_sysvar_get_value_by_name(
            {
                "name": "GetMe",
            }
        )

        assert result == 42.5

    @pytest.mark.asyncio
    async def test_sysvar_get_value_not_found(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test SysVar.getValueByName with unknown name."""
        with pytest.raises(ObjectNotFound):
            await json_rpc_handlers._handle_sysvar_get_value_by_name(
                {
                    "name": "Unknown",
                }
            )

    @pytest.mark.asyncio
    async def test_sysvar_set_bool(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test SysVar.setBool handler."""
        json_rpc_handlers._state.add_system_variable(
            name="BoolVar",
            var_type="BOOL",
            value=False,
        )

        result = await json_rpc_handlers._handle_sysvar_set_bool(
            {
                "name": "BoolVar",
                "value": True,
            }
        )

        assert result["success"] is True
        sv = json_rpc_handlers._state.get_system_variable("BoolVar")
        assert sv is not None
        assert sv.value is True

    @pytest.mark.asyncio
    async def test_sysvar_set_float(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test SysVar.setFloat handler."""
        json_rpc_handlers._state.add_system_variable(
            name="FloatVar",
            var_type="FLOAT",
            value=0.0,
        )

        result = await json_rpc_handlers._handle_sysvar_set_float(
            {
                "name": "FloatVar",
                "value": 123.45,
            }
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sysvar_delete(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test SysVar.deleteSysVarByName handler."""
        json_rpc_handlers._state.add_system_variable(
            name="DeleteMe",
            var_type="STRING",
            value="",
        )

        result = await json_rpc_handlers._handle_sysvar_delete(
            {
                "name": "DeleteMe",
            }
        )

        assert result["success"] is True
        assert json_rpc_handlers._state.get_system_variable("DeleteMe") is None


class TestHandlersRooms:
    """Test room handlers."""

    @pytest.mark.asyncio
    async def test_room_get_all(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Room.getAll handler."""
        json_rpc_handlers._state.add_room(name="Living Room")
        json_rpc_handlers._state.add_room(name="Kitchen")

        result = await json_rpc_handlers._handle_room_get_all({})

        assert isinstance(result, list)
        assert len(result) == 2


class TestHandlersFunctions:
    """Test function/subsection handlers."""

    @pytest.mark.asyncio
    async def test_subsection_get_all(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Subsection.getAll handler."""
        json_rpc_handlers._state.add_function(name="Lights")
        json_rpc_handlers._state.add_function(name="Heating")

        result = await json_rpc_handlers._handle_subsection_get_all({})

        assert isinstance(result, list)
        assert len(result) == 2


class TestHandlersReGa:
    """Test ReGa script handler."""

    @pytest.mark.asyncio
    async def test_rega_run_script(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test ReGa.runScript handler.

        Returns output directly (not wrapped in STDOUT) for aiohomematic compatibility.
        """
        result = await json_rpc_handlers._handle_rega_run_script(
            {
                "script": 'Write("test");',
            }
        )

        # Result is returned directly as a string for aiohomematic to parse
        assert result == "test"

    @pytest.mark.asyncio
    async def test_rega_run_script_missing_param(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test ReGa.runScript with missing script."""
        with pytest.raises(InvalidParams):
            await json_rpc_handlers._handle_rega_run_script({})


class TestHandlersInterface:
    """Test interface handlers."""

    @pytest.mark.asyncio
    async def test_list_interfaces(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Interface.listInterfaces handler."""
        result = await json_rpc_handlers._handle_list_interfaces({})

        assert isinstance(result, list)
        assert len(result) >= 2
        names = [i["name"] for i in result]
        assert "HmIP-RF" in names
        assert "BidCos-RF" in names

    @pytest.mark.asyncio
    async def test_ping(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Interface.ping handler."""
        result = await json_rpc_handlers._handle_ping({})
        assert result is True

    @pytest.mark.asyncio
    async def test_get_install_mode(self, json_rpc_handlers: JsonRpcHandlers) -> None:
        """Test Interface.getInstallMode handler."""
        result = await json_rpc_handlers._handle_get_install_mode({})
        assert result == 0
