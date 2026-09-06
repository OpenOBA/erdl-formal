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

"""ERDL-specific properties via the rule resolution reference model.

override-soundness / ring-respect / emergency-shortcut (with the
ring-respect CORRECTION discovered from evaluator.ts).
"""

from erdl_formal.resolution import resolve


def _r(name, decision, priority, ring=3, override=None, catch_all=False):
    return {"name": name, "decision": decision, "priority": priority,
            "ring": ring, "override": override, "catch_all": catch_all}


def test_override_allow_relaxes_deny():
    # Ring 0 DENY overridden by a Ring 3 override-critical ALLOW (DENY→ALLOW, cross-ring)
    rules = [
        _r("base-deny", "DENY", 10, ring=0),
        _r("exception-allow", "ALLOW", 20, ring=3, override="critical"),
    ]
    assert resolve(rules) == "ALLOW"


def test_override_deny_cannot_tighten_allow():
    # Same-ring override DENY after ALLOW is popped (unsafe ALLOW→DENY direction blocked)
    rules = [
        _r("base-allow", "ALLOW", 10, ring=0),
        _r("override-deny", "DENY", 20, ring=0, override="critical"),
    ]
    assert resolve(rules) == "ALLOW"


def test_ring_respect_higher_ring_deny_overrides_lower_allow():
    # Higher-ring DENY overrides a lower-ring ALLOW (ring order respected, tighten)
    rules = [
        _r("lower-allow", "ALLOW", 10, ring=0),
        _r("higher-deny", "DENY", 20, ring=1),
    ]
    assert resolve(rules) == "DENY"


def test_emergency_halt_short_circuits():
    # Ring 0 EMERGENCY_HALT short-circuits — the later override ALLOW never evaluates
    rules = [
        _r("halt", "EMERGENCY_HALT", 10, ring=0),
        _r("late-allow", "ALLOW", 20, ring=3, override="critical"),
    ]
    assert resolve(rules) == "EMERGENCY_HALT"


def test_default_allow_when_nothing_matches():
    assert resolve([]) == "ALLOW"


def test_priority_ordering_lower_number_wins():
    rules = [
        _r("p10-deny", "DENY", 10, ring=0),
        _r("p20-allow", "ALLOW", 20, ring=0),
    ]
    assert resolve(rules) == "DENY"


def test_same_ring_higher_priority_deny_overrides_allow():
    rules = [
        _r("allow", "ALLOW", 20, ring=0),
        _r("deny", "DENY", 10, ring=0),
    ]
    assert resolve(rules) == "DENY"


def test_multiple_deny_rules():
    rules = [
        _r("deny-a", "DENY", 10, ring=0),
        _r("deny-b", "DENY", 20, ring=1),
    ]
    assert resolve(rules) == "DENY"


def test_emergency_halt_non_root_ring_breaks():
    # EMERGENCY_HALT at ring != 0 sets final then breaks (only ring 0 returns early)
    rules = [_r("halt", "EMERGENCY_HALT", 10, ring=3)]
    assert resolve(rules) == "EMERGENCY_HALT"


def test_rollback_tightens_allow():
    # P2: ROLLBACK is a restrictive (blocking) decision and must tighten an ALLOW.
    rules = [
        _r("base-allow", "ALLOW", 10, ring=0),
        _r("rollback", "ROLLBACK", 20, ring=1),
    ]
    assert resolve(rules) == "ROLLBACK"


def test_quarantine_tightens_allow():
    # P2: QUARANTINE is a restrictive (blocking) decision and must tighten an ALLOW.
    rules = [
        _r("base-allow", "ALLOW", 10, ring=0),
        _r("quarantine", "QUARANTINE", 20, ring=1),
    ]
    assert resolve(rules) == "QUARANTINE"


def test_workflow_short_circuits():
    # P2: WORKFLOW short-circuits into its state machine on hit.
    rules = [
        _r("workflow", "WORKFLOW", 10, ring=0),
        _r("later-deny", "DENY", 20, ring=1),
    ]
    assert resolve(rules) == "WORKFLOW"


def test_override_allow_relaxes_rollback():
    # override ALLOW relaxes a restrictive decision (DENY/ROLLBACK/QUARANTINE) → ALLOW.
    rules = [
        _r("base-rollback", "ROLLBACK", 10, ring=0),
        _r("exception-allow", "ALLOW", 20, ring=3, override="critical"),
    ]
    assert resolve(rules) == "ALLOW"


def test_delegate_defer_guide_accumulate():
    # advisory / human-flow decisions accumulate only when nothing is set yet.
    for d in ("DELEGATE", "DEFER", "GUIDE"):
        assert resolve([_r("x", d, 10, ring=0)]) == d


def test_catch_all_inert_when_explicit_present():
    # §7.1 item 6 (global): a catch-all (empty-condition) DENY never overrides
    # an explicit ALLOW, even at a higher ring.
    rules = [
        _r("explicit-allow", "ALLOW", 10, ring=0),
        _r("catchall-deny", "DENY", 20, ring=3, catch_all=True),
    ]
    assert resolve(rules) == "ALLOW"


def test_catch_all_global_not_ring_local():
    # P1: a catch-all in ring 0 MUST NOT preempt an explicit rule in ring 3.
    # (the earlier per-ring "catch-all sorts last" reading returned ALLOW here;
    # the global fallback semantics returns CORRECT.)
    rules = [
        _r("catchall-allow", "ALLOW", 1, ring=0, catch_all=True),
        _r("explicit-correct", "CORRECT", 1, ring=3),
    ]
    assert resolve(rules) == "CORRECT"


def test_catch_all_allow_never_overrides_deny():
    # §7.1 item 6: a catch-all ALLOW never overrides an explicit DENY, even
    # with override=critical and across rings (the relax direction).
    rules = [
        _r("explicit-deny", "DENY", 10, ring=0),
        _r("catchall-allow", "ALLOW", 20, ring=3, override="critical", catch_all=True),
    ]
    assert resolve(rules) == "DENY"


def test_catch_all_allow_acts_as_fallback_when_nothing_set():
    # A catch-all ALLOW is still the fallback when no explicit rule matches.
    rules = [
        _r("catchall-allow", "ALLOW", 20, ring=3, override="critical", catch_all=True),
    ]
    assert resolve(rules) == "ALLOW"


def test_catch_all_sorts_last_within_ring():
    # v1.3: catch-all rules sort last within a ring, so an explicit rule wins
    # even at equal priority.
    rules = [
        _r("catchall-deny", "DENY", 10, ring=0, catch_all=True),
        _r("explicit-allow", "ALLOW", 10, ring=0),
    ]
    assert resolve(rules) == "ALLOW"
