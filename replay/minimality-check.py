"""Minimality check — is the witness bound ≤2 tight?

For each resolution property, ask: does a 3-rule set violate the property while
EVERY 2-element subset satisfies it?

  - UNSAT => no size-3 *minimal* witness exists — every 3-rule violation has a
    2-rule sub-violation, so the witness bound is ≤2 (tight at the checked n).
  - SAT   => a size-3 minimal witness exists (the bound is NOT 2).

This is the ANP2-recommended minimality query — it tests minimality, not a
single deletion order (which is what greedy shrink does).
"""
import sys
import time

from z3 import And, Not, Or, Solver, unsat, substitute

from erdl_formal.resolution_smt import (
    ALLOW,
    DENY,
    EMERGENCY_HALT,
    WORKFLOW,
    ResolutionFold,
)

BAD = {
    "override_soundness": lambda st: [And(st["effective"], st["has_before"],
                                          st["dec"] == DENY, st["enables"],
                                          st["final_before"] == ALLOW,
                                          st["final_ring_before"] == st["ring"],
                                          st["final_after"] == DENY) for st in st],
    "ring_respect": lambda st: [And(st["effective"], st["has_before"],
                                    st["dec"] == DENY, Not(st["catch_all"]),
                                    st["final_before"] == ALLOW,
                                    st["ring"] > st["final_ring_before"],
                                    st["final_after"] != DENY) for st in st],
    "catch_all_inert": lambda st: [And(st["effective"], st["catch_all"],
                                       st["has_explicit"]) for st in st],
    "emergency_shortcut": lambda st: (
        [And(st["term_hit"], st["dec"] == EMERGENCY_HALT,
             st["final_after"] != EMERGENCY_HALT) for st in st] +
        [And(st["effective"], st["has_before"], st["final_before"] == EMERGENCY_HALT,
             st["final_after"] != EMERGENCY_HALT) for st in st]),
    "workflow_shortcut": lambda st: (
        [And(st["term_hit"], st["dec"] == WORKFLOW,
             st["final_after"] != WORKFLOW) for st in st] +
        [And(st["effective"], st["has_before"], st["final_before"] == WORKFLOW,
             st["final_after"] != WORKFLOW) for st in st]),
}


def _subs_skip(m2, m, removed):
    """Bind m2's k-th variables to m's i-th variables, skipping `removed`."""
    subs = []
    k = 0
    for i in range(m.n):
        if i == removed:
            continue
        subs += [(m2.dec[k], m.dec[i]), (m2.ring[k], m.ring[i]),
                 (m2.prio[k], m.prio[i]), (m2.ovr[k], m.ovr[i]),
                 (m2.catch_all[k], m.catch_all[i])]
        k += 1
    return subs


def minimality(bad_fn, n=3):
    """UNSAT <=> no size-3 minimal witness (every 3-rule violation has a 2-rule sub-violation)."""
    m = ResolutionFold(n)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    _, steps = m.build()
    s.add(Or(*bad_fn(steps)))  # 3-rule set violates

    for removed in range(n):
        m2 = ResolutionFold(n - 1)
        subs = _subs_skip(m2, m, removed)
        for c in m2.domain_constraints() + m2.sorted_premise():
            s.add(substitute(c, *subs))
        _, steps2 = m2.build()
        bad2 = Or(*bad_fn(steps2))
        s.add(Not(substitute(bad2, *subs)))  # this 2-subset does NOT violate

    return s.check() == unsat


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(f"=== minimality at n={n} (UNSAT => witness bound <= 2 is tight) ===")
    for name, bad_fn in BAD.items():
        t0 = time.time()
        tight = minimality(bad_fn, n)
        dt = time.time() - t0
        print(f"  {name:22s}: {'UNSAT (bound<=2 tight)' if tight else 'SAT (size-3 minimal witness exists)'}  ({dt:.1f}s)")


if __name__ == "__main__":
    main()
