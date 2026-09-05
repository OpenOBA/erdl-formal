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

"""Symbolic resolution model (§9) — Z3 encoding of rule resolution.

`resolution.resolve` is a hand-written reference model of the resolution
semantics (ring order 0→3, priority ascending, override DENY→ALLOW only,
EMERGENCY_HALT short-circuit). Its ERDL-specific properties were previously
"verified" by 10 handwritten unit tests — sampling, not proof.

This module encodes the *same* semantics as Z3 constraints over a *bounded*
rule-set, so the properties can be proven over ALL rule-sets (UNSAT over the
negation). Any SAT counterexample is a concrete, replayable rule-set that can
be fed back into the real engine for cross-validation.

Faithfulness (no divergence between this Z3 model and the reference) is
guaranteed by ``tests/test_resolution_smt.py``, which exhaustively cross-checks
the Z3 fold against ``resolution.resolve`` over a finite rule-set space
(differential verification) — the same "proof + differential, double
insurance" the README claims for the expression kernel.
"""

from z3 import (
    And,
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
    ("ALLOW", "DENY", "EMERGENCY_HALT", "CORRECT", "REQUEST_HUMAN", "ESCALATE", "NOTIFY"),
)
(
    ALLOW, DENY, EMERGENCY_HALT, CORRECT, REQUEST_HUMAN, ESCALATE, NOTIFY,
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


class ResolutionFold:
    """Symbolic encoding of ``resolution.resolve`` over ``n`` rules.

    The ``n`` rules are modelled as free variables. ``sorted_premise()``
    constrains the array to resolve()'s processing order (ring ascending, then
    priority ascending, then override-rank ascending). Because ``resolve``
    groups by ring and sorts internally, it is permutation-invariant — so
    proving a property over *sorted* arrays is equivalent to proving it over
    all rule-sets.

    ``build()`` runs the fold and returns the final decision plus per-step
    transition records, which the property proofs use to express "bad
    transition" conditions.
    """

    def __init__(self, n, prio_max=None):
        assert n >= 1
        self.n = n
        self.prio_max = n - 1 if prio_max is None else prio_max
        self.dec = [Const(f"dec_{i}", Decision) for i in range(n)]
        self.ring = [Int(f"ring_{i}") for i in range(n)]
        self.prio = [Int(f"prio_{i}") for i in range(n)]
        self.ovr = [Const(f"ovr_{i}", Override) for i in range(n)]

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
        """Array is in resolve()'s processing order (ring, priority, rank)."""
        cs = []
        for i in range(self.n - 1):
            a, b = i, i + 1
            cs.append(self.ring[a] <= self.ring[b])
            cs.append(If(self.ring[a] == self.ring[b],
                         self.prio[a] <= self.prio[b], True))
            cs.append(If(And(self.ring[a] == self.ring[b],
                             self.prio[a] == self.prio[b]),
                         override_rank(self.ovr[a]) <= override_rank(self.ovr[b]), True))
        return cs

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

        steps = []
        for i in range(self.n):
            dec, ring, ovr = self.dec[i], self.ring[i], self.ovr[i]
            enables = override_enables(ovr)

            # A prior `break` skips every remaining rule of the SAME ring; the
            # skip clears once the (sorted) array moves to a higher ring.
            process = Or(Not(skip), ring > sring)
            # §7.1 gate: a non-override, non-terminating rule cannot change an
            # already-set decision (ALLOW may keep accumulating onto ALLOW).
            gate_pass = Or(
                Not(has),
                enables,
                dec == DENY,
                dec == EMERGENCY_HALT,
                And(dec == ALLOW, has, fin == ALLOW),
            )
            effective = And(process, gate_pass)

            allow_relax = And(dec == ALLOW, enables, has, fin == DENY)
            allow_init = And(dec == ALLOW, Not(has))
            halt = dec == EMERGENCY_HALT
            deny_set = And(dec == DENY, Or(Not(has), fin == DENY))
            deny_tighten = And(
                dec == DENY, has, fin == ALLOW,
                Or(ring > fring, And(ring == fring, Not(enables))),
            )
            # soft decisions (CORRECT / REQUEST_HUMAN / ESCALATE / NOTIFY)
            # only accumulate when nothing is set yet.

            fin_before, fring_before = fin, fring

            new_has = Or(has, effective)

            new_fin = If(
                Not(effective), fin,
                If(dec == ALLOW,
                    If(Or(allow_relax, allow_init), ALLOW, fin),
                If(dec == EMERGENCY_HALT,
                    EMERGENCY_HALT,
                If(dec == DENY,
                    If(Or(deny_set, deny_tighten), DENY, fin),
                    If(Not(has), dec, fin)))))

            new_fring = If(
                Not(effective), fring,
                If(dec == ALLOW,
                    If(Or(allow_relax, allow_init), ring, fring),
                If(dec == EMERGENCY_HALT,
                    ring,
                If(dec == DENY,
                    If(Or(deny_set, deny_tighten), ring, fring),
                    If(Not(has), ring, fring)))))

            breaks = Or(allow_relax, halt)
            new_skip = If(Not(process), skip, If(breaks, BoolVal(True), BoolVal(False)))
            new_sring = If(Not(process), sring, If(breaks, ring, sring))

            steps.append({
                "i": i,
                "dec": dec, "ring": ring, "ovr": ovr, "enables": enables,
                "effective": effective,
                "has_before": has,
                "final_before": fin_before, "final_ring_before": fring_before,
                "final_after": new_fin, "final_ring_after": new_fring,
            })

            has, fin, fring, skip, sring = new_has, new_fin, new_fring, new_skip, new_sring

        final = If(has, fin, ALLOW)
        return final, steps


# --- property proofs -----------------------------------------------------


def _prove(n, bad_terms):
    """UNSAT over the bad terms ⇒ property holds for ALL rule-sets of size ≤ n.

    Returns ``(holds, model)``: ``holds=True`` when UNSAT; otherwise a concrete
    counterexample model is returned for replay.
    """
    m = ResolutionFold(n)
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
    """override 仅 DENY→ALLOW 方向：同环 override DENY 不把 ALLOW 收紧为 DENY。

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
    """ring 顺序在 DENY 方向被尊重：高环 DENY 覆盖低环 ALLOW（高环权威）。

    Rings give authority ordering: a *higher*-ring DENY must tighten a
    lower-ring ALLOW. A DENY that failed to do so would violate the ring
    ordering (the property's negation).
    """
    def bad(steps):
        return [And(st["effective"], st["has_before"], st["dec"] == DENY,
                    st["final_before"] == ALLOW,
                    st["ring"] > st["final_ring_before"],
                    st["final_after"] != DENY) for st in steps]
    return _prove(n, bad)


def emergency_shortcut(n=4):
    """EMERGENCY_HALT 命中即短路，且为终态不可被后续规则改写。"""
    def bad(steps):
        hit_not_final = [And(st["effective"], st["dec"] == EMERGENCY_HALT,
                             st["final_after"] != EMERGENCY_HALT) for st in steps]
        not_terminal = [And(st["effective"], st["has_before"],
                            st["final_before"] == EMERGENCY_HALT,
                            st["final_after"] != EMERGENCY_HALT) for st in steps]
        return hit_not_final + not_terminal
    return _prove(n, bad)
