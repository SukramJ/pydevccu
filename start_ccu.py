from __future__ import annotations

import asyncio

from pydevccu import BackendMode, VirtualCCU


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
        await asyncio.sleep(600)


asyncio.run(main())
