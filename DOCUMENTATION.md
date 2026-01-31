# pydevccu - Complete Documentation

## What is pydevccu?

**pydevccu** is a virtual HomeMatic CCU (Central Control Unit) server for development and testing. It simulates a complete HomeMatic CCU without requiring real hardware, enabling testing of HomeMatic integrations (e.g., aiohomematic/Home Assistant).

|                |                                     |
| -------------- | ----------------------------------- |
| **Version**    | 0.2.0                               |
| **License**    | MIT                                 |
| **Python**     | >=3.13.0                            |
| **Repository** | https://github.com/sukramj/pydevccu |

---

## Architecture Overview

```
pydevccu/
├── ccu.py                    # XML-RPC server (legacy)
├── server.py                 # VirtualCCU orchestrator
├── session.py                # Session management & authentication
├── state/                    # State management subsystem
│   ├── manager.py            # Thread-safe StateManager
│   ├── models.py             # Dataclass models
│   └── defaults.py           # Default test data
├── json_rpc/                 # JSON-RPC API subsystem
│   ├── server.py             # aiohttp-based server
│   ├── handlers.py           # Method handlers
│   └── errors.py             # Error definitions
├── rega/                     # ReGa script engine
│   └── engine.py             # Pattern-matching interpreter
├── device_descriptions/      # 397 device JSON files
└── paramset_descriptions/    # Device paramset metadata
```

---

## Supported Backend Modes

| Mode         | XML-RPC | JSON-RPC | Auth | ReGa Scripts | Use Case                          |
| ------------ | ------- | -------- | ---- | ------------ | --------------------------------- |
| **HOMEGEAR** | Yes     | No       | No   | No           | Minimal XML-RPC simulation        |
| **CCU**      | Yes     | Yes      | Yes  | Yes          | CCU2/CCU3 simulation              |
| **OPENCCU**  | Yes     | Yes      | Yes  | Yes          | OpenCCU/RaspberryMatic simulation |

---

## Supported Devices

- **397 device types** in `/device_descriptions/`
- HomeMatic Wireless (HM-\*)
- HomeMatic IP (HmIP-\*)
- ELV Smart Home (ELV-SH-\*)
- ALPHA-IP devices

---

## XML-RPC Methods (Port 2010)

### Device Management

| Method                 | Parameters     | Returns                    | Description            |
| ---------------------- | -------------- | -------------------------- | ---------------------- |
| `listDevices`          | `interface_id` | `[Device]`                 | List all devices       |
| `getDeviceDescription` | `address`      | `Device`                   | Get device description |
| `getServiceMessages`   | -              | `[[address, type, value]]` | Get service messages   |

### Parameter Operations

| Method                   | Parameters                                     | Returns           | Description                      |
| ------------------------ | ---------------------------------------------- | ----------------- | -------------------------------- |
| `getValue`               | `address`, `value_key`                         | `value`           | Get single parameter value       |
| `setValue`               | `address`, `value_key`, `value`, `force`       | `""`              | Set parameter value, fires event |
| `getParamset`            | `address`, `paramset_key`                      | `{param: value}`  | Get all paramset values          |
| `putParamset`            | `address`, `paramset_key`, `paramset`, `force` | `""`              | Set multiple parameters          |
| `getParamsetDescription` | `address`, `paramset_type`                     | `{param: schema}` | Get paramset schema              |

### System Variables

| Method                  | Parameters      | Returns         | Description               |
| ----------------------- | --------------- | --------------- | ------------------------- |
| `getAllSystemVariables` | -               | `{name: value}` | Get all system variables  |
| `getSystemVariable`     | `name`          | `value`         | Get system variable value |
| `setSystemVariable`     | `name`, `value` | -               | Set system variable       |
| `deleteSystemVariable`  | `name`          | -               | Delete system variable    |

### Session/Callback

