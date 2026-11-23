"""A layered test-rig framework for the Air Data Computer.

Layers (top depends on bottom, never the other way round):

    tests            test_adc_requirements.py   WHAT is verified (requirements)
    steps            bench/steps.py             HOW, in domain language
    interfaces       bench/interfaces.py        contracts for test equipment
    implementations
        bench/sim.py      software-in-the-loop simulation (runs anywhere)
        bench/drivers.py  SCPI instrument drivers  } for a real
        bench/hw.py       hardware rig assembly    } hardware-in-the-loop rig

    cross-cutting    bench/traceability.py      requirement -> test -> verdict
    wiring           conftest.py                --target, fixtures, reporting
"""
