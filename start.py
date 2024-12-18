import pydevccu
# Create server that listens on 127.0.0.1:2001
# To listen on another address initialize with ("1.2.3.4", 1234) as first argument
# Add optional list of device names to only load these devices
# Enable paramset persistance (will be saved to paramset_db.json)
# Enable automated device logic (only if module for device is available), firing events at intervals of 30 seconds
#s = pydevccu.Server(devices=['HM-Sec-WDS'], persistance=True, logic={"startupdelay": 5, "interval": 30})

s = pydevccu.Server(persistance=True, logic={"startupdelay": 5, "interval": 30})
# devices=['HmIP-DLD']
# Start server
s.start()

