"""Software-in-the-loop (SIL) simulation of the ADC test rig.

The REAL avionics code (avionics.adc.AirDataComputer) runs inside a simulated
environment: simulated pressure controller, sensors, ARINC bus, power supply
and a VIRTUAL clock. Virtual time means a 10-second test takes milliseconds
and is perfectly repeatable - no flaky timing.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from avionics.adc import AirDataComputer, SensorError
from avionics.arinc429 import decode_word

from .interfaces import RigError, TimedWord

FRAME_PERIOD_S = 0.050  # ADC runs at 20 Hz
SLEW_RATE_HPA_PER_S = 100.0  # how fast the simulated controller moves
SENSOR_NOISE_HPA = 0.01
POWERED_CURRENT_A = 0.35


class SimClock:
    """Virtual clock. Time only moves when someone calls sleep().

    Time is kept in integer microseconds so that adding 0.05 s a thousand
    times gives exactly 50 s (float addition would drift).
    """

    def __init__(self) -> None:
        self._now_us = 0
        self._tasks: list[list] = []  # [next_due_us, period_us, callback]

    def now(self) -> float:
        return self._now_us / 1_000_000

    def every(self, period_s: float, callback: Callable[[], None]) -> None:
        period_us = round(period_s * 1_000_000)
        self._tasks.append([self._now_us + period_us, period_us, callback])

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot sleep for a negative time")
        target_us = self._now_us + round(seconds * 1_000_000)
        while self._tasks:
            task = min(self._tasks, key=lambda t: t[0])
            if task[0] > target_us:
                break
            self._now_us = task[0]
            task[0] += task[1]
            task[2]()
        self._now_us = target_us


class SimPressureController:
    """Moves toward the set-point at a limited slew rate, like a real one."""

    MIN_HPA, MAX_HPA = 30.0, 1300.0  # controller's own physical range

    def __init__(self, clock: SimClock, slew_hpa_per_s: float = SLEW_RATE_HPA_PER_S):
        self._clock = clock
        self._slew = slew_hpa_per_s
        self._actual = 1013.25
        self._setpoint = 1013.25
        self._last_update = clock.now()

    def _advance(self) -> None:
        now = self._clock.now()
        max_step = self._slew * (now - self._last_update)
        self._last_update = now
        error = self._setpoint - self._actual
        self._actual += max(-max_step, min(max_step, error))

    def set_pressure_hpa(self, hpa: float) -> None:
        if not self.MIN_HPA <= hpa <= self.MAX_HPA:
            raise RigError(f"set-point {hpa} hPa outside controller range")
        self._advance()
        self._setpoint = hpa

    def read_pressure_hpa(self) -> float:
        self._advance()
        return self._actual


class SimSensor:
    """One of the ADC's three pressure sensors, connected to the controller."""

    def __init__(self, source: SimPressureController, rng: random.Random) -> None:
        self._source = source
        self._rng = rng
        self.failed = False
        self.bias_hpa = 0.0

    def read_hpa(self) -> float:
        if self.failed:
            raise SensorError("simulated open circuit")
        noise = self._rng.uniform(-SENSOR_NOISE_HPA, SENSOR_NOISE_HPA)
        return self._source.read_pressure_hpa() + self.bias_hpa + noise


class SimBusMonitor:
    """Records every word the ADC transmits, time-stamped by the clock."""

    def __init__(self, clock: SimClock) -> None:
        self._clock = clock
        self._words: list[TimedWord] = []

    # The ADC sees this object as its Arinc429Transmitter ...
    def send(self, word: int) -> None:
        self._words.append((self._clock.now(), decode_word(word)))

    # ... and the tests see it as a BusMonitor.
    def latest(self, label: int) -> TimedWord | None:
        for timed in reversed(self._words):
            if timed[1].label == label:
                return timed
        return None

    def history(self, label: int, since: float = 0.0) -> list[TimedWord]:
        return [(t, w) for t, w in self._words if w.label == label and t > since]

    def clear(self) -> None:
        self._words.clear()


class SimPowerSupply:
    def __init__(self, on_power_change: Callable[[bool], None]) -> None:
        self._on = False
        self._callback = on_power_change

    def set_output(self, on: bool) -> None:
        if on != self._on:
            self._on = on
            self._callback(on)

    @property
    def output_on(self) -> bool:
        return self._on

    def measure_current_a(self) -> float:
        return POWERED_CURRENT_A if self._on else 0.0


class SimFaultInjector:
    def __init__(self, sensors: list[SimSensor]) -> None:
        self._sensors = sensors

    def fail_sensor(self, channel: int) -> None:
        self._sensors[channel].failed = True

    def bias_sensor(self, channel: int, bias_hpa: float) -> None:
        self._sensors[channel].bias_hpa = bias_hpa

    def clear(self) -> None:
        for sensor in self._sensors:
            sensor.failed = False
            sensor.bias_hpa = 0.0


class SimRig:
    """Everything wired together. Satisfies the `Rig` protocol."""

    name = "SIL simulation"
    capabilities = frozenset({"fault_injection"})

    def __init__(self, seed: int = 1) -> None:
        self.clock = SimClock()
        self.pressure = SimPressureController(self.clock)
        rng = random.Random(seed)  # seeded: identical noise on every run
        self._sensors = [SimSensor(self.pressure, rng) for _ in range(3)]
        self.bus = SimBusMonitor(self.clock)
        self.faults = SimFaultInjector(self._sensors)
        self.power = SimPowerSupply(self._on_power_change)
        self._adc: AirDataComputer | None = None
        self.clock.every(FRAME_PERIOD_S, self._frame)

    def _on_power_change(self, on: bool) -> None:
        # Power-up builds a fresh ADC: RAM (and the voter's latches) is lost
        # when power is removed, exactly like the real box.
        self._adc = AirDataComputer(self._sensors, self.bus) if on else None

    def _frame(self) -> None:
        if self._adc is not None:
            self._adc.run_frame()

    def close(self) -> None:
        self.power.set_output(False)
