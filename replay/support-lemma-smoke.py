"""Support-lemma smoke — deletion invariance for a gated-off rule.

ANP2 round: before committing to the full support lemma, prove (smoke) that the
encoding path is viable. The simplest instance of "verdict depends only on a
bounded support set" is deletion invariance for a rule that provably does not
fire.

Smoke 1 — advisory rule that arrives after a decision is already set:
  - dec[n-1] ∈ {CORRECT, NOTIFY, REQUEST_HUMAN, ESCALATE, DELEGATE, DEFER, GUIDE}
  - has_before(n-1) == True  (a decision is set before this rule)
  Then gate_pass = Not(has) = False, so the rule is gated off (effective=False),
  and deleting it MUST leave the final decision unchanged.

  UNSAT over ``final != final_without_last`` ⇒ deletion invariance holds.

Smoke 2 — catch-all rule when an explicit rule is present:
  - dec[n-1] is a catch-all (catch_all=True) with any decision
  - has_explicit == True
  Then catch_all_ok = False (global §7.1 item 6), so the rule is gated off,
  and deleting it MUST leave the final decision unchanged.

Both are checked at n=4 and n=5 (n=5 sits *outside* the exhaustively-checked
region, so it probes whether the invariance survives the cardinality bump).
"""
import time

from z3 import Not, Or, Solver, unsat, substitute

from erdl_formal.resolution_smt import (
    CORRECT,
    DEFER,
    DELEGATE,
    ESCALATE,
    GUIDE,
    NOTIFY,
    REQUEST_HUMAN,
    ResolutionFold,
)

ADVISORY = [CORRECT, NOTIFY, REQUEST_HUMAN, ESCALATE, DELEGATE, DEFER, GUIDE]


def _shared_prefix_subs(m2, m):
    """Bind m2's first (n-1) variables to m's first (n-1) variables."""
    subs = []
    for i in range(m2.n):
        subs.append((m2.dec[i], m.dec[i]))
        subs.append((m2.ring[i], m.ring[i]))
        subs.append((m2.prio[i], m.prio[i]))
        subs.append((m2.ovr[i], m.ovr[i]))
        subs.append((m2.catch_all[i], m.catch_all[i]))
    return subs


def deletion_invariance_advisory(n=4):
    """Deleting a gated-off advisory rule leaves the verdict unchanged."""
    m = ResolutionFold(n)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    s.add(Or(*[m.dec[n - 1] == d for d in ADVISORY]))
    final, steps = m.build()
    s.add(steps[n - 1]["has_before"])  # a decision is already set

    m2 = ResolutionFold(n - 1)
    final2, _ = m2.build()
    final2 = substitute(final2, *_shared_prefix_subs(m2, m))

    s.add(final != final2)
    return s.check() == unsat


def deletion_invariance_catchall(n=4):
    """Deleting a catch-all rule (inert when explicit present) leaves the verdict unchanged."""
    m = ResolutionFold(n)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    s.add(m.catch_all[n - 1])          # last rule is a catch-all
    s.add(m.has_explicit())            # some explicit rule exists
    final, _ = m.build()

    m2 = ResolutionFold(n - 1)
    final2, _ = m2.build()
    final2 = substitute(final2, *_shared_prefix_subs(m2, m))

    s.add(final != final2)
    return s.check() == unsat


def deletion_invariance_generic(n=4):
    """Deleting ANY rule with effective=False (gated off) leaves the verdict unchanged.

    This is the general form — it does not name the rule's decision class; it
    constrains the last rule to be gated off (effective=False, not a terminal
    short-circuit) and proves deleting it is verdict-neutral. It subsumes the
    advisory / catch-all / skip / done cases in one query.
    """
    m = ResolutionFold(n)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    final, steps = m.build()
    s.add(Not(steps[n - 1]["effective"]))  # gated off
    s.add(Not(steps[n - 1]["term_hit"]))   # not a terminal short-circuit

    m2 = ResolutionFold(n - 1)
    final2, _ = m2.build()
    final2 = substitute(final2, *_shared_prefix_subs(m2, m))

    s.add(final != final2)
    return s.check() == unsat


def main():
    for n in (4, 5):
        for name, fn in (("advisory gated-off", deletion_invariance_advisory),
                         ("catch-all gated-off", deletion_invariance_catchall),
                         ("generic gated-off", deletion_invariance_generic)):
            t0 = time.time()
            holds = fn(n)
            dt = time.time() - t0
            print(f"  n={n}  {name:22s}: {'UNSAT (invariance holds)' if holds else 'SAT (COUNTEREXAMPLE)'}  ({dt:.1f}s)")


if __name__ == "__main__":
    main()
