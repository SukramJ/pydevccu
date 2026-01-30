# pydevccu

Virtual HomeMatic CCU XML-RPC and JSON-RPC Server with fake devices for development and testing.

## Features

- **XML-RPC Server**: Full HomeMatic XML-RPC API for device operations
- **JSON-RPC Server**: CCU/OpenCCU compatible JSON-RPC API
- **VirtualCCU**: Complete CCU simulation with programs, system variables, rooms, and functions
- **ReGa Script Engine**: Pattern-matching based script execution for aiohomematic compatibility
- **Session Management**: CCU-compatible authentication
- **397 Device Types**: HomeMatic Wired, Wireless, and IP devices

## Installation

```bash
pip install pydevccu
```

For faster JSON serialization (not available on free-threaded Python):

```bash
pip install pydevccu[fast]
```

## Quick Start

### Basic Usage (XML-RPC only, Homegear mode)

```python
import pydevccu

# Create server that listens on 127.0.0.1:2001
s = pydevccu.Server(devices=['HM-Sec-WDS', 'HmIP-SWSD'])
s.start()

# Get device description
s.getDeviceDescription('VCU0000348')

# Get/set values
s.getValue('VCU0000348:1', 'STATE')
s.setValue('VCU0000348:1', 'STATE', 2, force=True)

# Stop server
s.stop()
```

### Full VirtualCCU (OpenCCU mode with JSON-RPC)

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
        setup_defaults=True,  # Populate with test data
    ) as ccu:
        # Add custom state
        ccu.add_program("My Program", "A test program")
        ccu.add_system_variable("Presence", "BOOL", True)
        ccu.add_room("Living Room")

        # Run your tests...
        await asyncio.sleep(60)

asyncio.run(main())
```

---

## Ausführliche Dokumentation

### Backend-Modi

pydevccu unterstützt drei Backend-Modi, die unterschiedliche Funktionen bereitstellen:

| Modus      | XML-RPC | JSON-RPC | Auth | ReGa Scripts | Beschreibung                     |
| ---------- | ------- | -------- | ---- | ------------ | -------------------------------- |
| `HOMEGEAR` | ✅      | ❌       | ❌   | ❌           | Nur XML-RPC, minimale Simulation |
| `CCU`      | ✅      | ✅       | ✅   | ✅           | CCU2/CCU3 Simulation             |
| `OPENCCU`  | ✅      | ✅       | ✅   | ✅           | OpenCCU/RaspberryMatic           |

### VirtualCCU - Der Haupteinstiegspunkt

Die `VirtualCCU` Klasse ist der zentrale Orchestrator für die komplette CCU-Simulation:

```python
from pydevccu import VirtualCCU, BackendMode

# Konfiguration
ccu = VirtualCCU(
    mode=BackendMode.OPENCCU,      # Backend-Modus
    host="127.0.0.1",              # Bind-Adresse
    xml_rpc_port=2010,             # Port für XML-RPC Server
    json_rpc_port=8080,            # Port für JSON-RPC Server
    username="Admin",              # Benutzername für Authentifizierung
    password="secret",             # Passwort für Authentifizierung
    auth_enabled=True,             # Authentifizierung aktivieren
    devices=["HmIP-SWSD"],         # Liste der zu ladenden Geräte
    setup_defaults=True,           # Testdaten vorausfüllen
    serial="0123456789",           # Seriennummer der CCU
)
```

#### Verwendung als Context Manager (empfohlen)

```python
async def main():
    async with VirtualCCU(mode=BackendMode.OPENCCU) as ccu:
        # Server ist gestartet
        print(f"XML-RPC: http://{ccu.host}:{ccu.xml_rpc_port}")
        print(f"JSON-RPC: http://{ccu.host}:{ccu.json_rpc_port}")

        # Ihr Test-Code hier...
        await asyncio.sleep(60)
    # Server wird automatisch gestoppt
```

#### Manuelle Steuerung

```python
ccu = VirtualCCU(mode=BackendMode.OPENCCU)
await ccu.start()

# ... Operationen ...

await ccu.stop()
```

### StateManager - Zustandsverwaltung

Der `StateManager` verwaltet den gesamten Zustand der virtuellen CCU:

```python
from pydevccu import StateManager
from pydevccu.const import BackendMode

# StateManager erstellen
state = StateManager(mode=BackendMode.OPENCCU, serial="0123456789")

# Programme verwalten
state.add_program(
    name="Anwesenheit",
    description="Simuliert Anwesenheit",
    active=True
)
programs = state.get_programs()
state.execute_program(program_id=1)
state.set_program_active(program_id=1, active=False)

# Systemvariablen verwalten
state.add_system_variable(
    name="Urlaubsmodus",
    var_type="BOOL",
    value=False,
    description="Urlaubsmodus aktiv"
)
state.add_system_variable(
    name="Temperatur",
    var_type="FLOAT",
    value=21.5,
    min_value=10.0,
    max_value=30.0,
    unit="°C"
)
state.add_system_variable(
    name="Betriebsmodus",
    var_type="ENUM",
    value=0,
    value_list=["Auto", "Manuell", "Urlaub"]
)

