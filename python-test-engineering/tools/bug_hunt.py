#!/usr/bin/env python3
"""Bug hunt: measure how good your tests are at finding real bugs.

Usage (from the python-test-engineering/ folder):

    python tools/bug_hunt.py lessons/02_pytest_fundamentals/test_arinc429.py
    python tools/bug_hunt.py <test file> --target voter      # choose bug group
    python tools/bug_hunt.py --list                          # list bug groups

What it does
------------
1. Runs your tests against the CORRECT code. They must pass - a test that
   fails on correct code is itself a bug.
2. For every seeded bug ("mutant") in the target group, runs your tests again
   with that one bug injected. If at least one test fails, the bug is CAUGHT.
   If everything still passes, the bug is MISSED - your tests would have let
   it reach the aircraft.

This technique is called MUTATION TESTING. Code coverage tells you which
lines your tests *executed*; mutation testing tells you whether your tests
would actually *notice* if those lines were wrong.

Exit status: 0 all caught, 1 some missed, 2 tests fail on correct code.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
COURSE_ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(COURSE_ROOT / "src")]

import mutants  # noqa: E402  (needs the sys.path tweak above)

USE_COLOUR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def colour(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text


def detect_groups(test_file: Path) -> list[str]:
    """Guess which bug groups apply: by file name first, then by imports."""
    stem = test_file.stem.removeprefix("test_")
    if stem in mutants.GROUPS:
        return [stem]
    source = test_file.read_text(encoding="utf-8")
    found = set(re.findall(r"avionics\.(\w+)", source))
    for names in re.findall(r"from\s+avionics\s+import\s+([\w\s,()]+)", source):
        found.update(re.findall(r"\w+", names))
    return sorted(found & set(mutants.GROUPS))


def run_pytest(test_files: list[Path], mutant_id: str | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(HERE), str(COURSE_ROOT / "src"), env.get("PYTHONPATH", "")]
    )
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "--no-header",
           "-p", "no:cacheprovider", "-p", "mutant_plugin"]
    if importlib.util.find_spec("hypothesis") is not None:
        cmd += ["--hypothesis-seed=0"]  # reproducible property-based runs
    if mutant_id:
        cmd += [f"--mutant={mutant_id}"]
    cmd += [str(f) for f in test_files]
    return subprocess.run(cmd, cwd=COURSE_ROOT, env=env, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tests", nargs="*", type=Path, help="test file(s) to evaluate")
    parser.add_argument("--target", action="append", choices=mutants.GROUPS,
                        help="bug group(s) to inject (default: guessed from the file)")
    parser.add_argument("--list", action="store_true", help="list bug groups and exit")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show pytest output for the baseline run")
    args = parser.parse_args(argv)

    if args.list or not args.tests:
        for group in mutants.GROUPS:
            count = sum(m.group == group for m in mutants.MUTANTS)
            print(f"  {group:<15} {count} seeded bugs")
        return 0

    tests = [t.resolve() for t in args.tests]
    for t in tests:
        if not t.exists():
            parser.error(f"{t} does not exist")

    groups = args.target or sorted({g for t in tests for g in detect_groups(t)})
    if not groups:
        parser.error("could not tell which module these tests target - use --target")
    selected = [m for m in mutants.MUTANTS if m.group in groups]

    print(colour(f"Bug hunt - target: {', '.join(groups)}", "1"))
    baseline = run_pytest(tests, None)
    if baseline.returncode != 0:
        print(colour("  Your tests FAIL on the correct code. Fix them first:", "31"))
        print(baseline.stdout[-3000:] or baseline.stderr[-3000:])
        return 2
    summary = baseline.stdout.strip().splitlines()[-1] if baseline.stdout.strip() else ""
    print(f"  Baseline on correct code: PASS  ({summary})")
    if args.verbose:
        print(baseline.stdout)

    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
        results = list(pool.map(lambda m: (m, run_pytest(tests, m.id)), selected))

    caught = 0
    for mutant, result in results:
        if result.returncode in (1, 2):  # 1 = tests failed, 2 = errored during collection
            caught += 1
            print(f"  {colour('[CAUGHT]', '32')} {mutant.id}")
        elif result.returncode == 0:
            print(f"  {colour('[MISSED]', '33')} {mutant.id}")
            print(f"           hint: {mutant.hint}")
        else:
            print(f"  {colour('[ERROR] ', '31')} {mutant.id} (pytest exit {result.returncode})")
            print(result.stdout[-1500:] or result.stderr[-1500:])

    total = len(selected)
    verdict = colour("all bugs caught!", "32") if caught == total else "keep going"
    print(colour(f"Score: {caught}/{total} seeded bugs caught - {verdict}", "1"))
    return 0 if caught == total else 1


if __name__ == "__main__":
    sys.exit(main())
