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

"""Symbolic resolution model (§7.1) — Z3 encoding of rule resolution.

`resolution.resolve` is a hand-written reference model of the resolution
semantics (ring order 0→3, priority ascending, override DENY→ALLOW only,
EMERGENCY_HALT / WORKFLOW full short-circuit, and the §7.1 item 6 *global*
catch-all fallback). Its ERDL-specific properties were previously "verified"
by handwritten unit tests — sampling, not proof.

This module encodes the *same* semantics as Z3 constraints over a *bounded*
rule-set, so the properties can be proven over ALL rule-sets (UNSAT over the
negation). Any SAT counterexample is a concrete, replayable rule-set that can
be fed back into the real engine for cross-validation.

Faithfulness (no divergence between this Z3 model and the reference) is
guaranteed by ``tests/test_resolution_smt.py``, which exhaustively cross-checks
the Z3 fold against ``resolution.resolve`` over a finite rule-set space
(differential verification) — the same "proof + differential, double
insurance" the README claims for the expression kernel.

The decision domain is the full SPEC §6 13-type set. The fold classifies them:

- **terminal** — EMERGENCY_HALT / WORKFLOW: full short-circuit on hit (SPEC
  §7.0.2 "命中即短路" / §6 state machine).
- **restrictive polarity** — DENY / ROLLBACK / QUARANTINE: tighten an ALLOW.
- **permissive** — ALLOW.
- **advisory / human-flow** — CORRECT / NOTIFY / REQUEST_HUMAN / ESCALATE /
  DELEGATE / DEFER / GUIDE: accumulate only when nothing is set yet.
"""

from z3 import (
    And,
    Bool,
    BoolVal,
    Const,
    EnumSort,
    If,
    Int,
    IntVal,
    Not,
    Or,
    Solver,
    sat,
    unsat,
)

# --- decision / override domains -----------------------------------------

Decision, _decision_consts = EnumSort(
    "Decision",
    (
        "ALLOW", "DENY", "CORRECT", "NOTIFY", "REQUEST_HUMAN", "ESCALATE",
        "DELEGATE", "DEFER", "EMERGENCY_HALT", "ROLLBACK", "QUARANTINE",
        "WORKFLOW", "GUIDE",
    ),
)
(
    ALLOW, DENY, CORRECT, NOTIFY, REQUEST_HUMAN, ESCALATE,
    DELEGATE, DEFER, EMERGENCY_HALT, ROLLBACK, QUARANTINE,
    WORKFLOW, GUIDE,
) = _decision_consts

Override, _override_consts = EnumSort(
    "Override",
    ("critical", "high", "normal", "low", "none"),
)
(
    OVR_CRITICAL, OVR_HIGH, OVR_NORMAL, OVR_LOW, OVR_NONE,
) = _override_consts


def override_enables(ovr):
    """critical / high enable the override mechanism (matches resolution.py)."""
    return Or(ovr == OVR_CRITICAL, ovr == OVR_HIGH)


def override_rank(ovr):
    """Sort tie-break rank: critical=0 … none=4 (matches resolution.py)."""
    return If(
        ovr == OVR_CRITICAL, 0,
        If(ovr == OVR_HIGH, 1,
        If(ovr == OVR_NORMAL, 2,
        If(ovr == OVR_LOW, 3, 4))))


def is_restrictive(dec):
    """Restrictive-polarity decisions: DENY + its action variants ROLLBACK / QUARANTINE."""
    return Or(dec == DENY, dec == ROLLBACK, dec == QUARANTINE)


