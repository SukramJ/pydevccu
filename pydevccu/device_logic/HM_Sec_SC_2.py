"""
Logic module for HM-Sec-SC-2 (VCU0000240).
Switch between open / closed, toggle LOWBAT every 5 events.
"""

from __future__ import annotations

import logging
import random
import sys
import time

LOG = logging.getLogger(__name__)
if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)


class HM_Sec_SC_2:
    def __init__(self, rpcfunctions, startupdelay=5, interval=60):
        self.rpcfunctions = rpcfunctions
        self.name = "HM-Sec-SC-2"
        self.address = "VCU0000240:1"
        self.active = False
        self.firstrun = True
        self.startupdelay = startupdelay
        self.interval = interval
        self.lowbat = False
        self.counter = 1

    def work(self):
        if self.firstrun:
            time.sleep(random.randint(0, self.startupdelay))
        self.firstrun = False
        while self.active:
            if self.rpcfunctions.active:
                current_state = self.rpcfunctions.getValue(self.address, "STATE")
                if self.counter % 5 == 0:
                    self.lowbat = not self.lowbat
                    self.rpcfunctions._fireEvent(self.name, self.address, "LOWBAT", self.lowbat)
                self.rpcfunctions.setValue(self.address, "STATE", not current_state, force=True)
                self.counter += 1
            time.sleep(self.interval)