| Method                    | Parameters            | Returns | Description                 |
| ------------------------- | --------------------- | ------- | --------------------------- |
| `init`                    | `url`, `interface_id` | `""`    | Register callback URL       |
| `ping`                    | `caller_id`           | `True`  | Heartbeat check             |
| `clientServerInitialized` | `interface_id`        | `bool`  | Check client initialization |

### Installation Mode

| Method           | Parameters                             | Returns | Description                     |
| ---------------- | -------------------------------------- | ------- | ------------------------------- |
| `getInstallMode` | -                                      | `int`   | Get remaining install mode time |
| `setInstallMode` | `on`, `time`, `mode`, `device_address` | `True`  | Set install mode                |

### Firmware Operations

| Method            | Parameters       | Returns             | Description      |
| ----------------- | ---------------- | ------------------- | ---------------- |
| `getVersion`      | -                | `"3.87.1.20250130"` | Get CCU version  |
| `installFirmware` | `device_address` | `True`              | Install firmware |
| `updateFirmware`  | `device_address` | `True`              | Update firmware  |

### Linking

| Method         | Parameters                                  | Returns | Description        |
| -------------- | ------------------------------------------- | ------- | ------------------ |
| `addLink`      | `sender`, `receiver`, `name`, `description` | `True`  | Create device link |
| `removeLink`   | `sender`, `receiver`                        | `True`  | Remove device link |
| `getLinkPeers` | `channel_address`                           | `[]`    | Get link peers     |
| `getLinks`     | `channel_address`, `flags`                  | `[]`    | Get all links      |

### Metadata

| Method        | Parameters                    | Returns | Description         |
| ------------- | ----------------------------- | ------- | ------------------- |
| `getMetadata` | `object_id`, `data_id`        | `value` | Get device metadata |
| `setMetadata` | `address`, `data_id`, `value` | `True`  | Set device metadata |

---

## JSON-RPC Methods (Port 80/8080)

**Endpoint:** `/api/homematic.cgi`

### Session Namespace

| Method           | Parameters             | Returns          | Description       |
| ---------------- | ---------------------- | ---------------- | ----------------- |
| `Session.login`  | `username`, `password` | `{_session_id_}` | Authenticate user |
| `Session.logout` | `_session_id_`         | `{success}`      | End session       |
| `Session.renew`  | `_session_id_`         | `{_session_id_}` | Renew session     |

### CCU Namespace

| Method                        | Parameters | Returns    | Description              |
| ----------------------------- | ---------- | ---------- | ------------------------ |
| `CCU.getAuthEnabled`          | -          | `bool`     | Check if auth is enabled |
| `CCU.getHttpsRedirectEnabled` | -          | `bool`     | Check HTTPS redirect     |
| `system.listMethods`          | -          | `[{name}]` | List available methods   |

### Interface Namespace

| Method                             | Parameters                      | Returns                | Description            |
| ---------------------------------- | ------------------------------- | ---------------------- | ---------------------- |
| `Interface.listInterfaces`         | -                               | `[{name, port, type}]` | List interfaces        |
| `Interface.listDevices`            | -                               | `[Device]`             | List all devices       |
| `Interface.getDeviceDescription`   | `address`                       | `Device`               | Get device description |
| `Interface.getValue`               | `address`, `valueKey`           | `value`                | Get parameter value    |
| `Interface.setValue`               | `address`, `valueKey`, `value`  | `bool`                 | Set parameter value    |
| `Interface.getParamset`            | `address`, `paramsetKey`        | `{params}`             | Get paramset values    |
| `Interface.putParamset`            | `address`, `paramsetKey`, `set` | `bool`                 | Set paramset values    |
| `Interface.getParamsetDescription` | `address`, `paramsetKey`        | `{schema}`             | Get paramset schema    |
| `Interface.isPresent`              | `address`                       | `bool`                 | Check device presence  |
| `Interface.getInstallMode`         | -                               | `int`                  | Get install mode time  |
| `Interface.setInstallMode`         | `mode`                          | `bool`                 | Set install mode       |
| `Interface.setInstallModeHMIP`     | `mode`                          | `bool`                 | Set HmIP install mode  |
| `Interface.getMasterValue`         | `address`, `valueKey`           | `value`                | Get master value       |
| `Interface.ping`                   | -                               | `True`                 | Heartbeat check        |
| `Interface.init`                   | `url`, `interfaceId`            | `string`               | Register callback      |

