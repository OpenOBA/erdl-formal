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


def _r(name, decision, priority, ring=3, override=None):
    return {"name": name, "decision": decision, "priority": priority, "ring": ring, "override": override}


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


def test_request_human_accumulates():
    # non-ALLOW/DENY/HALT decision accumulates when nothing set yet
    rules = [_r("human", "REQUEST_HUMAN", 10, ring=0)]
    assert resolve(rules) == "REQUEST_HUMAN"
