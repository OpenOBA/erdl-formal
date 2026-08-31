"""Phase 1 — G3「涉密访问控制」: file_classification > operator_classification → DENY.

This demonstrates the two halves of the POC goal:
1. **Guarded property**: with the schema premise (both fields present), the rule
   fires (→ DENY) exactly when file_cls > operator_cls.
2. **Field-missing bypass (counterexample)**: without the schema premise, a
   missing operator_classification collapses the comparison to False (E11), so
   the rule never fires → no DENY → fail-open. This is the counterexample that
   *proves the schema premise is necessary*.
"""

from z3 import Int, Solver, sat, unsat

from erdl_formal.tvl import (
    TVLInt,
    tvl_gt,
    val_bool,
    val_int,
)


def _rule_fires(file_cls, op_cls):
    """G3 `when`: file_classification > operator_classification (E11 collapse)."""
    return val_bool(tvl_gt(file_cls, op_cls))


def test_g3_guarded_fires_when_higher_classification():
    """Both fields present → the rule fires iff file_cls > op_cls."""
    file_cls = TVLInt.Def(Int("file_cls"))
    op_cls = TVLInt.Def(Int("op_cls"))
    fired = _rule_fires(file_cls, op_cls)

    s = Solver()
    s.add(fired)
    assert s.check() == sat
    m = s.model()
    assert m.eval(val_int(file_cls)).as_long() > m.eval(val_int(op_cls)).as_long()


def test_g3_guarded_never_fires_when_lower_or_equal():
    """Both fields present → file_cls <= op_cls never fires (block only on exceed)."""
    file_cls = TVLInt.Def(Int("file_cls"))
    op_cls = TVLInt.Def(Int("op_cls"))
    fired = _rule_fires(file_cls, op_cls)

    s = Solver()
    s.add(file_cls == op_cls, fired)  # equal classification must NOT block
    assert s.check() == unsat


def test_g3_field_missing_bypass():
    """operator_classification Missing → comparison collapses False → never fires.

    This is the POC's canonical counterexample: the 'always-denies' property is
    FALSE without the schema premise that operator_classification exists.
    """
    file_cls = TVLInt.Def(Int("file_cls"))
    op_cls = TVLInt.Missing
    fired = _rule_fires(file_cls, op_cls)

    s = Solver()
    s.add(fired)
    assert s.check() == unsat  # never fires → fail-open bypass