### Device/Channel Namespace

| Method                  | Parameters        | Returns                           | Description                |
| ----------------------- | ----------------- | --------------------------------- | -------------------------- |
| `Device.listAllDetail`  | -                 | `[{id, address, type, channels}]` | List devices with channels |
| `Device.get`            | `address`         | `{id, address, type, name}`       | Get device info            |
| `Device.setName`        | `address`, `name` | `bool`                            | Set device name            |
| `Channel.setName`       | `address`, `name` | `bool`                            | Set channel name           |
| `Channel.hasProgramIds` | `address`         | `[ids]`                           | Get associated programs    |

### Program Namespace

| Method              | Parameters     | Returns                              | Description                 |
| ------------------- | -------------- | ------------------------------------ | --------------------------- |
| `Program.getAll`    | -              | `[{id, name, isActive, isInternal}]` | List all programs           |
| `Program.execute`   | `id`           | `{success}`                          | Execute program             |
| `Program.setActive` | `id`, `active` | `{success}`                          | Activate/deactivate program |

### SysVar Namespace

| Method                      | Parameters      | Returns                                 | Description               |
| --------------------------- | --------------- | --------------------------------------- | ------------------------- |
| `SysVar.getAll`             | -               | `[{id, name, type, value, isInternal}]` | List all system variables |
| `SysVar.getValueByName`     | `name`          | `value`                                 | Get variable value        |
| `SysVar.setBool`            | `name`, `value` | `{success}`                             | Set boolean variable      |
| `SysVar.setFloat`           | `name`, `value` | `{success}`                             | Set float variable        |
| `SysVar.setString`          | `name`, `value` | `{success}`                             | Set string variable       |
| `SysVar.deleteSysVarByName` | `name`          | `{success}`                             | Delete variable           |

### Room/Subsection Namespace

| Method              | Parameters | Returns                    | Description            |
| ------------------- | ---------- | -------------------------- | ---------------------- |
| `Room.getAll`       | -          | `[{id, name, channelIds}]` | List all rooms         |
| `Room.listAll`      | -          | `[{id, name, channelIds}]` | List all rooms (alias) |
| `Subsection.getAll` | -          | `[{id, name, channelIds}]` | List all functions     |

### ReGa Namespace

| Method           | Parameters | Returns  | Description         |
| ---------------- | ---------- | -------- | ------------------- |
| `ReGa.runScript` | `script`   | `string` | Execute ReGa script |

---

## ReGa Script Engine

Pattern-based interpreter for aiohomematic compatibility. Instead of implementing a full ReGa language interpreter, uses regex pattern matching to recognize and handle common scripts.

### Supported Script Patterns

