"""Triplex (3-channel) sensor voter with miscompare monitoring.

Safety-critical air data systems use three independent sensors so that one
faulty sensor can be detected and outvoted. Every frame the voter receives
one reading per channel (or ``None`` if that channel produced no data) and
produces a single voted value.

Requirements implemented here (used by the tests in lessons 3 and 5):

    VOT-001  With three healthy channels reporting, the output is the median
             (mid-value select) of the three readings.
    VOT-002  A healthy channel MISCOMPARES in a frame when
             |reading - voted value| > threshold   (strictly greater).
             This check is only made when three channels report.
    VOT-003  A healthy channel that reports no data (None) miscompares.
    VOT-004  A channel that miscompares on `persistence` CONSECUTIVE frames is
             latched failed and no longer used for voting.
    VOT-005  A channel's miscompare counter resets to zero on any frame in
             which it does not miscompare.
    VOT-006  A latched failure stays latched until reset() is called;
             reset() clears all latches AND all miscompare counters.
    VOT-007  With exactly two channels contributing, the output is their
             mean if |a - b| <= threshold; otherwise the output is invalid.
             (With two channels we cannot tell which one is wrong, so no new
             channel is latched.)
    VOT-008  With fewer than two channels contributing, the output is invalid.
    VOT-009  update() raises ValueError unless it gets exactly three readings,
             each either None or a finite number.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

CHANNELS = 3


@dataclass(frozen=True)
class VoterOutput:
    value: float | None  # None when the output is invalid
    valid: bool
    failed_channels: frozenset[int]  # latched failed channel indices (0, 1, 2)


class TriplexVoter:
    def __init__(self, threshold: float, persistence: int) -> None:
        if not threshold > 0:
            raise ValueError(f"threshold must be > 0, got {threshold!r}")
        if persistence < 1:
            raise ValueError(f"persistence must be >= 1, got {persistence!r}")
        self.threshold = threshold
        self.persistence = persistence
        self._miscompare_counts = [0] * CHANNELS
        self._failed: set[int] = set()

    @property
    def failed_channels(self) -> frozenset[int]:
        return frozenset(self._failed)

    def miscompare_count(self, channel: int) -> int:
        return self._miscompare_counts[channel]

    def reset(self) -> None:
        """Maintenance reset: clear every latch and counter (VOT-006)."""
        self._failed.clear()
        self._miscompare_counts = [0] * CHANNELS

    def update(self, readings: Sequence[float | None]) -> VoterOutput:
        self._validate(readings)
        healthy = [ch for ch in range(CHANNELS) if ch not in self._failed]

        # VOT-003: a healthy channel with no data counts as a miscompare.
        for ch in healthy:
            if readings[ch] is None:
                self._record(ch, miscompared=True)

        reporting = [ch for ch in healthy if readings[ch] is not None]

        if len(reporting) == 3:
            values = [readings[ch] for ch in reporting]
            voted = self._mid_value(values)
            for ch in reporting:
                self._record(ch, self._miscompares(readings[ch], voted))
            return self._output(voted)

        if len(reporting) == 2:
            a, b = (readings[ch] for ch in reporting)
            if self._miscompares(a, b):
                return self._output(None)
            return self._output((a + b) / 2)

        return self._output(None)

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _validate(readings: Sequence[float | None]) -> None:
        if len(readings) != CHANNELS:
            raise ValueError(f"expected {CHANNELS} readings, got {len(readings)}")
        for r in readings:
            if r is not None and not math.isfinite(r):
                raise ValueError(f"readings must be finite or None, got {r!r}")

    @staticmethod
    def _mid_value(values: Sequence[float]) -> float:
        return sorted(values)[1]

    def _miscompares(self, reading: float, reference: float) -> bool:
        return abs(reading - reference) > self.threshold

    def _record(self, channel: int, miscompared: bool) -> None:
        if miscompared:
            self._miscompare_counts[channel] += 1
            if self._miscompare_counts[channel] >= self.persistence:
                self._failed.add(channel)
        else:
            self._miscompare_counts[channel] = 0

    def _output(self, value: float | None) -> VoterOutput:
        return VoterOutput(
            value=value, valid=value is not None, failed_channels=self.failed_channels
        )
