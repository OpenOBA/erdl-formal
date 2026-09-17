"""Support-lemma — deletion invariance at ANY position (not just the last).

The earlier ``support_lemma`` only proved deleting the *last* gated-off rule is
verdict-neutral. For "delete repeatedly to a minimal support set" we need the
invariance at an arbitrary sorted-array position j: delete position j, shift the
tail left (which preserves sortedness — deleting an element of a sorted array
keeps it sorted), and the verdict is unchanged.

This is NOT "swap invariance": swapping adjacent rules breaks ``sorted_premise``
(ring/priority/override order). Deletion-and-shift is the right bridge.
"""
import sys
import time

from z3 import Not, Solver, unsat, substitute

from erdl_formal.resolution_smt import ResolutionFold


def support_lemma_at(n, j):
    """Deleting the gated-off rule at sorted position j leaves the verdict unchanged."""
    m = ResolutionFold(n)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    final, steps = m.build()
    s.add(Not(steps[j]["effective"]))  # position j gated off
    s.add(Not(steps[j]["term_hit"]))   # not a terminal short-circuit

    m2 = ResolutionFold(n - 1)
    subs = []
    k = 0
    for i in range(n):
        if i == j:
            continue
        subs += [(m2.dec[k], m.dec[i]), (m2.ring[k], m.ring[i]),
                 (m2.prio[k], m.prio[i]), (m2.ovr[k], m.ovr[i]),
                 (m2.catch_all[k], m.catch_all[i])]
        k += 1
    for c in m2.domain_constraints() + m2.sorted_premise():
        s.add(substitute(c, *subs))
    final2, _ = m2.build()
    final2 = substitute(final2, *subs)

    s.add(final != final2)
    return s.check() == unsat


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    for n in (4, 5):
        cells = []
        for j in range(n):
            t0 = time.time()
            holds = support_lemma_at(n, j)
            dt = time.time() - t0
            cells.append('U' if holds else 'S')
            print(f"  n={n} j={j}: {'UNSAT (invariance holds)' if holds else 'SAT (COUNTEREXAMPLE)'}  ({dt:.1f}s)")
        print(f"    row: {' '.join(cells)}")


if __name__ == "__main__":
    main()
