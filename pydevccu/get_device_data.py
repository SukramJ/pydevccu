#!/usr/bin/python3
"""
Script to fetch device data for given HomeMatic device ID from CCU.
The two resulting files will be stored in the folders:
- device_descriptions
- paramset_descriptions

Post these files at https://gist.github.com/ to assist device implementation
for hahomematic (https://github.com/sukramj/hahomematic) and / or create
a pull request at https://github.com/sukramj/pydevccu to increase
device coverage if data for your device is not yet available in the repository.

Set CCU_IP to the IP address of your CCU.
Set DEVICE_ID to the ID of the device you want to get the data for.
If required, set CCU_PORT to the port where the XML-RPC API is reachable.

TLS/SSL and authentication are NOT supported!

Python 3 is required to execute this script.
"""

from __future__ import annotations

import json
import os
import random
from xmlrpc.client import ServerProxy

### Configuration globals ###
CCU_IP = "192.168.1.23"
CCU_PORT = 2010
DEVICE_ID = "aabbccdd112233"
#############################

DIR_DEVICE_DESCRIPTIONS = "device_descriptions"
DIR_PARAMSET_DESCRIPTIONS = "paramset_descriptions"
DEVICE_CACHE = "device_cache.json"
RANDOM_ID = "VCU%i" % random.randint(1000000, 9999999)
PROXY = ServerProxy("http://%s:%i" % (CCU_IP, CCU_PORT))

if not os.path.exists(DIR_DEVICE_DESCRIPTIONS):
    os.makedirs(DIR_DEVICE_DESCRIPTIONS)

if not os.path.exists(DIR_PARAMSET_DESCRIPTIONS):
    os.makedirs(DIR_PARAMSET_DESCRIPTIONS)

if not os.path.exists(DEVICE_CACHE):
    print("Getting devices from CCU")
    DEVICES = PROXY.listDevices()
    with open(DEVICE_CACHE, "w") as fptr:
        json.dump(DEVICES, fptr)

with open(DEVICE_CACHE) as fptr:
    DEVICES = json.load(fptr)


def anonymize_address(address):
    address_parts = address.split(":")
    address_parts[0] = RANDOM_ID
    return ":".join(address_parts)


DEVICE_TYPE = None
DEVICE_DESCRIPTION = []
PARAMSET_DESCRIPTION = {}

for device in DEVICES:
    if DEVICE_ID in device.get("ADDRESS"):
        # Get device description
        address = device["ADDRESS"]
        device["ADDRESS"] = anonymize_address(address)
        if device.get("PARENT"):
            device["PARENT"] = device["ADDRESS"].split(":")[0]
        elif device.get("CHILDREN"):
            device["CHILDREN"] = [anonymize_address(a) for a in device["CHILDREN"]]
            DEVICE_TYPE = device.get("TYPE")
        DEVICE_DESCRIPTION.append(device)

        # Get paramset description
        PARAMSET_DESCRIPTION[device["ADDRESS"]] = {}
        for paramset in device.get("PARAMSETS", []):
            PARAMSET_DESCRIPTION[device["ADDRESS"]][paramset] = {}
            try:
                PARAMSET_DESCRIPTION[device["ADDRESS"]][paramset] = PROXY.getParamsetDescription(address, paramset)
            except Exception as err:
                print(err)

print("Saving device of type %s to:" % DEVICE_TYPE)
with open(os.path.join(DIR_DEVICE_DESCRIPTIONS, "%s.json" % DEVICE_TYPE), "w") as fptr:
    json.dump(DEVICE_DESCRIPTION, fptr, indent=0)
    print(os.path.abspath(fptr.name))
with open(os.path.join(DIR_PARAMSET_DESCRIPTIONS, "%s.json" % DEVICE_TYPE), "w") as fptr:
    json.dump(PARAMSET_DESCRIPTION, fptr, indent=0)
    print(os.path.abspath(fptr.name))
