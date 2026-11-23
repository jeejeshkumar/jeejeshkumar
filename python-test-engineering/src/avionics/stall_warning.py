"""Stall warning decision - a compact example for learning MC/DC (lesson 6).

Requirement:

    SW-001  The stall warning shall be active when EITHER
              (a) the angle of attack is GREATER than the AoA limit AND the
                  aircraft is NOT on the ground (no weight on wheels),
            OR
              (b) the crew presses the stall-warning test switch.

The decision has three conditions:

    A = aoa_deg > aoa_limit_deg
    B = not weight_on_wheels
    C = test_switch

    decision = (A and B) or C
"""

from __future__ import annotations


def stall_warning(
    aoa_deg: float, aoa_limit_deg: float, weight_on_wheels: bool, test_switch: bool
) -> bool:
    if (aoa_deg > aoa_limit_deg and not weight_on_wheels) or test_switch:
        return True
    return False
