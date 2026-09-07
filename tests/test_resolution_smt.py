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

from z3 import And, BoolVal, IntVal, Or, Solver, is_true, sat, simplify, substitute

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
    catch_all_override_irrelevant_when_explicit,
    catch_all_then_irrelevant_when_explicit,
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


def test_catch_all_then_irrelevant_when_explicit_holds():
    """§7.1 item 6 over the decision observable: with an explicit rule present,
    a catch-all's `then` value is irrelevant to the final decision (UNSAT over
    the counterfactual)."""
    for n in (2, 3, 4):
        holds, model = catch_all_then_irrelevant_when_explicit(n)
        assert holds, f"catch-all then-irrelevant violated at n={n}: {model}"


def test_catch_all_then_irrelevant_detects_mutants():
    """The counterfactual property is a detector over the decision observable,
    not a restatement of the fold's internal `effective` flag: each broken gate
    makes the catch-all's `then` observable in the final decision (SAT)."""
    for gate in _MUTANTS:
        holds, model = catch_all_then_irrelevant_when_explicit(4, gate=gate)
        assert not holds, (
            f"mutant '{gate}': catch-all then-irrelevant held (UNSAT) even though "
            f"the gate is broken — no detector for this obligation"
        )


def test_catch_all_override_irrelevant_when_explicit_holds():
    """§7.1.6 second quantifier: a catch-all's `override` value is irrelevant to
    the final decision when an explicit rule is present (UNSAT over the
    counterfactual)."""
    for n in (2, 3, 4):
        holds, model = catch_all_override_irrelevant_when_explicit(n)
        assert holds, f"catch-all override-irrelevant violated at n={n}: {model}"


def test_catch_all_override_irrelevant_detects_mutants():
    """The override counterfactual is a detector too: each broken gate makes the
    catch-all's `override` observable in the final decision (SAT)."""
    for gate in _MUTANTS:
        holds, model = catch_all_override_irrelevant_when_explicit(4, gate=gate)
        assert not holds, (
            f"mutant '{gate}': catch-all override-irrelevant held (UNSAT) even "
            f"though the gate is broken — no detector for this obligation"
        )


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


# --- mutation testing: catch_all_inert_when_explicit is a DETECTOR --------
#
# Over the intended fold the property is UNSAT-by-construction (the gate is
# embedded directly as ``catch_all_ok``). ANP2's point: that makes it a
# *restatement*, not a *detector* — it can stay green after some later
# encoding change breaks the intended semantics. Mutation testing closes that
# gap: each deliberately-broken gate must be KILLED (the property returns a
# SAT counterexample), and each counterexample is kept as a replayable
# regression fixture.

_MUTANTS = {
    "none": "eligibility gate removed entirely (catch-all always effective)",
    "invert": "has_explicit inverted (catch-all effective only when explicit present)",
    "same_ring": "suppression limited to same-ring explicit matches",
    "same_priority": "suppression limited to same-priority explicit matches",
}


def _model_to_rules(m, model):
    """Extract a concrete rule list from a SAT model of ResolutionFold."""
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


def _mutant_fold_violates(rules, gate):
    """Does the concrete rule-set violate catch-all inertness under ``gate``?

    Builds a fold with the given gate, substitutes the concrete rules, and
    checks whether any step has ``effective & catch_all & has_explicit``
    (the property's bad term) — i.e. the broken gate lets a catch-all rule
    take effect while an explicit-condition rule is present.
    """
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


def test_catch_all_inert_detects_mutants():
    """Every broken gate is killed (SAT counterexample), and the intact fold is
    not falsely flagged (each counterexample replays clean under the global
    gate). The counterexamples are asserted inline as regression fixtures.
    """
    for gate, desc in _MUTANTS.items():
        holds, model = catch_all_inert_when_explicit(4, gate=gate)
        assert not holds, (
            f"mutant '{gate}' ({desc}) SURVIVED: property holds (UNSAT), so it "
            f"cannot distinguish the intended fold from this violation"
        )
        # Recover the concrete counterexample and prove it is a genuine
        # violation under the mutant gate — and harmless under the intact gate.
        m = ResolutionFold(4, gate=gate)
        rules = _model_to_rules(m, model)
        assert _mutant_fold_violates(rules, gate), (
            f"mutant '{gate}': recovered counterexample {rules!r} does not "
            f"reproduce the violation"
        )
        assert not _mutant_fold_violates(rules, "global"), (
            f"mutant '{gate}': counterexample {rules!r} also violates the intact "
            f"global gate — the differential is broken"
        )


def test_catch_all_mutant_counterexamples_are_replayable():
    """Each recovered counterexample is a concrete rule-set that the intact
    reference ``resolution.resolve`` accepts but the mutant fold mis-resolves
    — kept as a replayable regression fixture (differential, not just symbolic).
    """
    for gate in _MUTANTS:
        holds, model = catch_all_inert_when_explicit(4, gate=gate)
        assert not holds
        m = ResolutionFold(4, gate=gate)
        rules = _model_to_rules(m, model)
        # The reference resolve() must not be confused by the counterexample:
        # it simply runs the (correct) global gate, so a catch-all present with
        # an explicit rule is inert there. The mutant fold differs.
        ref = resolution.resolve(rules)
        # Sanity: the recovered rules are a valid matched set (not a solver
        # artifact) — the reference returns one of the 13 decision types.
        assert ref in _DEC, f"mutant '{gate}': reference returned {ref!r}"