class ResolutionFold:
    """Symbolic encoding of ``resolution.resolve`` over ``n`` rules.

    The ``n`` rules are modelled as free variables. ``sorted_premise()``
    constrains the array to resolve()'s processing order (ring ascending, then
    catch-all last within ring, then priority ascending, then override-rank
    ascending).

    NOTE on permutation-invariance: resolve() is *not* fully
    permutation-invariant — advisory decisions (CORRECT / REQUEST_HUMAN / …)
    are order-sensitive because the first one to reach an unset decision wins.
    The sorted_premise therefore encodes a fixed definition order, and the
    properties are proven over sorted arrays (the fold's input contract), not
    over arbitrary permutations. This is an explicit modelling boundary, not a
    hidden assumption.

    ``build()`` runs the fold and returns the final decision plus per-step
    transition records, which the property proofs use to express "bad
    transition" conditions.
    """

    def __init__(self, n, prio_max=None, gate="global"):
        assert n >= 1
        self.n = n
        self.prio_max = n - 1 if prio_max is None else prio_max
        self.gate = gate
        self.dec = [Const(f"dec_{i}", Decision) for i in range(n)]
        self.ring = [Int(f"ring_{i}") for i in range(n)]
        self.prio = [Int(f"prio_{i}") for i in range(n)]
        self.ovr = [Const(f"ovr_{i}", Override) for i in range(n)]
        self.catch_all = [Bool(f"catch_all_{i}") for i in range(n)]

    # -- constraints ------------------------------------------------------

    def domain_constraints(self):
        """ring ∈ [0,3], priority ∈ [0, prio_max]."""
        cs = []
        for i in range(self.n):
            cs.append(self.ring[i] >= 0)
            cs.append(self.ring[i] <= 3)
            cs.append(self.prio[i] >= 0)
            cs.append(self.prio[i] <= self.prio_max)
        return cs

    def sorted_premise(self):
        """Array is in resolve()'s processing order.

        Within a ring: catch-all (empty-condition) rules sort LAST, then
        priority ascending, then override-rank ascending.
        """
        cs = []
        for i in range(self.n - 1):
            a, b = i, i + 1
            cs.append(self.ring[a] <= self.ring[b])
            # catch-all sorts last: False (explicit) before True (catch-all)
            cs.append(If(self.ring[a] == self.ring[b],
                         Or(Not(self.catch_all[a]), self.catch_all[b]), True))
            cs.append(If(And(self.ring[a] == self.ring[b],
                             self.catch_all[a] == self.catch_all[b]),
                         self.prio[a] <= self.prio[b], True))
            cs.append(If(And(self.ring[a] == self.ring[b],
                             self.catch_all[a] == self.catch_all[b],
                             self.prio[a] == self.prio[b]),
                         override_rank(self.ovr[a]) <= override_rank(self.ovr[b]), True))
        return cs

    def has_explicit(self):
        """Global §7.1 item 6 premise: some explicit-condition rule is present."""
        return Or(*[Not(self.catch_all[i]) for i in range(self.n)])

    def has_explicit_same_ring(self, i):
        """Some *other* explicit-condition rule shares rule ``i``'s ring."""
        return Or(*[And(Not(self.catch_all[j]), self.ring[j] == self.ring[i])
                    for j in range(self.n) if j != i])

    def has_explicit_same_priority(self, i):
        """Some *other* explicit-condition rule shares rule ``i``'s priority."""
        return Or(*[And(Not(self.catch_all[j]), self.prio[j] == self.prio[i])
                    for j in range(self.n) if j != i])

    def catch_all_gate(self, i):
        """§7.1 item 6 eligibility gate for rule ``i``.

        ``self.gate`` selects the intended semantics or a deliberately-broken
        mutant, for mutation testing. Each mutant must be *detected* by
        ``catch_all_inert_when_explicit`` (i.e. produce a counterexample) —
        otherwise the property merely restates the gate instead of detecting
        violations.
        """
        catch_all = self.catch_all[i]
        if self.gate == "none":
            # eligibility gate removed: a catch-all always takes effect
            return BoolVal(True)
        if self.gate == "invert":
            # has_explicit inverted: catch-all takes effect only when an
            # explicit rule IS present (backwards fallback)
            return Or(Not(catch_all), self.has_explicit())
        if self.gate == "same_ring":
            # suppression limited to explicit matches in the same ring
            return Or(Not(catch_all), Not(self.has_explicit_same_ring(i)))
        if self.gate == "same_priority":
            # suppression limited to explicit matches at the same priority
            return Or(Not(catch_all), Not(self.has_explicit_same_priority(i)))
        # global (intended): catch-all effective only when NO explicit rule exists
        return Or(Not(catch_all), Not(self.has_explicit()))

    # -- the fold ---------------------------------------------------------

    def build(self):
        """Run the fold; return ``(final, steps)``.

        ``final`` is the final decision as a Z3 ``Decision`` term. ``steps`` is
        a list of per-position dicts recording the before/after state and the
        rule identity, for the property proofs.
        """
        has = BoolVal(False)
        fin = ALLOW           # arbitrary while has=False (guarded by `has`)
        fring = IntVal(0)
        skip = BoolVal(False)  # in break mode: skip the rest of the current ring
        sring = IntVal(0)
        done = BoolVal(False)  # terminal short-circuit (WORKFLOW / EMERGENCY_HALT)

        has_explicit = self.has_explicit()

        steps = []
        for i in range(self.n):
            dec, ring, ovr, catch_all = self.dec[i], self.ring[i], self.ovr[i], self.catch_all[i]
            enables = override_enables(ovr)
            blocking = is_restrictive(dec)

            # A prior `break` skips every remaining rule of the SAME ring; the
            # skip clears once the (sorted) array moves to a higher ring.
            process = Or(Not(skip), ring > sring)
            # §7.1 item 6 (global): a catch-all rule takes effect only when NO
            # explicit-condition rule is present anywhere in the matched set.
            catch_all_ok = self.catch_all_gate(i)

            # Terminal decisions short-circuit the whole resolve (SPEC §7.0.2
            # "命中即短路" for EMERGENCY_HALT; §6 state machine for WORKFLOW),
            # BEFORE the §7.1 gate — they return immediately in the reference.
            terminate = Or(dec == WORKFLOW, dec == EMERGENCY_HALT)
            term_hit = And(Not(done), process, terminate, catch_all_ok)

            # §7.1 gate for non-terminal rules: a non-override, non-terminating
            # rule cannot change an already-set decision (ALLOW may accumulate).
            gate_pass = Or(
                Not(has),
                enables,
                blocking,
                And(dec == ALLOW, has, fin == ALLOW),
            )
            effective = And(Not(done), process, Not(terminate), gate_pass, catch_all_ok)

            allow_relax = And(dec == ALLOW, enables, has, is_restrictive(fin))
            allow_init = And(dec == ALLOW, Not(has))
            blocking_set = And(blocking, Or(Not(has), is_restrictive(fin)))
            blocking_tighten = And(
                blocking, has, fin == ALLOW,
                Or(ring > fring, And(ring == fring, Not(enables))),
            )

            fin_before, fring_before = fin, fring

            new_has = Or(has, term_hit, effective)

            new_fin = If(
                term_hit, dec,  # WORKFLOW or EMERGENCY_HALT (both terminal)
                If(Not(effective), fin,
                    If(dec == ALLOW,
                        If(Or(allow_relax, allow_init), ALLOW, fin),
                    If(blocking,
                        If(Or(blocking_set, blocking_tighten), dec, fin),
                        If(Not(has), dec, fin)))))

            new_fring = If(
                term_hit, ring,
                If(Not(effective), fring,
                    If(dec == ALLOW,
                        If(Or(allow_relax, allow_init), ring, fring),
                    If(blocking,
                        If(Or(blocking_set, blocking_tighten), ring, fring),
                        If(Not(has), ring, fring)))))

            # only override-ALLOW relax breaks the ring; terminal decisions use `done`.
            breaks = And(effective, allow_relax)
            new_skip = If(Not(process), skip, If(breaks, BoolVal(True), BoolVal(False)))
            new_sring = If(Not(process), sring, If(breaks, ring, sring))
            new_done = Or(done, term_hit)

            steps.append({
                "i": i,
                "dec": dec, "ring": ring, "ovr": ovr, "enables": enables,
                "catch_all": catch_all,
                "has_explicit": has_explicit,
                "term_hit": term_hit,
                "effective": effective,
                "has_before": has,
                "final_before": fin_before, "final_ring_before": fring_before,
                "final_after": new_fin, "final_ring_after": new_fring,
            })

            has, fin, fring, skip, sring, done = new_has, new_fin, new_fring, new_skip, new_sring, new_done

        final = If(has, fin, ALLOW)
        return final, steps


