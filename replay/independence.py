"""ANP2 round: precise satisfy-one-violate-other (independence).

For each pair of gate mutants, ask Z3 for a single rule-set that violates
catch-all-inert under gate A but NOT under gate B. Because ResolutionFold names
its variables dec_i/ring_i/prio_i/ovr_i/catch_all_i, two folds over the same n
share the same Z3 constants, so `bad_A ∧ ¬bad_B` is a well-formed query over one
rule-set. SAT => A and B are distinguishable (A detects something B does not);
UNSAT => every A-violation is also a B-violation (A adds no independent signal).
"""
import sys

from z3 import And, Not, Or, Solver, sat, unsat

from erdl_formal.resolution_smt import ResolutionFold

MUTANTS = ["none", "invert", "same_ring", "same_priority"]


def bad_terms(n, gate):
    m = ResolutionFold(n, gate=gate)
    _, steps = m.build()
    return Or(*[And(st["effective"], st["catch_all"], st["has_explicit"]) for st in steps])


def distinguishable(n, ga, gb):
    """Is there a rule-set violating `ga` but not `gb`?"""
    mA = ResolutionFold(n, gate=ga)
    mB = ResolutionFold(n, gate=gb)
    badA = bad_terms(n, ga)
    badB = bad_terms(n, gb)
    s = Solver()
    # domain + sorted premise (identical across folds; use one copy)
    for c in mA.domain_constraints() + mA.sorted_premise():
        s.add(c)
    s.add(badA)
    s.add(Not(badB))
    r = s.check()
    return r == sat  # SAT = distinguishable


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    print(f"=== satisfy-one-violate-other (n={n}, catch_all_inert) ===")
    print(f"  {'':<12s}" + "".join(f"{g:<14s}" for g in MUTANTS))
    for ga in MUTANTS:
        row = f"  {ga:<12s}"
        for gb in MUTANTS:
            if ga == gb:
                row += f"{'---':<14s}"
            else:
                d = distinguishable(n, ga, gb)
                row += f"{'DIFF' if d else 'SUBSUMES':<14s}"
        print(row)
    print()
    print("  DIFF     = exists a rule-set violating row-gate but not col-gate (distinguishable)")
    print("  SUBSUMES = every row-gate violation is also a col-gate violation (row adds no independent signal)")


if __name__ == "__main__":
    main()
