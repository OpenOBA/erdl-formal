"""Phase 2 — 量词 all（空数组折叠 + 索引展开）+ 三值逻辑 AND.

Rule: "所有审批人均已批准 → ALLOW" (all approvers approved → ALLOW).
"""

from z3 import Bool, Int, Not, Solver, sat, unsat

from erdl_formal.quantifiers import tvl_all
from erdl_formal.tvl import (
    TVLBool,
    TVLInt,
    tvl_and,
    tvl_eq,
    val_bool,
)


def _approval_rule(approvals):
    """when: all(approvers, status == approved) → ALLOW."""
    return val_bool(tvl_all(approvals))


def test_all_fires_when_every_approver_approved():
    """all([T, T, T]) → rule fires (ALLOW)."""
    approvals = [TVLBool.Def(Bool(f"a{i}")) for i in range(3)]
    fired = _approval_rule(approvals)
    s = Solver()
    s.add(fired)
    assert s.check() == sat
    m = s.model()
    assert all(m.eval(val_bool(a)) for a in approvals)


def test_all_does_not_fire_when_any_not_approved():
    """any approver not approved → all() = False → no ALLOW (fail-closed)."""
    approvals = [TVLBool.Def(Bool(f"a{i}")) for i in range(3)]
    fired = _approval_rule(approvals)
    s = Solver()
    # force one approver to be "not approved" (False)
    s.add(Not(val_bool(approvals[1])))
    s.add(fired)
    assert s.check() == unsat  # rule never fires when any is False


def test_all_empty_array_folds_false():
    """E8: all([]) = False — anti-vacuous-truth (fail-closed, no empty bypass)."""
    fired = _approval_rule([])
    s = Solver()
    s.add(fired)
    assert s.check() == unsat  # empty approvals never ALLOW


def test_three_valued_and_leaf_collapse():
    """AND with a missing-field comparison: missing → False → false AND x = False.

    `context.role == 'admin'` with role missing collapses to False (E11);
    `False AND <anything>` is False (two-valued AND).
    """
    role = TVLInt.Missing  # role field missing
    is_admin = tvl_eq(role, TVLInt.Def(Int("admin_val")))
    other = TVLBool.Def(Bool("other"))
    combined = tvl_and(is_admin, other)
    # combined is always False (is_admin collapsed to False)
    s = Solver()
    s.add(val_bool(combined))
    assert s.check() == unsat