| Script Name                           | Pattern                              | Output                                            |
| ------------------------------------- | ------------------------------------ | ------------------------------------------------- |
| `get_backend_info.fn`                 | `system.Exec.*cat.*/VERSION`         | `{version, product, hostname, is_ha_addon}`       |
| `get_serial.fn`                       | `system.GetVar("SERIALNO")`          | JSON-encoded serial number                        |
| `fetch_all_device_data.fn`            | `dom.GetObject(ID_DATAPOINTS)`       | `[{address, param, value}]`                       |
| `get_program_descriptions.fn`         | `dom.GetObject(ID_PROGRAMS)`         | `[{id, name, description, isActive, isInternal}]` |
| `get_system_variable_descriptions.fn` | `dom.GetObject(ID_SYSTEM_VARIABLES)` | `[{id, name, type, value, isInternal}]`           |
| `get_service_messages.fn`             | `dom.GetObject(ID_SERVICES)`         | `[{id, name, timestamp, type, address}]`          |
| `get_inbox_devices.fn`                | `INBOX`                              | `[{deviceId, address, name, deviceType}]`         |
| `set_program_state.fn`                | `dom.GetObject(id).Active(bool)`     | Empty (side effect)                               |
| `set_system_variable.fn`              | `dom.GetObject("name").State(value)` | Empty (side effect)                               |
| `create_backup_start.fn`              | `CreateBackup`                       | `{success, status, pid}`                          |
| `create_backup_status.fn`             | `backup.pid`                         | `{status, pid, filename, size}`                   |
| `get_system_update_info.fn`           | `checkFirmwareUpdate`                | `{currentFirmware, availableFirmware}`            |
| `trigger_firmware_update.fn`          | `nohup.*checkFirmwareUpdate`         | `{success}`                                       |
| `get_rooms.fn`                        | `ID_ROOMS`                           | `[{id, name, channelIds}]`                        |
| `get_functions.fn`                    | `ID_FUNCTIONS`                       | `[{id, name, channelIds}]`                        |

---

## State Management

Thread-safe management using `threading.RLock()` with callback support.

### Programs

```python
state_manager.add_program(name, description, active, program_id)
state_manager.get_programs() -> List[Program]
state_manager.execute_program(program_id) -> bool
state_manager.set_program_active(program_id, active) -> bool
```

### System Variables

Supported types: `BOOL`, `FLOAT`, `STRING`, `ENUM`

```python
state_manager.add_system_variable(name, var_type, value, description, unit, value_list, min_value, max_value)
state_manager.get_system_variables() -> List[SystemVariable]
state_manager.set_system_variable(name, value) -> bool
```

### Rooms & Functions

```python
state_manager.add_room(name, description, channel_ids)
state_manager.add_function(name, description, channel_ids)
state_manager.add_channel_to_room(room_id, channel_id)
```

### Service Messages

Message types: `UNREACH`, `CONFIG_PENDING`, `LOWBAT`, etc.

```python
state_manager.add_service_message(name, msg_type, address, device_name)
state_manager.clear_service_message(msg_id)
```

### Callbacks

```python
state_manager.register_sysvar_callback(callback)
state_manager.register_program_callback(callback)
```

---

## Session Management

- 32-character random session IDs using `secrets.token_hex()`
- Configurable timeout (default: 30 minutes)
- Automatic expiration and cleanup
- Optional authentication bypass (`auth_enabled=False`)

```python
session_manager = SessionManager(
    username="Admin",
    password="",
    session_timeout=1800,
    auth_enabled=True,
)
```

---

## Device Response Logic

When parameters are set via `setValue` or `putParamset`, pydevccu simulates realistic device behavior by sending appropriate response events based on the device type.

### How It Works

1. Client sends `setValue(address, "LEVEL", 0.5)` to a dimmer
2. pydevccu identifies the device type (e.g., `HmIP-BDT`)
3. Response mapping computes appropriate events
4. Events are fired back to client (e.g., `LEVEL=0.5`, `ACTIVITY_STATE=2`)

### Supported Device Response Mappings

| Device Type                                     | Trigger Parameter        | Response Events                                             |
| ----------------------------------------------- | ------------------------ | ----------------------------------------------------------- |
| **HmIP-PS, HmIP-PSM, HmIP-BSM** (Switches)      | `STATE`                  | `STATE`, `WORKING=false`                                    |
| **HmIP-BDT, HmIP-PDT, HmIP-FDT** (Dimmers)      | `LEVEL`                  | `LEVEL`, `ACTIVITY_STATE` (0=off, 2=active)                 |
| **HmIP-BROLL, HmIP-BBL, HmIP-FBL** (Blinds)     | `LEVEL`                  | `LEVEL`, preserves `LEVEL_2` (slat position)                |
| **HmIP-eTRV, HmIP-WTH, HmIP-STH** (Thermostats) | `SET_POINT_TEMPERATURE`  | `SET_POINT_TEMPERATURE`, `CONTROL_MODE`                     |
| **HmIP-DLD** (Door Lock)                        | `LOCK_TARGET_LEVEL`      | `LOCK_STATE` (1=locked, 2=unlocked)                         |
| **HmIP-SWSD** (Smoke Detector)                  | `SMOKE_DETECTOR_COMMAND` | `SMOKE_DETECTOR_ALARM_STATUS`, `SMOKE_DETECTOR_TEST_RESULT` |
| **Unknown devices**                             | Any                      | Echoes the parameter back                                   |

