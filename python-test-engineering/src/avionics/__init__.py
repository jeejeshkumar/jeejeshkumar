"""A small, realistic avionics code base used as the *system under test* (SUT).

Modules
-------
arinc429  - encode / decode ARINC 429 32-bit words (incl. BNR numeric data)
air_data  - International Standard Atmosphere (ISA) pressure-altitude maths
voter     - triplex (3-channel) mid-value-select voter with fault latching
adc       - Air Data Computer application that ties everything together
stall_warning - a small decision used to learn MC/DC coverage (lesson 6)

Import the sub-modules directly, e.g. ``from avionics import arinc429`` or
``from avionics.arinc429 import encode_word``.

Note: this package deliberately does NOT re-export names here. The bug-hunt
tool (tools/bug_hunt.py) swaps functions inside the sub-modules at run time,
and re-exports would keep pointing at the original, un-mutated functions.
"""
