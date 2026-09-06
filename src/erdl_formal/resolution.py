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

"""Rule resolution reference model (§7.1 + erdl-landing evaluator.ts).

Models the resolution semantics: ring order (0→3), priority ascending, override
(DENY→ALLOW only), EMERGENCY_HALT short-circuit, WORKFLOW state-machine
short-circuit, and the §7.1 item 6 catch-all semantics.

A rule here is a dict: {name, priority, ring, override, decision, catch_all};
all rules are assumed to MATCH (this models resolution, not condition
matching). ``catch_all`` (default False) marks an empty-condition rule.

Decision domain = SPEC §6's 13 types. The resolution fold classifies them as:

- **restrictive polarity** — DENY / ROLLBACK / QUARANTINE: tighten an ALLOW
  (ROLLBACK/QUARANTINE are deny action-variants; they were previously mis-
  modeled as soft-accumulate, so an ALLOW could not be rolled back — P2).
- **terminal** — EMERGENCY_HALT: fail-closed brake; short-circuits at ring 0.
- **state machine** — WORKFLOW: short-circuits into its own workflow on hit.
- **permissive** — ALLOW.
- **advisory / human-flow** — CORRECT / NOTIFY / REQUEST_HUMAN / ESCALATE /
  DELEGATE / DEFER / GUIDE: accumulate only when nothing is set yet.

§7.1 item 6 (catch-all) is modeled as a *global* gate: a catch-all rule takes
effect only when **no** explicit-condition rule matched (i.e. the matched set
contains no ``catch_all=False`` rule). This is stronger than the earlier
per-ring "catch-all sorts last" reading — a catch-all in ring 0 must not preempt
an explicit rule in ring 3 (the "global last" semantics).
"""

_OVERRIDE_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3}

# Restrictive-polarity decisions (SPEC §6): DENY + its action variants ROLLBACK /
# QUARANTINE. These tighten an established ALLOW. EMERGENCY_HALT is terminal and
# handled separately; WORKFLOW short-circuits into its state machine.
# Consolidated 2026-09-06 — previously only DENY/EMERGENCY_HALT were terminating;
# ROLLBACK/QUARANTINE fell into soft-accumulate and could never override ALLOW (P2).
BLOCKING_DECISIONS = ("DENY", "ROLLBACK", "QUARANTINE")


def override_enables(rule):
    return rule.get("override") in ("critical", "high")


def _override_rank(rule):
    return _OVERRIDE_RANK.get(rule.get("override"), 4)


def resolve(rules):
    """Return the final decision for a matched rule set (evaluator.ts semantics)."""
    # §7.1 item 6 (global): a catch-all rule takes effect only when NO explicit-
    # condition rule matched. So the whole catch-all population is inert whenever
    # any explicit rule is present — regardless of ring, priority or override.
    has_explicit = any(not r.get("catch_all") for r in rules)

    by_ring = {}
    for r in rules:
        by_ring.setdefault(r.get("ring", 3), []).append(r)

    final = None
    final_ring = None

    for ring in sorted(by_ring):
        ring_rules = sorted(by_ring[ring], key=lambda r: (
            (1 if r.get("catch_all") else 0), r["priority"], _override_rank(r),
        ))
        for r in ring_rules:
            d = r["decision"]

            # §7.1 item 6: a catch-all rule never takes effect when any explicit
            # rule matched (global fallback, not per-ring last).
            if r.get("catch_all") and has_explicit:
                continue

            # WORKFLOW (SPEC §6): hit short-circuits into the state machine,
            # before the §7.1 gate (matches evaluator.ts ordering).
            if d == "WORKFLOW":
                return "WORKFLOW"

            # EMERGENCY_HALT (SPEC §7.0.2): 命中即短路 — full short-circuit on hit,
            # regardless of ring. (The earlier "only ring 0 returns" was a partial
            # implementation of the spec's full short-circuit; WORKFLOW's short-circuit
            # exposed that a ring!=0 EMERGENCY_HALT could be rewritten by a later
            # terminal decision.)
            if d == "EMERGENCY_HALT":
                return "EMERGENCY_HALT"

            # Sec. 7.1 gate: non-override non-terminating rules can't change a decision
            if final is not None:
                is_terminating = d in BLOCKING_DECISIONS
                is_allow_accum = d == "ALLOW" and final == "ALLOW"
                if not override_enables(r) and not is_terminating and not is_allow_accum:
                    continue

            if d == "ALLOW":
                # override ALLOW covers a prior restrictive decision -> ALLOW
                # (safe relax, cross-ring).
                if override_enables(r) and final in BLOCKING_DECISIONS:
                    final, final_ring = "ALLOW", ring
                    break  # override takes effect, stop evaluating this ring
                if final is None:
                    final, final_ring = "ALLOW", ring
                continue

            if d in BLOCKING_DECISIONS:
                # A restrictive decision (DENY/ROLLBACK/QUARANTINE) tightens an
                # ALLOW; among restrictive decisions the ring-major last one wins.
                if final is None or final in BLOCKING_DECISIONS:
                    final, final_ring = d, ring
                elif final == "ALLOW":
                    if ring > final_ring or (ring == final_ring and not override_enables(r)):
                        # higher-ring restrictive, or same-ring non-override restrictive
                        # → overrides ALLOW
                        final, final_ring = d, ring
                    # same-ring override restrictive cannot override ALLOW (unsafe direction)
                # restrictive cannot override EMERGENCY_HALT / WORKFLOW / advisory decisions
                continue

            # CORRECT / NOTIFY / REQUEST_HUMAN / ESCALATE / DELEGATE / DEFER / GUIDE:
            # advisory & human-flow decisions accumulate only when nothing is set yet.
            if final is None:
                final, final_ring = d, ring
            continue

    return final if final is not None else "ALLOW"