### Adding Custom Response Mappings

Edit `pydevccu/device_responses.py`:

```python
from pydevccu.device_responses import DEVICE_RESPONSE_MAPPINGS, ParameterResponse

# Add custom mapping
DEVICE_RESPONSE_MAPPINGS["HmIP-CUSTOM"] = {
    "MY_PARAM": ParameterResponse(
        trigger_param="MY_PARAM",
        value_transformer=lambda value, current: {"MY_PARAM": value, "STATUS": 1},
    ),
}
```

---

## What Happens When...?

| Action                                                 | Response                                                                                                                          |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| **Client calls `init(url, interface_id)`**             | pydevccu registers callback URL, queries client for known devices via `listDevices`, pushes new devices via `newDevices` callback |
| **Client calls `setValue(address, key, value)`**       | Value validated, stored, device-specific response events computed and fired to all registered clients                             |
| **Client calls `putParamset(address, key, paramset)`** | Each value validated and stored, device-specific response events fired for each parameter                                         |
| **Client calls `getParamset(address, "VALUES")`**      | Returns paramset defaults merged with stored overrides                                                                            |
| **ReGa script executed**                               | Pattern matching identifies script type, appropriate handler returns JSON string                                                  |
| **Session expires**                                    | All authenticated methods return `SessionExpired` error (-32001)                                                                  |
| **Device added via `addDevices()`**                    | `newDevices` callback sent to all registered clients                                                                              |
| **Device removed via `removeDevices()`**               | `deleteDevices` callback sent to all registered clients                                                                           |
| **Ping received**                                      | Returns `True`, confirms connection is alive                                                                                      |
| **Invalid JSON-RPC version**                           | Accepts both 1.1 (CCU) and 2.0, responds with 1.1                                                                                 |

---

## VirtualCCU Configuration

```python
from pydevccu import VirtualCCU, BackendMode

ccu = VirtualCCU(
    mode: BackendMode = BackendMode.OPENCCU,  # Backend mode
    host: str = "127.0.0.1",                  # Bind address
    xml_rpc_port: int = 2010,                 # XML-RPC port
    json_rpc_port: int = 80,                  # JSON-RPC port
    username: str = "Admin",                  # Auth username
    password: str = "",                       # Auth password
    auth_enabled: bool = True,                # Enable authentication
    devices: list[str] | None = None,         # Filter device types
    persistence: bool = False,                # Persist paramsets to disk
    serial: str = "PYDEVCCU0001",             # CCU serial number
    setup_defaults: bool = False,             # Create sample data
)
```

---

## Usage Examples

### Basic Server (XML-RPC only)

```python
import pydevccu

server = pydevccu.Server(
    devices=['HmIP-SWSD'],
    persistence=True,
    logic={"startupdelay": 5, "interval": 30},
)
server.start()
```

### Full VirtualCCU (XML + JSON-RPC)

```python
import asyncio
from pydevccu import VirtualCCU, BackendMode

async def main():
    async with VirtualCCU(
        mode=BackendMode.OPENCCU,
        xml_rpc_port=2010,
        json_rpc_port=8080,
        username="Admin",
        password="test123",
        setup_defaults=True,
    ) as ccu:
        # Add test data
        ccu.add_program("Test Program", "A test program")
        ccu.add_system_variable("Temperature", "FLOAT", 21.5, unit="°C")
        ccu.add_room("Living Room", channel_ids=["VCU0000001:1"])

        # Keep running
        await asyncio.sleep(3600)

asyncio.run(main())
```

