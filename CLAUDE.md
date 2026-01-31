# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
pip install -e ".[test]"

# Run all tests
pytest

# Run single test file
pytest tests/test_state_manager.py

# Run single test
pytest tests/test_state_manager.py::TestPrograms::test_add_program -v

# Run with coverage
pytest --cov=pydevccu --cov-report=html

# Linting
ruff check pydevccu/
ruff check --fix pydevccu/

# Type checking
mypy pydevccu/ccu.py
```

## Architecture Overview

pydevccu is a virtual HomeMatic CCU server for testing Home Assistant integrations without real hardware.

### Core Components

**VirtualCCU** (`server.py`) - Main orchestrator that combines:

- XML-RPC server (legacy HomeMatic protocol)
- JSON-RPC server (CCU web API)
- State management
- Session authentication

**BackendMode** (`const.py`) - Three simulation modes:

- `HOMEGEAR`: XML-RPC only, minimal simulation
- `CCU`: Full CCU2/CCU3 simulation
- `OPENCCU`: OpenCCU/RaspberryMatic simulation

### Server Layer

**ccu.py** - Legacy XML-RPC server (`RPCFunctions`, `ServerThread`):

- HomeMatic protocol methods (getValue, setValue, putParamset, etc.)
- Method names are camelCase per HomeMatic specification
- Uses `@cache` decorators with manual cache clearing
- Raises `RPCError` for operation failures

**json_rpc/** - CCU-compatible JSON-RPC API:

- `server.py`: aiohttp server at `/api/homematic.cgi`
- `handlers.py`: Method dispatch (Session, Interface, Device, Program, SysVar, Room, ReGa)

### State Layer

**state/** - Centralized state management (`StateManager`):

- Programs, system variables, rooms, functions
- Device values and names
- Service messages, backup, firmware updates
- Callbacks for state changes

**session.py** - Token-based authentication (`SessionManager`)

### Script Engine

**rega/** - ReGa script pattern matching (`RegaEngine`):

- Parses aiohomematic script patterns
- Returns JSON responses for compatibility
- Pattern-based, not a full interpreter

### Device Simulation

**device_responses.py** - Device-specific parameter response mappings:

- Defines how devices respond to parameter changes
- Example: Setting `STATE` on a switch triggers `STATE` + `WORKING` events

**device_logic/** - Automated device behavior simulation:

- Optional periodic state changes for testing
- Class names match HomeMatic device names (e.g., `HM_Sec_SC_2`)

### Device Data

**device_descriptions/** and **paramset_descriptions/** - JSON files for 397 device types:

- Generated from HomeMatic firmware XML via `hm_xml_to_json.py`
- Each device has matching files in both directories

## Key Conventions

- XML-RPC methods use camelCase (HomeMatic protocol requirement)
- Internal Python methods use snake_case
- Device addresses are uppercase (e.g., `VCU0000001:1`)
- All files require `from __future__ import annotations`
