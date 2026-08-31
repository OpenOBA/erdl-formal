"""Rule resolution reference model (§9 + erdl evaluator.ts).

Models the resolution semantics: ring order (0→3), priority ascending, override
(DENY→ALLOW only), EMERGENCY_HALT short-circuit. Used to verify the
ERDL-specific properties (override-soundness / ring-respect / emergency-shortcut).

A rule here is a dict: {name, priority, ring, override, decision}; all rules are
assumed to MATCH (this models resolution, not condition matching).
"""

_OVERRIDE_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def override_enables(rule):
    return rule.get("override") in ("critical", "high")


def _override_rank(rule):
    return _OVERRIDE_RANK.get(rule.get("override"), 4)


def resolve(rules):
    """Return the final decision for a matched rule set (evaluator.ts semantics)."""
    by_ring = {}
    for r in rules:
        by_ring.setdefault(r.get("ring", 3), []).append(r)

    final = None
    final_ring = None

    for ring in sorted(by_ring):
        ring_rules = sorted(by_ring[ring], key=lambda r: (r["priority"], _override_rank(r)))
        for r in ring_rules:
            d = r["decision"]

            # Sec. 7.1 gate: non-override non-terminating rules can't change a decision
            if final is not None:
                is_terminating = d in ("DENY", "EMERGENCY_HALT")
                is_allow_accum = d == "ALLOW" and final == "ALLOW"
                if not override_enables(r) and not is_terminating and not is_allow_accum:
                    continue

            if d == "ALLOW":
                if override_enables(r) and final == "DENY":
                    # override DENY→ALLOW (cross-ring, safe relax)
                    final, final_ring = "ALLOW", ring
                    break
                if final is None:
                    final, final_ring = "ALLOW", ring
                continue

            if d == "EMERGENCY_HALT":
                final, final_ring = "EMERGENCY_HALT", ring
                if ring == 0:
                    return "EMERGENCY_HALT"  # only EMERGENCY_HALT short-circuits
                break

            if d == "DENY":
                if final is None or final == "DENY":
                    final, final_ring = "DENY", ring
                elif final == "ALLOW":
                    if ring > final_ring or (ring == final_ring and not override_enables(r)):
                        # higher-ring DENY, or same-ring non-override DENY → overrides ALLOW
                        final, final_ring = "DENY", ring
                    # same-ring override DENY cannot override ALLOW (unsafe direction)
                # DENY cannot override ESCALATE/REQUEST_HUMAN etc.
                continue

            # CORRECT / REQUEST_HUMAN / ESCALATE / NOTIFY: accumulate
            if final is None:
                final, final_ring = d, ring
            continue

    return final if final is not None else "ALLOW"