### Pytest Fixture

```python
import pytest
from pydevccu import VirtualCCU, BackendMode

@pytest.fixture
async def virtual_ccu():
    ccu = VirtualCCU(
        mode=BackendMode.OPENCCU,
        xml_rpc_port=12010,
        json_rpc_port=18080,
        devices=["HmIP-SWSD"],
        setup_defaults=True,
    )
    await ccu.start()
    yield ccu
    await ccu.stop()

async def test_system_variable(virtual_ccu):
    virtual_ccu.add_system_variable("Test", "BOOL", False)
    sv = virtual_ccu.state_manager.get_system_variable("Test")
    assert sv.value is False
```

---

## HTTP Endpoints

### Backup Download

```
GET /config/cp_security.cgi?sid=<session_id>
Content-Type: application/octet-stream
```

### Maintenance Operations

```
POST /config/cp_maintenance.cgi?sid=<session_id>
Content-Type: application/json

{"action": "checkUpdate"}
→ {"currentFirmware": "...", "availableFirmware": "...", "updateAvailable": false}

{"action": "triggerUpdate"}
→ {"success": true}
```

### Version Information

```
GET /VERSION
Content-Type: text/plain

VERSION=3.87.1.20250130
PRODUCT=OpenCCU
```

---

## Feature Matrix

| Feature              | HOMEGEAR | CCU  | OPENCCU |
| -------------------- | -------- | ---- | ------- |
| XML-RPC Methods      | Full     | Full | Full    |
| Device Management    | Yes      | Yes  | Yes     |
| Parameter Operations | Yes      | Yes  | Yes     |
| JSON-RPC API         | No       | Yes  | Yes     |
| Session Management   | No       | Yes  | Yes     |
| Programs             | No       | Yes  | Yes     |
| System Variables     | Limited  | Yes  | Yes     |
| Rooms/Functions      | No       | Yes  | Yes     |
| ReGa Scripts         | No       | Yes  | Yes     |
| Backup/Firmware      | No       | Yes  | Yes     |
| Device Logic         | Yes      | Yes  | Yes     |
| Persistence          | Yes      | Yes  | Yes     |
| Authentication       | No       | Yes  | Yes     |

---

## Error Handling

### JSON-RPC Errors

| Code   | Name           | Description                |
| ------ | -------------- | -------------------------- |
| -32700 | ParseError     | Invalid JSON               |
| -32600 | InvalidRequest | Invalid request structure  |
| -32601 | MethodNotFound | Method does not exist      |
| -32602 | InvalidParams  | Invalid parameters         |
| -32603 | InternalError  | Internal server error      |
| -32001 | SessionExpired | Session expired or invalid |
| -32002 | ObjectNotFound | Requested object not found |

---

## Key Capabilities Summary

1. **397 Supported Devices** - Complete device database with descriptions and paramsets
2. **Dual Server Architecture** - XML-RPC (threading) + JSON-RPC (async aiohttp)
3. **Complete CCU Simulation** - Programs, system variables, rooms, functions
4. **Pattern-Based ReGa Engine** - Supports all aiohomematic script patterns
5. **Authentication System** - Session management with expiration
6. **Thread-Safe State Management** - Callback-enabled state with RLock protection
7. **Device Logic Simulation** - Automated device behavior with configurable intervals
8. **Backup/Firmware Simulation** - Complete maintenance workflow
9. **HTTP Endpoints** - Backup download, maintenance operations, VERSION file
10. **Test-Ready** - Easy setup for testing HomeMatic integrations

---

## Dependencies

### Core

```
aiohttp>=3.9.0
```

### Optional

```
orjson>=3.11.0  # Fast JSON (not for free-threaded Python)
```

### Development

```
pytest>=8.0.0
pytest-asyncio>=0.24.0
pytest-cov>=4.0.0
ruff>=0.4.0
mypy>=1.10.0
```
