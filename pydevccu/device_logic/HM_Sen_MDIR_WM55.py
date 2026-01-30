"""
Logic module for HM-Sen-MDIR-WM55 (VCU0000274).
Switch between motion, toggle LOWBAT every 5 events,
random brightness from 60 to 90, press on channel 1.
"""

from __future__ import annotations

import logging
import random
import sys
import time

LOG = logging.getLogger(__name__)
if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)


class HM_Sen_MDIR_WM55:
    def __init__(self, rpcfunctions, startupdelay=5, interval=60):
        self.rpcfunctions = rpcfunctions
        self.name = "HM-Sen-MDIR-WM55"
        self.address = "VCU0000274"
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
                current_state = self.rpcfunctions.getValue("%s:3" % self.address, "MOTION")
                if self.counter % 5 == 0:
                    self.lowbat = not self.lowbat
                    self.rpcfunctions._fireEvent(self.name, "%s:0" % self.address, "LOWBAT", self.lowbat)
                self.rpcfunctions.setValue("%s:3" % self.address, "MOTION", not current_state, force=True)
                self.rpcfunctions.setValue("%s:3" % self.address, "BRIGHTNESS", random.randint(60, 90), force=True)
                self.rpcfunctions._fireEvent(self.name, "%s:1" % self.address, "PRESS_SHORT", True)
                self.counter += 1
            time.sleep(self.interval)
