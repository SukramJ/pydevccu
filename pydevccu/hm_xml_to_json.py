"""
Convert XML-files for HomeMatic and HomeMatic Wired to JSON files.
Copy XML-files from /firmware/hs485types and /firmware/rftypes into
the hm_xml-folder to be processed.
"""

from __future__ import annotations

import copy
import json
import os
import re
import xml.etree.ElementTree as ET

START_ID = 1
VCU = "VCU0000000"

PATH_XML = "hm_xml"
PATH_JSON_DEVICE_DESCRIPTIONS = "device_descriptions"
PATH_JSON_PARAMSET_DESCRIPTIONS = "paramset_descriptions"

DEV_FLAG_VISIBLE = 1
DEV_FLAG_INTERNAL = 2
DEV_FLAG_DONTDELETE = 8
DEV_FLAG_VISIBLE_STR = "visible"
DEV_FLAG_INVISIBLE_STR = "invisible"
DEV_FLAG_INTERNAL_STR = "internal"
DEV_FLAG_DONTDELETE_STR = "dontdelete"  # ?

DEV_RX_MODE_ALWAYS = 1
DEV_RX_MODE_BURST = 2
DEV_RX_MODE_CONFIG = 4
DEV_RX_MODE_WAKEUP = 8
DEV_RX_MODE_LAZY_CONFIG = 10
DEV_RX_MODE_ALWAYS_STR = "ALWAYS"
DEV_RX_MODE_BURST_STR = "BURST"
DEV_RX_MODE_CONFIG_STR = "CONFIG"
DEV_RX_MODE_WAKEUP_STR = "WAKEUP"
DEV_RX_MODE_LAZY_CONFIG_STR = "LAZY_CONFIG"

CHAN_DIRECTION_NONE = 0
CHAN_DIRECTION_SENDER = 1
CHAN_DIRECTION_RECEIVER = 2
FRAME_DIRECTION_TO_DEVICE_XML = "to_device"
FRAME_DIRECTION_FROM_DEVICE_XML = "from_device"

PARAM_FLAG_INVISIBLE = 0
PARAM_FLAG_VISIBLE = 1
PARAM_FLAG_INTERNAL = 2
PARAM_FLAG_TRANSFORM = 4
PARAM_FLAG_SERVICE = 8
PARAM_FLAG_STICKY = 10
PARAM_FLAG_INVISIBLE_STR = "invisible"
PARAM_FLAG_VISIBLE_STR = "visible"
PARAM_FLAG_INTERNAL_STR = "internal"
PARAM_FLAG_TRANSFORM_STR = "transform"
PARAM_FLAG_SERVICE_STR = "service"
PARAM_FLAG_STICKY_STR = "sticky"

PARAM_OPERATION_READ = 1
PARAM_OPERATION_READ_XML = "read"
PARAM_OPERATION_WRITE = 2
PARAM_OPERATION_WRITE_XML = "write"
PARAM_OPERATION_EVENT = 4
PARAM_OPERATION_EVENT_XML = "event"

VAL_TRUE = "true"
VAL_FALSE = "false"

DEV_DESC_DEV = {
    "UPDATABLE": 0,
    "TYPE": "",
    "CHILDREN": [],
    "FIRMWARE": "",
    "PARAMSETS": [],
    "ROAMING": 0,
    "PARENT": "",
    "FLAGS": 1,
    "INTERFACE": "",
    "RX_MODE": 0,
    "ADDRESS": "",
    "RF_ADDRESS": 0,
    "VERSION": 0,
}

DEV_DESC_CHAN = {
    "TYPE": "",
    "PARENT_TYPE": "",
    "PARAMSETS": [],
    "LINK_TARGET_ROLES": "",
    "PARENT": "",
    "FLAGS": 1,
    "AES_ACTIVE": 0,
    "DIRECTION": 0,
    "INDEX": 0,
    "VERSION": 0,
    "LINK_SOURCE_ROLES": "",
    "ADDRESS": "",
}

