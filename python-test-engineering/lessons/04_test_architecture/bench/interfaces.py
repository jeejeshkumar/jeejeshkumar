"""Contracts between the test layers and the test equipment.

Tests and steps ONLY talk to these interfaces. Whether a PressureController is
a simulation or a real pressure controller on a LAN port is decided once, in
conftest.py, by the --target option. This is the Dependency Inversion
Principle: high-level policy (tests) and low-level detail (drivers) both
depend on an abstraction.

typing.Protocol gives "structural typing": a class satisfies the protocol if
it has the right methods - it does not need to inherit from it. That keeps
simulations and drivers decoupled from this file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from avionics.arinc429 import Arinc429Word

# A received ARINC 429 word together with the rig time it arrived at.
TimedWord = tuple[float, Arinc429Word]


class RigError(Exception):
    """Test equipment problem (NOT a failure of the unit under test)."""


class Clock(Protocol):
    def now(self) -> float:
        """Seconds since the rig started."""
        ...

    def sleep(self, seconds: float) -> None: ...


class PressureController(Protocol):
    """Pneumatic pressure controller feeding the ADC's static port."""

    def set_pressure_hpa(self, hpa: float) -> None: ...

    def read_pressure_hpa(self) -> float: ...


class BusMonitor(Protocol):
    """ARINC 429 receiver listening to the ADC's output bus."""

    def latest(self, label: int) -> TimedWord | None: ...

    def history(self, label: int, since: float = 0.0) -> list[TimedWord]: ...

    def clear(self) -> None: ...


class PowerSupply(Protocol):
    """28 V DC aircraft-power simulation for the ADC."""

    def set_output(self, on: bool) -> None: ...

    @property
    def output_on(self) -> bool: ...

    def measure_current_a(self) -> float: ...


class FaultInjector(Protocol):
    """Fault insertion (a relay box on a real rig; trivial in simulation)."""

    def fail_sensor(self, channel: int) -> None: ...

    def bias_sensor(self, channel: int, bias_hpa: float) -> None: ...

    def clear(self) -> None: ...


class Rig(Protocol):
    name: str
    capabilities: frozenset[str]  # e.g. {"fault_injection"}
    clock: Clock
    pressure: PressureController
    bus: BusMonitor
    power: PowerSupply
    faults: FaultInjector | None

    def close(self) -> None: ...


# A factory that builds a rig - conftest.py chooses which one.
RigFactory = Callable[[], Rig]
