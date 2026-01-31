"""
Logic module for HM-Sen-MDIR-WM55 (VCU0000274).

Switch between motion, toggle LOWBAT every 5 events,
random brightness from 60 to 90, press on channel 1.
"""

# ruff: noqa: N999, N801, S311  # Module/class names match HomeMatic device naming

from __future__ import annotations

import logging
import random
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydevccu.ccu import RPCFunctions

LOG = logging.getLogger(__name__)
if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)


class HM_Sen_MDIR_WM55:
    """Simulate HM-Sen-MDIR-WM55 motion detector device behavior."""

    def __init__(
        self,
        rpcfunctions: RPCFunctions,
        startupdelay: int = 5,
        interval: int = 60,
    ) -> None:
        self.rpcfunctions = rpcfunctions
        self.name = "HM-Sen-MDIR-WM55"
        self.address = "VCU0000274"
        self.active = False
        self.firstrun = True
        self.startupdelay = startupdelay
        self.interval = interval
        self.lowbat = False
        self.counter = 1

    def work(self) -> None:
        """Run the device simulation loop."""
        if self.firstrun:
            time.sleep(random.randint(0, self.startupdelay))
        self.firstrun = False
        while self.active:
            if self.rpcfunctions.active:
                current_state = self.rpcfunctions.getValue(f"{self.address}:3", "MOTION")
                if self.counter % 5 == 0:
                    self.lowbat = not self.lowbat
                    self.rpcfunctions._fire_event(self.name, f"{self.address}:0", "LOWBAT", self.lowbat)
                self.rpcfunctions.setValue(f"{self.address}:3", "MOTION", not current_state, force=True)
                self.rpcfunctions.setValue(f"{self.address}:3", "BRIGHTNESS", random.randint(60, 90), force=True)
                self.rpcfunctions._fire_event(self.name, f"{self.address}:1", "PRESS_SHORT", True)
                self.counter += 1
            time.sleep(self.interval)
