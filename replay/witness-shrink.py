"""ANP2 round: witness-shrink (small-model evidence) + independence check.

Experiment A (small-model evidence) — take each gate mutant's counterexample at
n=6, greedily delete rules one at a time, and report the minimum rule-count that
still violates the property. If every mutant witness shrinks to ≤4, that is
evidence (not proof) that "exhausting four" reaches the interesting witnesses;
a witness that will not shrink below 4 is the "real counterexample" ANP2 names.

Experiment B (independence) — for each pair of gate mutants, ask the solver for
one concrete rule-set that violates the property under mutant A but NOT under
mutant B (satisfy-one-violate-other). SAT => the two mutants are distinguishable
by that property; UNSAT (at the checked cardinality) => the property carries no
signal separating them.
"""
import sys
import time

from z3 import And, BoolVal, IntVal, Or, is_true, simplify, substitute

from erdl_formal.resolution_smt import (
    ALLOW,
    CORRECT,
    DEFER,
    DELEGATE,
    DENY,
    EMERGENCY_HALT,
    ESCALATE,
    GUIDE,
    NOTIFY,
    OVR_CRITICAL,
    OVR_HIGH,
    OVR_LOW,
    OVR_NONE,
    OVR_NORMAL,
    QUARANTINE,
    REQUEST_HUMAN,
    ROLLBACK,
    ResolutionFold,
    WORKFLOW,
    catch_all_inert_when_explicit,
)

_DEC = {
    "ALLOW": ALLOW, "DENY": DENY, "EMERGENCY_HALT": EMERGENCY_HALT,
    "CORRECT": CORRECT, "REQUEST_HUMAN": REQUEST_HUMAN, "ESCALATE": ESCALATE,
    "NOTIFY": NOTIFY, "DELEGATE": DELEGATE, "DEFER": DEFER, "ROLLBACK": ROLLBACK,
    "QUARANTINE": QUARANTINE, "WORKFLOW": WORKFLOW, "GUIDE": GUIDE,
}
_OVR = {
    "critical": OVR_CRITICAL, "high": OVR_HIGH, "normal": OVR_NORMAL,
    "low": OVR_LOW, "none": OVR_NONE,
}
MUTANTS = ["none", "invert", "same_ring", "same_priority"]


def _model_to_rules(m, model):
    rules = []
    for i in range(m.n):
        dec = str(model.eval(m.dec[i], model_completion=True))
        ring = model.eval(m.ring[i], model_completion=True).as_long()
        prio = model.eval(m.prio[i], model_completion=True).as_long()
        ovr = str(model.eval(m.ovr[i], model_completion=True))
        catch_all = is_true(model.eval(m.catch_all[i], model_completion=True))
        rules.append({"decision": dec, "ring": ring, "priority": prio,
                      "override": ovr, "catch_all": catch_all})
    return rules


def _violates(rules, gate):
    """Does this concrete rule-set violate catch-all inertness under `gate`?"""
    m = ResolutionFold(len(rules), gate=gate)
    _, steps = m.build()
    subs = []
    for i, r in enumerate(rules):
        subs.append((m.dec[i], _DEC[r["decision"]]))
        subs.append((m.ring[i], IntVal(r["ring"])))
        subs.append((m.prio[i], IntVal(r["priority"])))
        subs.append((m.ovr[i], _OVR[r["override"]]))
        subs.append((m.catch_all[i], BoolVal(r["catch_all"])))
    bad = Or(*[And(st["effective"], st["catch_all"], st["has_explicit"]) for st in steps])
    return is_true(simplify(substitute(bad, *subs)))


def _shrink(rules, gate):
    """Greedy delete: remove rules one at a time while the violation persists."""
    cur = list(rules)
    changed = True
    while changed and len(cur) > 1:
        changed = False
        for i in range(len(cur)):
            cand = cur[:i] + cur[i + 1:]
            if _violates(cand, gate):
                cur = cand
                changed = True
                break
    return cur


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6

    print(f"=== Experiment A: mutant witness shrink at n={n} ===")
    for gate in MUTANTS:
        t0 = time.time()
        holds, model = catch_all_inert_when_explicit(n, gate=gate)
        if holds:
            print(f"  {gate:14s}: UNSAT at n={n} (no counterexample) — skip shrink")
            continue
        m = ResolutionFold(n, gate=gate)
        rules = _model_to_rules(m, model)
        shrunk = _shrink(rules, gate)
        dt = time.time() - t0
        print(f"  {gate:14s}: witness {len(rules)} rules -> shrunk to {len(shrunk)} rules "
              f"(min={'yes' if len(shrunk) <= 4 else 'NO, >4'}) ({dt:.1f}s)")

    print()
    print(f"=== Experiment B: satisfy-one-violate-other (n={n}, property=catch_all_inert) ===")
    for i, ga in enumerate(MUTANTS):
        for gb in MUTANTS[i + 1:]:
            holds_a, model_a = catch_all_inert_when_explicit(n, gate=ga)
            holds_b, model_b = catch_all_inert_when_explicit(n, gate=gb)
            # both are SAT (detected); now ask for a single rule-set violating
            # under ga but not under gb. We approximate by: does ga's witness
            # also violate gb, and vice versa? (a coarser check than a fresh
            # solver query, but informative for the matrix rows).
            ma = ResolutionFold(n, gate=ga)
            ra = _model_to_rules(ma, model_a) if not holds_a else None
            mb = ResolutionFold(n, gate=gb)
            rb = _model_to_rules(mb, model_b) if not holds_b else None
            a_hits_b = (ra is not None) and _violates(ra, gb)
            b_hits_a = (rb is not None) and _violates(rb, ga)
            same = "SAME" if (a_hits_b and b_hits_a) else "DIFFER"
            print(f"  {ga:12s} vs {gb:12s}: a-witness-violates-b={a_hits_b}, "
                  f"b-witness-violates-a={b_hits_a} -> {same}")


if __name__ == "__main__":
    main()
