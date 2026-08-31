"""Quantifier encoding (E8): all / any / none over a bounded array.

E8 (spec v2.0 §10.2): empty array → **all / any / none ALL fold to false** —
a deliberate safe deviation from the standard ``all([])=true`` vacuous truth,
to prevent fail-open ("no elements to check → treated as all-pass").

Non-empty: index expansion (∧ / ∨ / ¬∨ over 0..N-1), where N is the concrete
array cardinality (a schema premise, since v2.0 has no verification schema).
"""

from z3 import And, Not, Or

from .tvl import TVLBool, val_bool


def tvl_all(elements):
    """all(elements) — empty → Def(False); else ∧ elements[i].

    ``elements`` is a fixed-length list of TVLBool (already-collapsed booleans).
    """
    if not elements:
        return TVLBool.Def(False)  # E8: all([]) = false (anti-vacuous-truth)
    return TVLBool.Def(And(*[val_bool(e) for e in elements]))


def tvl_any(elements):
    """any(elements) — empty → Def(False); else ∨ elements[i]."""
    if not elements:
        return TVLBool.Def(False)  # E8: any([]) = false (standard)
    return TVLBool.Def(Or(*[val_bool(e) for e in elements]))


def tvl_none(elements):
    """none(elements) — empty → Def(False); else ¬∨ elements[i]."""
    if not elements:
        return TVLBool.Def(False)  # E8: none([]) = false (safe deviation)
    return TVLBool.Def(Not(Or(*[val_bool(e) for e in elements])))
