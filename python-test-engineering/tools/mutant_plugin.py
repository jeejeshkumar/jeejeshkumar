"""pytest plugin that injects ONE seeded bug before your tests are collected.

Used by tools/bug_hunt.py as:  pytest -p mutant_plugin --mutant=<id> <tests>

How it works: in ``pytest_configure`` (which runs before any test module is
imported) we import the target module and replace one attribute - e.g.
``avionics.arinc429.parity_bit`` - with a buggy version. Any code that looks
the name up at call time (including the SUT's own internal calls and your
``from avionics.arinc429 import ...`` statements, which run later) gets the
mutant. This is the same "monkeypatching" idea you will use in lesson 3.
"""

from __future__ import annotations

import importlib

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--mutant", default=None, help="id of the seeded bug to inject")


def pytest_configure(config: pytest.Config) -> None:
    mutant_id = config.getoption("--mutant")
    if not mutant_id:
        return
    import mutants  # imported lazily so a plain run has no side effects

    try:
        mutant = mutants.BY_ID[mutant_id]
    except KeyError:
        raise pytest.UsageError(f"unknown mutant {mutant_id!r}") from None

    owner = importlib.import_module(mutant.module)
    *path, attribute = mutant.target.split(".")
    for name in path:  # e.g. "TriplexVoter.update" -> owner = TriplexVoter
        owner = getattr(owner, name)
    if not hasattr(owner, attribute):
        raise pytest.UsageError(f"{mutant.module}.{mutant.target} does not exist")
    setattr(owner, attribute, mutant.replacement)
