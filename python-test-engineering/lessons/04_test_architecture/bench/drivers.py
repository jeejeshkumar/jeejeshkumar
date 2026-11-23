"""Instrument drivers for a real hardware-in-the-loop (HIL) rig.

Most lab instruments (pressure controllers, power supplies, DMMs) speak SCPI
- text commands like "MEAS:CURR?" - over Ethernet, USB or GPIB. A driver
turns those strings into a typed Python API that satisfies our interfaces.

The driver does NOT open the connection itself: it is given a `Transport`.
That one decision makes drivers unit-testable without hardware - the tests
in test_instrument_drivers.py pass a FakeTransport that records commands.

NOTE: the command strings below are generic SCPI-style examples. Real
instruments differ - always follow your instrument's programming manual.
"""

from __future__ import annotations

from typing import Protocol

from .interfaces import RigError


class Transport(Protocol):
    def write(self, command: str) -> None: ...

    def query(self, command: str) -> str: ...

    def close(self) -> None: ...


class InstrumentError(RigError):
    """The instrument reported an error or replied with nonsense."""


class ScpiInstrument:
    def __init__(self, transport: Transport) -> None:
        self._io = transport

    def identify(self) -> str:
        return self._io.query("*IDN?").strip()

    def check_errors(self) -> None:
        """Read the instrument's error queue; raise if it is not empty."""
        reply = self._io.query("SYST:ERR?").strip()
        if not reply.startswith("0,"):
            raise InstrumentError(f"{type(self).__name__} reported: {reply}")

    def _query_float(self, command: str) -> float:
        reply = self._io.query(command).strip()
        try:
            return float(reply)
        except ValueError:
            raise InstrumentError(f"{command} returned {reply!r}, not a number") from None

    def close(self) -> None:
        self._io.close()


class ScpiPressureController(ScpiInstrument):
    MIN_HPA, MAX_HPA = 30.0, 1300.0

    def __init__(self, transport: Transport) -> None:
        super().__init__(transport)
        self._io.write("UNIT:PRES HPA")

    def set_pressure_hpa(self, hpa: float) -> None:
        if not self.MIN_HPA <= hpa <= self.MAX_HPA:
            raise ValueError(f"{hpa} hPa outside controller range")
        self._io.write(f"SOUR:PRES {hpa:.3f}")
        self.check_errors()

    def read_pressure_hpa(self) -> float:
        return self._query_float("MEAS:PRES?")


class ScpiPowerSupply(ScpiInstrument):
    MAX_VOLTAGE = 32.0
    MAX_CURRENT_A = 5.0

    def __init__(self, transport: Transport, voltage: float = 28.0, current_limit_a: float = 1.0):
        super().__init__(transport)
        self.configure(voltage, current_limit_a)

    def configure(self, voltage: float, current_limit_a: float) -> None:
        if not 0.0 <= voltage <= self.MAX_VOLTAGE:
            raise ValueError(f"voltage {voltage} V outside 0..{self.MAX_VOLTAGE} V")
        if not 0.0 < current_limit_a <= self.MAX_CURRENT_A:
            raise ValueError(f"current limit {current_limit_a} A outside range")
        self._io.write(f"VOLT {voltage:.2f}")
        self._io.write(f"CURR {current_limit_a:.3f}")
        self.check_errors()

    def set_output(self, on: bool) -> None:
        self._io.write("OUTP ON" if on else "OUTP OFF")

    @property
    def output_on(self) -> bool:
        return self._io.query("OUTP?").strip() in {"1", "ON"}

    def measure_current_a(self) -> float:
        return self._query_float("MEAS:CURR?")