# Wert abrufen/setzen
sysvar = state.get_system_variable_by_name("Urlaubsmodus")
state.set_system_variable(sysvar_id=1, value=True)

# Räume und Funktionen
state.add_room(name="Wohnzimmer", description="", channel_ids=["ABC123:1"])
state.add_function(name="Licht", description="Alle Lichter")

# Service-Nachrichten
state.add_service_message(
    address="VCU0000001:0",
    message_id="CONFIG_PENDING",
    message="Konfiguration ausstehend"
)
messages = state.get_service_messages()
state.clear_service_message(address="VCU0000001:0", message_id="CONFIG_PENDING")

# Gerätewerte
state.set_device_value("VCU0000001:1", "STATE", True)
value = state.get_device_value("VCU0000001:1", "STATE")

# Gerätenamen
state.set_device_name("VCU0000001", "Rauchmelder Küche")
name = state.get_device_name("VCU0000001")

# Backend-Info
info = state.get_backend_info()
# Returns: {"version": "3.75.7", "serial": "0123456789", ...}
```

#### Callbacks für Änderungen

```python
def on_sysvar_change(sysvar_id: int, name: str, value: Any) -> None:
    print(f"Systemvariable {name} geändert: {value}")

def on_program_executed(program_id: int, name: str) -> None:
    print(f"Programm {name} ausgeführt")

state.register_sysvar_callback(on_sysvar_change)
state.register_program_callback(on_program_executed)
```

### SessionManager - Authentifizierung

Der `SessionManager` verwaltet die JSON-RPC Sitzungen:

```python
from pydevccu import SessionManager

session_mgr = SessionManager(
    username="Admin",
    password="secret",
    auth_enabled=True,
    session_timeout=1800  # 30 Minuten
)

# Login
session_id = session_mgr.login("Admin", "secret")
# Returns: "abc123..." oder None bei Fehler

# Session validieren
is_valid = session_mgr.validate(session_id)

# Session erneuern
new_session_id = session_mgr.renew(session_id)

# Logout
success = session_mgr.logout(session_id)

# Wenn auth_enabled=False, ist validate() immer True
```

### ReGa Script Engine

Die ReGa-Engine führt aiohomematic-kompatible Scripts aus:

```python
from pydevccu.rega import RegaEngine

# Engine erstellen (benötigt StateManager und optional RPC-Funktionen)
rega = RegaEngine(
    state_manager=state,
    rpc_functions=rpc  # Optional, für Geräteoperationen
)

# Script ausführen
result = rega.execute(script_code)
# result.output = Script-Ausgabe
# result.success = True/False
```

#### Unterstützte Script-Patterns

Die Engine unterstützt folgende Patterns für aiohomematic:

```tcl
# Backend-Version abfragen
Write(system.GetVar(0).Version());

# Seriennummer abfragen
Write(system.GetVar(0).SerialNumber());

# Programme abrufen
string sPrgID;
foreach(sPrgID, dom.GetObject(ID_PROGRAMS).EnumUsedIDs()) { ... }

# Systemvariablen abrufen
string sSysVarId;
foreach(sSysVarId, dom.GetObject(ID_SYSTEM_VARIABLES).EnumUsedIDs()) { ... }

# Systemvariable setzen
dom.GetObject("Urlaubsmodus").State(true);
dom.GetObject(123).State(21.5);

# Programm aktivieren/deaktivieren
dom.GetObject("Mein Programm").Active(true);

# Räume abrufen
string sRoomId;
foreach(sRoomId, dom.GetObject(ID_ROOMS).EnumUsedIDs()) { ... }

# Funktionen/Gewerke abrufen
string sFuncId;
foreach(sFuncId, dom.GetObject(ID_FUNCTIONS).EnumUsedIDs()) { ... }

# Service-Nachrichten
string sSvcMsgId;
foreach(sSvcMsgId, dom.GetObject(ID_SERVICES).EnumUsedIDs()) { ... }

# Firmware-Update starten
TRIGGER_UPDATE();
```

### JSON-RPC API

Die JSON-RPC API ist unter `/api/homematic.cgi` erreichbar:

```python
import aiohttp
import json

