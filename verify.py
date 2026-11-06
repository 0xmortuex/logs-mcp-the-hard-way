"""Run every module's main.py for real, the way CI does.

Each main.py checks its own results with assert and prints "module NN ok" last.
A chapter whose code drifts out of sync with what its README claims fails here.

Usage: python verify.py            # all modules
       python verify.py 02 05      # just these
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def modules() -> list[str]:
    return sorted(d for d in os.listdir(ROOT) if d[:2].isdigit() and os.path.isfile(os.path.join(ROOT, d, "main.py")))


def run(mod: str) -> bool:
    num = mod[:2]
    start = time.monotonic()
    # Run from OUTSIDE the module directory so nothing is picked up by accident.
    r = subprocess.run(
        [sys.executable, "-I", os.path.join(ROOT, mod, "main.py")],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=ROOT,
    )
    ok = r.returncode == 0 and f"module {num} ok" in r.stdout
    print(f"{'PASS' if ok else 'FAIL'}  {mod}  ({time.monotonic() - start:.1f}s)")
    if not ok:
        print(r.stdout[-2000:])
        print(r.stderr[-3000:])
    return ok


def main() -> int:
    wanted = sys.argv[1:]
    mods = [m for m in modules() if not wanted or m[:2] in wanted]
    if not mods:
        print("no modules matched")
        return 2
    results = [run(m) for m in mods]
    print(f"{sum(results)}/{len(results)} modules verified")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
