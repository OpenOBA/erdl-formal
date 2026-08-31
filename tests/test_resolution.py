"""ERDL-specific properties via the rule resolution reference model.

override-soundness / ring-respect / emergency-shortcut (plan §2, v6 — with the
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