async def call_json_rpc(method: str, params: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        async with session.post(
            "http://localhost:8080/api/homematic.cgi",
            json=payload
        ) as response:
            return await response.json()

# Login
result = await call_json_rpc("Session.login", {
    "username": "Admin",
    "password": "secret"
})
session_id = result["result"]["_session_id_"]

# Programme abrufen
result = await call_json_rpc("Program.getAll", {
    "_session_id_": session_id
})

# Systemvariable setzen
result = await call_json_rpc("SysVar.setBool", {
    "_session_id_": session_id,
    "name": "Urlaubsmodus",
    "value": True
})

# ReGa-Script ausführen
result = await call_json_rpc("ReGa.runScript", {
    "_session_id_": session_id,
    "script": 'Write(system.GetVar(0).Version());'
})

# Logout
await call_json_rpc("Session.logout", {"_session_id_": session_id})
```

### Verfügbare JSON-RPC Methoden

| Namespace  | Methode                 | Beschreibung                     |
| ---------- | ----------------------- | -------------------------------- |
| Session    | login                   | Anmeldung                        |
| Session    | logout                  | Abmeldung                        |
| Session    | renew                   | Session erneuern                 |
| CCU        | getAuthEnabled          | Auth-Status abfragen             |
| CCU        | getHttpsRedirectEnabled | HTTPS-Redirect Status            |
| Interface  | listInterfaces          | Verfügbare Schnittstellen        |
| Interface  | listDevices             | Alle Geräte auflisten            |
| Interface  | getDeviceDescription    | Gerätebeschreibung               |
| Interface  | getValue                | Parameterwert abrufen            |
| Interface  | setValue                | Parameterwert setzen             |
| Interface  | getParamset             | Parameterset abrufen             |
| Interface  | putParamset             | Parameterset setzen              |
| Interface  | getParamsetDescription  | Parameterset-Beschreibung        |
| Interface  | isPresent               | Gerät erreichbar?                |
| Interface  | getInstallMode          | Anlernmodus Status               |
| Interface  | setInstallMode          | Anlernmodus setzen               |
| Interface  | ping                    | Ping                             |
| Device     | listAllDetail           | Alle Geräte mit Details          |
| Device     | get                     | Gerät abrufen                    |
| Device     | setName                 | Gerätename setzen                |
| Channel    | setName                 | Kanalname setzen                 |
| Program    | getAll                  | Alle Programme                   |
| Program    | execute                 | Programm ausführen               |
| Program    | setActive               | Programm aktivieren/deaktivieren |
| SysVar     | getAll                  | Alle Systemvariablen             |
| SysVar     | getValueByName          | Wert nach Name                   |
| SysVar     | setBool                 | Boolean setzen                   |
| SysVar     | setFloat                | Float setzen                     |
| SysVar     | setString               | String setzen                    |
| SysVar     | deleteSysVarByName      | Variable löschen                 |
| Room       | getAll                  | Alle Räume                       |
| Subsection | getAll                  | Alle Gewerke/Funktionen          |
| ReGa       | runScript               | ReGa-Script ausführen            |

### HTTP Endpoints

| Endpoint                     | Methode | Beschreibung         |
| ---------------------------- | ------- | -------------------- |
| `/api/homematic.cgi`         | POST    | JSON-RPC Endpoint    |
| `/config/cp_security.cgi`    | GET     | Backup herunterladen |
| `/config/cp_maintenance.cgi` | POST    | Firmware-Wartung     |
| `/VERSION`                   | GET     | Backend-Version      |

### Testing mit pytest

```python
import pytest
from pydevccu import VirtualCCU, BackendMode

@pytest.fixture
async def virtual_ccu():
    """Fixture für VirtualCCU."""
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

async def test_programs(virtual_ccu):
    """Test: Programme sind verfügbar."""
    programs = virtual_ccu.state_manager.get_programs()
    assert len(programs) >= 1

async def test_sysvars(virtual_ccu):
    """Test: Systemvariablen können gesetzt werden."""
    virtual_ccu.add_system_variable("Test", "BOOL", False)
    sv = virtual_ccu.state_manager.get_system_variable_by_name("Test")
    assert sv is not None
    assert sv.value is False

async def test_rooms(virtual_ccu):
    """Test: Räume können hinzugefügt werden."""
    virtual_ccu.add_room("Testroom")
    rooms = virtual_ccu.state_manager.get_rooms()
    assert any(r.name == "Testroom" for r in rooms)
```

### Device Logic

Automatische Gerätesimulation für bestimmte Gerätetypen:

```python
s = pydevccu.Server(
    devices=['HM-Sec-SC-2'],
    logic={"startupdelay": 5, "interval": 30}
)
```

## XML-RPC Methods

- `setValue(address, value_key, value, force=False)`
- `getValue(address, value_key)`
- `getDeviceDescription(address)`
- `getParamsetDescription(address, paramset_key)`
- `getParamset(address, paramset_key)`
- `putParamset(address, paramset_key, paramset, force=False)`
- `listDevices()`
- `init(url, interface_id)`
- `getServiceMessages()`
- `supportedDevices()` (proprietary)
- `addDevices(devices)` (proprietary)
- `removeDevices(devices)` (proprietary)

## Documentation

For more information about the XML-RPC methods refer to the official [HomeMatic XML-RPC API](https://www.eq-3.de/Downloads/eq3/download%20bereich/hm_web_ui_doku/HM_XmlRpc_API.pdf) (German).

## License

MIT