# --- property proofs -----------------------------------------------------


def _prove(n, bad_terms, gate="global"):
    """UNSAT over the bad terms ⇒ property holds for ALL rule-sets of size ≤ n.

    Returns ``(holds, model)``: ``holds=True`` when UNSAT; otherwise a concrete
    counterexample model is returned for replay. ``gate`` selects the intended
    catch-all gate or a mutant (mutation testing).
    """
    m = ResolutionFold(n, gate=gate)
    s = Solver()
    for c in m.domain_constraints() + m.sorted_premise():
        s.add(c)
    _, steps = m.build()
    s.add(Or(*bad_terms(steps)))
    r = s.check()
    if r == unsat:
        return True, None
    return False, s.model()


def override_soundness(n=4):
    """override only relaxes DENY→ALLOW: a same-ring override DENY never tightens ALLOW into DENY.

    The only way a DENY tightens ALLOW is ``ring > final_ring`` (ring order) or
    ``ring == final_ring and not override_enables`` — so an override-enabled
    DENY at the SAME ring can never tighten (the "unsafe direction" the
    reference blocks). The cross-ring case is ring-driven, not override-driven.
    """
    def bad(steps):
        return [And(st["effective"], st["has_before"], st["dec"] == DENY, st["enables"],
                    st["final_before"] == ALLOW,
                    st["final_ring_before"] == st["ring"],
                    st["final_after"] == DENY) for st in steps]
    return _prove(n, bad)


