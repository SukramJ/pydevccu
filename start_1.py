from __future__ import annotations

import pydevccu

# Create server that listens on 127.0.0.1:2001
# To listen on another address initialize with ("1.2.3.4", 1234) as first argument
# Add optional list of device names to only load these devices
# Enable paramset persistence (will be saved to paramset_db.json)
# Enable automated device logic (only if module for device is available), firing events at intervals of 30 seconds
# s = pydevccu.Server(devices=['HM-Sec-WDS'], persistence=True, logic={"startupdelay": 5, "interval": 30})

s = pydevccu.Server(
    devices=["HmIP-RGBW", "HM-TC-IT-WM-W-EU", "HBW-LC-RGBWW-IN6-DR"],
    persistence=True,
    logic={"startupdelay": 5, "interval": 30},
)
# devices=['HmIP-DLD']
# Start server
s.start()
