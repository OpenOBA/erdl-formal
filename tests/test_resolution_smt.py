# Copyright 2026 Shenzhen Miaojing Technology Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Differential + property tests for the symbolic resolution model.

Two kinds of test:

1. **Differential** — the symbolic fold must agree with the hand-written
   reference ``resolution.resolve`` on concrete rule-sets. This is checked two
   ways: (a) a pure-Python mirror of the fold's decision table, exhaustively
   against ``resolve`` (fast, proves the *reformulation* is faithful); (b) the
   Z3 fold itself, on a targeted + seeded-random sample (proves the *Z3
   transliteration* is faithful).

2. **Property proofs** — override-soundness / ring-respect / emergency-shortcut
   must be UNSAT over the negation (proof, not sampling), and non-vacuous
   (their antecedent is reachable).
"""

import itertools
import random

from z3 import BoolVal, IntVal, Or, Solver, sat, simplify, substitute

from erdl_formal import resolution
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
    emergency_shortcut,
    override_soundness,
    ring_respect,
    workflow_shortcut,
)

_DEC = {
    "ALLOW": ALLOW,
    "DENY": DENY,
    "EMERGENCY_HALT": EMERGENCY_HALT,
    "CORRECT": CORRECT,
    "REQUEST_HUMAN": REQUEST_HUMAN,
    "ESCALATE": ESCALATE,
    "NOTIFY": NOTIFY,
    "DELEGATE": DELEGATE,
    "DEFER": DEFER,
    "ROLLBACK": ROLLBACK,
    "QUARANTINE": QUARANTINE,
    "WORKFLOW": WORKFLOW,
    "GUIDE": GUIDE,
}
_OVR = {
    "critical": OVR_CRITICAL,
    "high": OVR_HIGH,
    "normal": OVR_NORMAL,
    "low": OVR_LOW,
    "none": OVR_NONE,
}
_OVR_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3, "none": 4}


def _rule(decision, ring, priority=0, override="none", catch_all=False):
    return {"decision": decision, "ring": ring, "priority": priority,
            "override": override, "catch_all": catch_all}


def _sort_key(r):
    return (r["ring"], 1 if r.get("catch_all") else 0,
            r["priority"], _OVR_RANK[r["override"]])


# --- pure-Python mirror of the fold's decision table (input pre-sorted) ---


_BLOCKING = ("DENY", "ROLLBACK", "QUARANTINE")


def _fold_sorted_py(rules):
    """Mirror of the Z3 fold, over an already-sorted rule list."""
    has_explicit = any(not r.get("catch_all") for r in rules)
    final = None
    fring = None
    skip = None
    for r in rules:
        d, ring, ovr = r["decision"], r["ring"], r["override"]
        enables = ovr in ("critical", "high")
        if skip is not None and ring == skip:
            continue
        skip = None
        # §7.1 item 6 (global): catch-all inert when any explicit rule matched
        if r.get("catch_all") and has_explicit:
            continue
        if d == "WORKFLOW":
            return "WORKFLOW"
        if d == "EMERGENCY_HALT":
            return "EMERGENCY_HALT"
        if final is not None:
            is_term = d in _BLOCKING
            is_acc = d == "ALLOW" and final == "ALLOW"
            if not enables and not is_term and not is_acc:
                continue
        if d == "ALLOW":
            if enables and final in _BLOCKING:
                final, fring = "ALLOW", ring
                skip = ring
            elif final is None:
                final, fring = "ALLOW", ring
            continue
        if d in _BLOCKING:
            if final is None or final in _BLOCKING:
                final, fring = d, ring
            elif final == "ALLOW":
                if ring > fring or (ring == fring and not enables):
                    final, fring = d, ring
            continue
        if final is None:
            final, fring = d, ring
    return final if final is not None else "ALLOW"


def _z3_resolve(rules):
    """Evaluate the Z3 fold on a concrete (unsorted) rule-set."""
    rules = sorted(rules, key=_sort_key)  # the fold assumes sorted input
    m = ResolutionFold(len(rules))
    final, _ = m.build()
    subs = []
    for i, r in enumerate(rules):
        subs.append((m.dec[i], _DEC[r["decision"]]))
        subs.append((m.ring[i], IntVal(r["ring"])))
        subs.append((m.ovr[i], _OVR[r["override"]]))
        subs.append((m.catch_all[i], BoolVal(r.get("catch_all", False))))
    return str(simplify(substitute(final, *subs)))


# --- differential: reformulation (pure-Python fold) ≡ reference -----------


def test_reformulation_matches_reference_exhaustive():
    """The sorted-array reformulation equals resolve() on exhaustive grids."""
    # n = 2 over the full grid (7 dec × 4 ring × 2 prio × 5 ovr × 2 catch-all).
    atoms = [
        _rule(d, ring, prio, ovr, catch_all)
        for d in list(_DEC)
        for ring in [0, 1, 2, 3]
        for prio in [0, 1]
        for ovr in ["critical", "high", "normal", "low", "none"]
        for catch_all in [False, True]
    ]
    for a, b in itertools.product(atoms, repeat=2):
        rules = [dict(a), dict(b)]
        got = _fold_sorted_py(sorted(rules, key=_sort_key))
        assert got == resolution.resolve(rules), f"{rules!r}"

    # n = 3 over a reduced grid (3 dec × 3 ring × 2 prio × 3 ovr).
    atoms3 = [
        _rule(d, ring, prio, ovr)
        for d in ["ALLOW", "DENY", "EMERGENCY_HALT"]
        for ring in [0, 1, 2]
        for prio in [0, 1]
        for ovr in ["critical", "normal", "none"]
    ]
    for a, b, c in itertools.product(atoms3, repeat=3):
        rules = [dict(a), dict(b), dict(c)]
        got = _fold_sorted_py(sorted(rules, key=_sort_key))
        assert got == resolution.resolve(rules), f"{rules!r}"


def test_reformulation_matches_reference_random():
    """Seeded random n=4 over the full grid."""
    rng = random.Random(20260905)
    decisions = list(_DEC)
    overrides = ["critical", "high", "normal", "low", "none"]
    for _ in range(20000):
        rules = [
            _rule(rng.choice(decisions), rng.randint(0, 3),
                  rng.randint(0, 3), rng.choice(overrides), rng.choice([False, True]))
            for _ in range(4)
        ]
        got = _fold_sorted_py(sorted(rules, key=_sort_key))
        assert got == resolution.resolve(rules), f"{rules!r}"


# --- differential: Z3 transliteration ≡ reference (sample) ----------------


def test_z3_fold_matches_reference_sample():
    """The Z3 fold agrees with resolve() on n=1 full + seeded random n=2..4."""
    # n = 1 over the full grid.
    for d in list(_DEC):
        for ring in [0, 1, 2, 3]:
            for ovr in ["critical", "high", "normal", "low", "none"]:
                rules = [_rule(d, ring, override=ovr)]
                assert _z3_resolve(rules) == resolution.resolve(rules)

    rng = random.Random(20260906)
    decisions = list(_DEC)
    overrides = ["critical", "high", "normal", "low", "none"]
    for n, count in ((2, 250), (3, 250), (4, 250)):
        for _ in range(count):
            rules = [
                _rule(rng.choice(decisions), rng.randint(0, 3),
                      rng.randint(0, 3), rng.choice(overrides), rng.choice([False, True]))
                for _ in range(n)
            ]
            got = _z3_resolve(rules)
            want = resolution.resolve(rules)
            assert got == want, f"{rules!r}: z3={got} ref={want}"


# --- property proofs (UNSAT over the negation) ---------------------------


def test_override_soundness_holds():
    for n in (2, 3, 4):
        holds, model = override_soundness(n)
        assert holds, f"override-soundness violated at n={n}: {model}"


def test_ring_respect_holds():
    for n in (2, 3, 4):
        holds, model = ring_respect(n)
        assert holds, f"ring-respect violated at n={n}: {model}"


def test_emergency_shortcut_holds():
    for n in (2, 3, 4):
        holds, model = emergency_shortcut(n)
        assert holds, f"emergency-shortcut violated at n={n}: {model}"


def test_catch_all_inert_when_explicit_holds():
    for n in (2, 3, 4):
        holds, model = catch_all_inert_when_explicit(n)
        assert holds, f"catch-all-inert-when-explicit violated at n={n}: {model}"


def test_workflow_shortcut_holds():
    for n in (2, 3, 4):
        holds, model = workflow_shortcut(n)
        assert holds, f"workflow-shortcut violated at n={n}: {model}"


# --- non-vacuity: each property's antecedent is reachable ----------------


def _antecedent_sat(n, antecedent):
    m = ResolutionFold(n)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    _, steps = m.build()
    s.add(Or(*[antecedent(st) for st in steps]))
    return s.check() == sat


def test_override_soundness_antecedent_reachable():
    # A same-ring override DENY after an ALLOW genuinely occurs.
    reachable = _antecedent_sat(
        2,
        lambda st: (st["effective"] & st["has_before"] & (st["dec"] == DENY) & st["enables"]
                    & (st["final_before"] == ALLOW)
                    & (st["final_ring_before"] == st["ring"])),
    )
    assert reachable


def test_ring_respect_antecedent_reachable():
    # A higher-ring DENY after a lower-ring ALLOW genuinely occurs.
    reachable = _antecedent_sat(
        2,
        lambda st: (st["effective"] & st["has_before"] & (st["dec"] == DENY)
                    & (st["final_before"] == ALLOW)
                    & (st["ring"] > st["final_ring_before"])),
    )
    assert reachable


def test_emergency_shortcut_antecedent_reachable():
    # EMERGENCY_HALT is hittable (the property is non-vacuous).
    # The "terminal" half is now structural: EMERGENCY_HALT full short-circuits
    # (sets `done`), so a later rule can never even reach `final_before ==
    # EMERGENCY_HALT` — that state is unreachable by construction.
    hit = _antecedent_sat(
        1,
        lambda st: st["term_hit"] & (st["dec"] == EMERGENCY_HALT),
    )
    assert hit
    # and a later rule genuinely CANNOT see an already-set EMERGENCY_HALT:
    terminal_unreachable = not _antecedent_sat(
        2,
        lambda st: st["term_hit"] & st["has_before"] & (st["final_before"] == EMERGENCY_HALT),
    )
    assert terminal_unreachable


def test_catch_all_inert_when_explicit_antecedent_reachable():
    # A catch-all rule genuinely takes effect when NO explicit rule is present
    # (so the inert-when-explicit property is non-vacuous in the reachable
    # direction: catch-all rules do fire in an all-catch-all matched set).
    reachable = _antecedent_sat(
        2,
        lambda st: st["effective"] & st["catch_all"],
    )
    assert reachable


def test_workflow_shortcut_antecedent_reachable():
    reachable = _antecedent_sat(
        1,
        lambda st: st["term_hit"] & (st["dec"] == WORKFLOW),
    )
    assert reachable