PARAMSET_DESC = {
    "TYPE": "",
    "OPERATIONS": 0,
    "FLAGS": 1,
    "DEFAULT": 0,
    "MAX": 0,
    "MIN": 0,
    "UNIT": "",
    "TAB_ORDER": 0,
}

PVAL_XML_FALSE = "false"
PVAL_PD_FALSE = 0
PVAL_XML_TRUE = "true"
PVAL_PD_TRUE = 1

PARAMTYPE_MAP = {
    "boolean": "BOOL",
    "integer": "INTEGER",
    "float": "FLOAT",
    "option": "ENUM",
    "action": "ACTION",
    "string": "STRING",
}

INT_MAX = 2147483647
INT_MIN = -2147483648

# Clear old data
for filename in os.listdir(PATH_JSON_DEVICE_DESCRIPTIONS):
    if filename != "HM-CC-VG-1.json":
        os.unlink(os.path.join(PATH_JSON_DEVICE_DESCRIPTIONS, filename))
for filename in os.listdir(PATH_JSON_PARAMSET_DESCRIPTIONS):
    if filename != "HM-CC-VG-1.json":
        os.unlink(os.path.join(PATH_JSON_PARAMSET_DESCRIPTIONS, filename))
nextid = len(os.listdir(PATH_JSON_DEVICE_DESCRIPTIONS)) + START_ID - 1


def logical_to_dict(node):
    data = {}
    param_type = node.get("type")
    data["UNIT"] = node.get("unit")
    if data["UNIT"]:
        if b"\xef\xbf\xbdC" in bytes(data["UNIT"], encoding="ISO-8859-1"):
            if data["UNIT"].endswith("F"):
                data["UNIT"] = "°F"
            else:
                data["UNIT"] = "°C"
    if param_type is not None and param_type != "address":
        data["TYPE"] = PARAMTYPE_MAP[param_type]
    param_default = node.get("default")
    try:
        if param_type == "boolean":
            data["MIN"] = False
            data["MAX"] = True
            if param_default == PVAL_XML_TRUE:
                data["DEFAULT"] = True
            elif param_default == PVAL_XML_FALSE:
                data["DEFAULT"] = False
        elif param_type == "float":
            if param_default is None:
                param_default = 0.0
            data["DEFAULT"] = float(param_default)
            if node.get("min"):
                data["MIN"] = float(node.get("min"))
            else:
                data["MIN"] = INT_MIN
            if node.get("max"):
                data["MAX"] = float(node.get("max"))
            else:
                data["MAX"] = INT_MAX
            if node.findall("special_value"):
                data["SPECIAL"] = []
                for s in node.findall("special_value"):
                    data["SPECIAL"] = {s.get("id"): float(s.get("value"))}
        elif param_type == "integer":
            if param_default is None:
                param_default = 0
            if param_default != 0:
                if "." in param_default:
                    param_default = float(param_default)
                elif "0x" in param_default:
                    param_default = int(param_default, 16)
            data["DEFAULT"] = int(param_default)
            v_min = node.get("min")
            if v_min:
                if "." in v_min:
                    data["MIN"] = float(v_min)
                elif "0x" in v_min:
                    data["MIN"] = int(v_min, 16)
                else:
                    data["MIN"] = int(v_min)
            else:
                data["MIN"] = INT_MIN
            v_max = node.get("max")
            if v_max:
                if "." in v_max:
                    data["MAX"] = float(v_max)
                elif "0x" in v_max:
                    data["MAX"] = int(v_max, 16)
                else:
                    data["MAX"] = int(v_max)
            else:
                data["MAX"] = INT_MAX
            if node.findall("special_value"):
                data["SPECIAL"] = []
                for s in node.findall("special_value"):
                    if s.get("value"):
                        if "." in s.get("value"):
                            data["SPECIAL"] = {s.get("id"): float(s.get("value"))}
                        else:
                            data["SPECIAL"] = {s.get("id"): int(s.get("value"))}
        elif param_type == "string":
            data["DEFAULT"] = param_default
        elif param_type == "action":
            data["DEFAULT"] = False
        elif param_type == "option":
            data["VALUE_LIST"] = []
            data["MIN"] = 0
            counter = 0
            for o in node.findall("option"):
                data["VALUE_LIST"].append(o.get("id"))
                if o.get("default"):
                    data["DEFAULT"] = counter
                data["MAX"] = counter
                counter += 1
    except Exception as err:
        print(parent_map[node].get("id"))
        print(err)
        print(param_type)
        print(param_default)
    return data


