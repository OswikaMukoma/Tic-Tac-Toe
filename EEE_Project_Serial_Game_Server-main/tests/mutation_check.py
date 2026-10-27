#!/usr/bin/env python3
"""Prove the tests can fail: inject each fault into the mock and require pytest to fail.

    python tests/mutation_check.py          # baseline must pass, every fault must be caught
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mock_server import ALL_FAULTS   # noqa: E402


def run(fault=None):
    cmd = [sys.executable, "-m", "pytest", HERE, "-q", "-x", "--port", "mock", "-p", "no:cacheprovider"]
    if fault:
        cmd += ["--mock-fault", fault]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    failed = [l.split()[1] for l in proc.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))]
    return proc.returncode, (failed[0] if failed else "")


def main():
    rc, _ = run()
    print("baseline (no fault): %s" % ("PASS" if rc == 0 else "FAIL"))
    if rc != 0:
        return 2
    missed = 0
    print("%-24s %-8s %s" % ("fault", "result", "first failing test"))
    for fault in sorted(ALL_FAULTS):
        rc, test = run(fault)
        caught = rc != 0
        missed += not caught
        print("%-24s %-8s %s" % (fault, "CAUGHT" if caught else "MISSED", test))
    print("%d/%d faults caught" % (len(ALL_FAULTS) - missed, len(ALL_FAULTS)))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