def ring_respect(n=4):
    """ring order is honored in the DENY direction: a higher-ring *explicit* DENY overrides a lower-ring ALLOW.

    Rings give authority ordering: a *higher*-ring explicit-condition DENY must
    tighten a lower-ring ALLOW. A catch-all (empty-condition) DENY is inert
    whenever any explicit rule exists (§7.1 item 6), so it is excluded here
    (its inertness is asserted separately by ``catch_all_inert_when_explicit``).
    """
    def bad(steps):
        return [And(st["effective"], st["has_before"], st["dec"] == DENY,
                    Not(st["catch_all"]),
                    st["final_before"] == ALLOW,
                    st["ring"] > st["final_ring_before"],
                    st["final_after"] != DENY) for st in steps]
    return _prove(n, bad)


def catch_all_inert_when_explicit(n=4, gate="global"):
    """§7.1 item 6 (global): a catch-all rule never takes effect when any
    explicit-condition rule is present in the matched set.

    This is the property that closes the "relax direction" gap ANP2 flagged,
    stated in its *global* form: a fallback rule carries the weak, general
    intent of "all other cases"; it MUST NOT rewrite the strong, specific
    decision established by an explicit-condition rule — regardless of ring or
    override. Over the intended fold (``gate="global"``) this is
    UNSAT-by-construction (encoded directly as ``catch_all_ok``); mutation
    testing (``gate=`` a mutant) proves it is a genuine *detector* rather than
    a restatement — each broken gate must yield a counterexample. The
    non-vacuity check (a catch-all rule is reachable when no explicit rule
    exists) is asserted in the tests.
    """
    def bad(steps):
        return [And(st["effective"], st["catch_all"], st["has_explicit"]) for st in steps]
    return _prove(n, bad, gate=gate)


def emergency_shortcut(n=4):
    """EMERGENCY_HALT short-circuits on hit (full resolve), and is terminal (no later rule can rewrite it)."""
    def bad(steps):
        hit_not_final = [And(st["term_hit"], st["dec"] == EMERGENCY_HALT,
                             st["final_after"] != EMERGENCY_HALT) for st in steps]
        not_terminal = [And(st["effective"], st["has_before"],
                            st["final_before"] == EMERGENCY_HALT,
                            st["final_after"] != EMERGENCY_HALT) for st in steps]
        return hit_not_final + not_terminal
    return _prove(n, bad)


def workflow_shortcut(n=4):
    """WORKFLOW short-circuits into its state machine on hit (full resolve), and is terminal."""
    def bad(steps):
        hit_not_final = [And(st["term_hit"], st["dec"] == WORKFLOW,
                             st["final_after"] != WORKFLOW) for st in steps]
        not_terminal = [And(st["effective"], st["has_before"],
                            st["final_before"] == WORKFLOW,
                            st["final_after"] != WORKFLOW) for st in steps]
        return hit_not_final + not_terminal
    return _prove(n, bad)