def paramset_to_dict(node):
    paramset = {}
    direction = CHAN_DIRECTION_NONE
    if node:
        for parameter in node.findall("parameter"):
            param_id = parameter.get("id")
            paramset[param_id] = copy.deepcopy(PARAMSET_DESC)
            logical = parameter.find("logical")
            if logical is None:
                continue
            psdata = logical_to_dict(logical)
            for k, v in psdata.items():
                paramset[param_id][k] = v
            if parameter.get("control") is not None:
                paramset[param_id]["CONTROL"] = parameter.get("control")
            if parameter.get("ui_flags") is not None:
                flags = parameter.get("ui_flags").split(",")
                if flags:
                    if PARAM_FLAG_INVISIBLE_STR in flags:
                        paramset[param_id]["FLAGS"] = paramset[param_id]["FLAGS"] ^ PARAM_FLAG_VISIBLE
                    if PARAM_FLAG_INTERNAL_STR in flags:
                        paramset[param_id]["FLAGS"] = paramset[param_id]["FLAGS"] | PARAM_FLAG_INTERNAL
                    if PARAM_FLAG_TRANSFORM_STR in flags:
                        paramset[param_id]["FLAGS"] = paramset[param_id]["FLAGS"] | PARAM_FLAG_TRANSFORM
                    if PARAM_FLAG_SERVICE_STR in flags:
                        paramset[param_id]["FLAGS"] = paramset[param_id]["FLAGS"] | PARAM_FLAG_SERVICE
                    if PARAM_FLAG_STICKY_STR in flags:
                        paramset[param_id]["FLAGS"] = paramset[param_id]["FLAGS"] | PARAM_FLAG_STICKY
            if parameter.get("operations") is not None:
                operations = [o.strip() for o in parameter.get("operations").split(",")]
                if PARAM_OPERATION_READ_XML in operations:
                    paramset[param_id]["OPERATIONS"] = paramset[param_id]["OPERATIONS"] | PARAM_OPERATION_READ
                if PARAM_OPERATION_WRITE_XML in operations:
                    paramset[param_id]["OPERATIONS"] = paramset[param_id]["OPERATIONS"] | PARAM_OPERATION_WRITE
                if PARAM_OPERATION_EVENT_XML in operations:
                    paramset[param_id]["OPERATIONS"] = paramset[param_id]["OPERATIONS"] | PARAM_OPERATION_EVENT
    return paramset, direction


def get_rx_mode(node, default_rx=0):
    rx = default_rx
    modes = node.get("rx_modes").split(",")
    if DEV_RX_MODE_ALWAYS_STR in modes:
        rx = rx | DEV_RX_MODE_ALWAYS
    if DEV_RX_MODE_BURST_STR in modes:
        rx = rx | DEV_RX_MODE_BURST
    if DEV_RX_MODE_CONFIG_STR in modes:
        rx = rx | DEV_RX_MODE_CONFIG
    if DEV_RX_MODE_WAKEUP_STR in modes:
        rx = rx | DEV_RX_MODE_WAKEUP
    if DEV_RX_MODE_LAZY_CONFIG_STR in modes:
        rx = rx | DEV_RX_MODE_LAZY_CONFIG
    return rx


