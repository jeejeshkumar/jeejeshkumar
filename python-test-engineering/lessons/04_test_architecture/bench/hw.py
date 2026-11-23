"""TEMPLATE: assembling a real hardware-in-the-loop rig.

This shows WHERE real hardware plugs into the architecture. It cannot run
here (no instruments), so `--target hw` is skipped unless you complete it.

Typical rig configuration file (rig.toml):

    name = "HIL bench 3"
    pressure_controller = "TCPIP0::192.168.1.20::5025::SOCKET"
    power_supply        = "TCPIP0::192.168.1.21::INSTR"
    arinc_card          = 0
    arinc_rx_channel    = 1
"""

from __future__ import annotations

import time
import tomllib
from pathlib import Path

from .drivers import ScpiPowerSupply, ScpiPressureController
from .interfaces import RigError


class WallClock:
    """Real time, for real hardware."""

    def __init__(self) -> None:
        self._t0 = time.monotonic()  # monotonic: never jumps when NTP adjusts

    def now(self) -> float:
        return time.monotonic() - self._t0

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class VisaTransport:
    """Transport over VISA (pip install pyvisa pyvisa-py)."""

    def __init__(self, resource: str, timeout_ms: int = 2000) -> None:
        import pyvisa  # imported here so the course runs without pyvisa installed

        self._inst = pyvisa.ResourceManager().open_resource(resource)
        self._inst.timeout = timeout_ms
        self._inst.read_termination = self._inst.write_termination = "\n"

    def write(self, command: str) -> None:
        self._inst.write(command)

    def query(self, command: str) -> str:
        return self._inst.query(command)

    def close(self) -> None:
        self._inst.close()


class HwRig:
    capabilities = frozenset()  # no fault-insertion unit on this bench

    def __init__(self, config: dict) -> None:
        self.name = config["name"]
        self.clock = WallClock()
        self.pressure = ScpiPressureController(VisaTransport(config["pressure_controller"]))
        self.power = ScpiPowerSupply(VisaTransport(config["power_supply"]))
        self.faults = None
        # The ARINC 429 receiver is normally a PCIe/USB card with a vendor
        # SDK (often a C library wrapped with ctypes). Wrap it in a class
        # that satisfies the BusMonitor protocol and assign it here.
        raise NotImplementedError("wrap your ARINC 429 card's SDK as a BusMonitor")

    def close(self) -> None:
        self.power.set_output(False)  # ALWAYS leave the unit unpowered
        self.pressure.set_pressure_hpa(1013.25)  # ... and at ambient pressure
        self.pressure.close()
        self.power.close()


def build_hw_rig(config_path: str | None) -> HwRig:
    if not config_path:
        raise RigError("--target hw needs --rig-config path/to/rig.toml")
    with Path(config_path).open("rb") as f:
        return HwRig(tomllib.load(f))
