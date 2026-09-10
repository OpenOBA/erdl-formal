"""ANP2 round: small-model evidence + kill matrix (resolution_smt).

Experiment 1 — do the properties stay UNSAT when the harness is pushed past the
checked n ∈ {2,3,4} to n=5,6? (a necessary condition for "exhausting four
exhausts everything"; if any turns SAT at 5/6, the cutoff is not 4).

Experiment 2 — kill matrix: which properties detect which gate mutants?
"none" (gate removal) should be killed by everything (no independence info);
same_ring / same_priority are the informative columns.
"""
import sys
import time

from erdl_formal.resolution_smt import (
    catch_all_inert_when_explicit,
    catch_all_override_irrelevant_when_explicit,
    catch_all_then_irrelevant_when_explicit,
    emergency_shortcut,
    override_soundness,
    ring_respect,
    workflow_shortcut,
)

PROPS = {
    "override_soundness": override_soundness,
    "ring_respect": ring_respect,
    "emergency_shortcut": emergency_shortcut,
    "workflow_shortcut": workflow_shortcut,
    "catch_all_inert": catch_all_inert_when_explicit,
    "catch_all_then_irrelevant": catch_all_then_irrelevant_when_explicit,
    "catch_all_override_irrelevant": catch_all_override_irrelevant_when_explicit,
}
MUTANTS = ["none", "invert", "same_ring", "same_priority"]

MAX_N = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def main():
    print("=== 实验 1: property UNSAT at n ∈ {2,3,4,5,6} (up to %d) ===" % MAX_N)
    for name, fn in PROPS.items():
        cells = []
        for n in range(2, MAX_N + 1):
            t0 = time.time()
            holds, _ = fn(n)
            dt = time.time() - t0
            cells.append("U" if holds else "S")
            print(f"  {name:36s} n={n}: {'UNSAT' if holds else 'SAT'}  ({dt:.1f}s)")
        print(f"    row: {' '.join(cells)}")
        print()

    print("=== 实验 2: kill matrix (catch-all props × gate mutants, n=4) ===")
    catchall = ["catch_all_inert", "catch_all_then_irrelevant", "catch_all_override_irrelevant"]
    header = "  {:<36s}  ".format("property") + " | ".join(f"{g:<12s}" for g in MUTANTS)
    print(header)
    for name in catchall:
        fn = PROPS[name]
        cells = []
        for gate in MUTANTS:
            t0 = time.time()
            holds, _ = fn(4, gate=gate)
            dt = time.time() - t0
            cells.append(("SURVIVE" if holds else "KILL") + f"({dt:.0f}s)")
        print(f"  {name:<36s}  " + " | ".join(cells))


if __name__ == "__main__":
    main()