def guess_channels(devname, nicename):
    try:
        return int(re.search(r"[0-9]+\-channel", nicename).group(0).split("-")[0]), False
    except:
        pass
    try:
        return int(re.search(r"[0-9]+\ channel", nicename).group(0).split(" ")[0]), False
    except:
        pass
    try:
        return int(re.search(r"[0-9]+\ switches", nicename).group(0).split(" ")[0]), False
    except:
        pass
    try:
        return int(re.search(r"[0-9]+\ button", nicename).group(0).split(" ")[0]), False
    except:
        pass
    try:
        return int(re.search(r"Button\ [0-9]+", nicename).group(0).split(" ")[1]), False
    except:
        pass
    try:
        return int(re.search(r"Sw[0-9]+\-", devname).group(0)[:-1].split("Sw")[1]), False
    except:
        pass
    try:
        return int(re.search(r"RC\-[0-9]+", devname).group(0).split("-")[1]), False
    except:
        pass
    try:
        return int(re.search(r"PB\-[0-9]+", devname).group(0).split("-")[1]), False
    except:
        pass
    try:
        return int(re.search(r"RC-Sec[0-9]+", devname).group(0).split("RC-Sec")[1]), False
    except:
        pass
    try:
        return int(re.search(r"RC-Key[0-9]+", devname).group(0).split("RC-Key")[1]), False
    except:
        pass
    if "Dim1" in devname:
        return 1, False
    if "Dim2" in devname:
        return 2, False
    if "LED16" in devname:
        return 16, False
    if "EM-8" in devname:
        return 8, False
    if "Re-8" in devname:
        return 8, False
    if devname in ["HM-PBI-4-FM", "ZEL STG RM FST UP4", "263 145", "BRC-H"]:
        return 4, False
    if "Rotary Handle Sensor" in nicename or devname == "HM-SCI-3-FM":
        return 3, False
    if (
        nicename.endswith("Shutter Contact")
        or "HM-Sen-MD" in devname
        or "HM-Sec-MD" in devname
        or "HM-Sec-WDS" in devname
    ):
        return 1, False
    if devname in [
        "HM-Sec-TiS",
        "ZEL STG RM FFK",
        "263 162",
        "HM-Sec-SCo",
        "HM-MD",
        "HM-RC-SB-X",
        "HM-Sen-DB-PCB",
        "HM-Sen-EP",
        "HM-Sec-SFA-SM",
    ]:
        return 1, False
    if "SENSOR_FOR_CARBON_DIOXIDE" in nicename:
        return 1, False
    print("Could not guess channels for: %s (%s)" % (devname, nicename))
    return 1, True


files = os.listdir(PATH_XML)
for filename in files:
    if filename == ".gitkeep":
        continue
    f = os.path.join(PATH_XML, filename)
    tree = ET.parse(f)
    root = tree.getroot()
    parent_map = dict((c, p) for p in tree.getiterator() for c in p)
    supported_types = root.find("supported_types")
    channels = root.find("channels")
    if channels is None:
        continue
    frames = root.find("frames")
    paramset_defs = {}
    if root.find("paramset_defs"):
        for paramset_def in root.find("paramset_defs").getchildren():
            paramset_defs[paramset_def.get("id")] = paramset_def
    for t in supported_types.findall("type"):
        nicename = t.get("name")
        devname = t.get("id")
        if devname == "CENTRAL":
            continue
        if "/" in devname:
            print("Skipping: %s (%s)" % (devname, filename))
            continue
        dev_desc = []
        paramsets = {}
        d_dict = copy.deepcopy(DEV_DESC_DEV)
        d_dict["TYPE"] = devname
        address = "VCU" + format(nextid, "07d")
        d_dict["ADDRESS"] = address
        d_dict["INTERFACE"] = VCU
        if root.findall("paramset") is not None:
            paramsets[address] = {}
        for root_paramset in root.findall("paramset"):
            p_type = root_paramset.get("type")
            d_dict["PARAMSETS"].append(p_type)
            paramsets[d_dict["ADDRESS"]][p_type], _ = paramset_to_dict(root_paramset)
        if root.get("ui_flags") is not None:
            if DEV_FLAG_DONTDELETE_STR in root.get("ui_flags"):
                d_dict["FLAGS"] = d_dict["FLAGS"] | DEV_FLAG_DONTDELETE
        if root.get("rx_modes") is not None:
            d_dict["RX_MODE"] = get_rx_mode(root, d_dict["RX_MODE"])
        if root.get("version") is not None:
            d_dict["VERSION"] = int(root.get("version"))
        if t.get("updatable") == VAL_TRUE:
            d_dict["UPDATABLE"] = 1
        dev_desc.append(d_dict)
        for channel in channels:
            if channel.get("hidden") is not None:
                continue
            index = int(channel.get("index"))
            count = 1
            count_unknown = False
            if channel.get("count") is not None:
                count = int(channel.get("count"))
            if channel.get("count_from_sysinfo") is not None:
                count, count_unknown = guess_channels(devname, nicename)
            if count_unknown:
                paramsets["unknown"] = True
            for i in range(count):
                direction = CHAN_DIRECTION_NONE
                s_dict = copy.deepcopy(DEV_DESC_CHAN)
                s_dict["TYPE"] = channel.get("type")
                s_dict["PARENT"] = address
                s_dict["PARENT_TYPE"] = devname
                s_dict["INDEX"] = index + i
                s_dict["ADDRESS"] = "%s:%i" % (address, index + i)
                dev_desc[0]["CHILDREN"].append(s_dict["ADDRESS"])
                paramsets[s_dict["ADDRESS"]] = {}
                flags = channel.get("ui_flags")
                if flags is not None:
                    if DEV_FLAG_INVISIBLE_STR in flags:
                        s_dict["FLAGS"] = s_dict["FLAGS"] ^ DEV_FLAG_VISIBLE
                    if DEV_FLAG_INTERNAL_STR in flags:
                        s_dict["FLAGS"] = s_dict["FLAGS"] | DEV_FLAG_INTERNAL
                    if DEV_FLAG_DONTDELETE_STR in flags:
                        s_dict["FLAGS"] = s_dict["FLAGS"] | DEV_FLAG_DONTDELETE
                if channel.get("direction"):
                    if channel.get("type") == "sender":
                        s_dict["DIRECTION"] = CHAN_DIRECTION_SENDER
                    else:
                        s_dict["DIRECTION"] = CHAN_DIRECTION_RECEIVER
                for p in channel.findall("paramset"):
                    ptype = p.get("type")
                    s_dict["PARAMSETS"].append(ptype)
                    if p.findall("subset"):
                        for ps in p.findall("subset"):
                            p = paramset_defs.get(ps.get("ref"))
                            if p is None:
                                continue
                    paramsets[s_dict["ADDRESS"]][ptype], direction = paramset_to_dict(p)
                    if not s_dict["DIRECTION"]:
                        s_dict["DIRECTION"] = direction
                link_roles = channel.find("link_roles")
                if link_roles is not None:
                    lsr = []
                    ltr = []
                    for t in link_roles.findall("target"):
                        ltr.append(t.get("name"))
                    s_dict["LINK_TARGET_ROLES"] = " ".join(ltr)
                    for s in link_roles.findall("source"):
                        lsr.append(s.get("name"))
                    s_dict["LINK_SOURCE_ROLES"] = " ".join(lsr)
                if s_dict["LINK_TARGET_ROLES"]:
                    s_dict["DIRECTION"] = CHAN_DIRECTION_RECEIVER
                if s_dict["LINK_SOURCE_ROLES"]:
                    s_dict["DIRECTION"] = CHAN_DIRECTION_SENDER
                if s_dict["LINK_TARGET_ROLES"] and s_dict["LINK_SOURCE_ROLES"]:
                    s_dict["DIRECTION"] = CHAN_DIRECTION_NONE
                dev_desc.append(s_dict)
        dd_filename = "%s.json" % devname
        dd_filename = dd_filename.replace(" ", "_")
        dev_desc_filename = os.path.join(PATH_JSON_DEVICE_DESCRIPTIONS, dd_filename)
        with open(dev_desc_filename, "w", encoding="utf8") as fptr:
            json.dump(dev_desc, fptr, indent=0)

        pd_filename = "%s.json" % devname
        pd_filename = pd_filename.replace(" ", "_")
        paramsets_filename = os.path.join(PATH_JSON_PARAMSET_DESCRIPTIONS, pd_filename)
        with open(paramsets_filename, "w", encoding="utf8") as fptr:
            json.dump(paramsets, fptr, indent=0)
        nextid += 1
