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

"""Quantifier all/any/none (empty-array collapse E8 + length-guarded index expansion)."""

from z3 import Bool, Int, IntVal, Not, Solver, is_false, is_true, sat, simplify, unsat

from erdl_formal.quantifiers import tvl_all, tvl_any, tvl_none
from erdl_formal.tvl import (
    TVLBool,
    TVLInt,
    tvl_and,
    tvl_eq,
    val_bool,
)


def test_all_fires_when_every_approver_approved():
    """all over length=3 with all true → fires."""
    preds = [Bool(f"a{i}") for i in range(3)]
    fired = val_bool(tvl_all(IntVal(3), preds))
    s = Solver()
    s.add(fired)
    assert s.check() == sat
    m = s.model()
    assert all(m.eval(a) for a in preds)


def test_all_does_not_fire_when_any_not_approved():
    """any predicate false → all() = False (fail-closed)."""
    preds = [Bool(f"a{i}") for i in range(3)]
    fired = val_bool(tvl_all(IntVal(3), preds))
    s = Solver()
    s.add(Not(preds[1]))
    s.add(fired)
    assert s.check() == unsat


def test_all_empty_array_folds_false():
    """E8: all(empty) = False — anti-vacuous-truth (fail-closed, no empty bypass)."""
    fired = val_bool(tvl_all(IntVal(0), []))
    s = Solver()
    s.add(fired)
    assert s.check() == unsat


def test_all_partial_length_guarded():
    """Only the first `length` predicates participate; out-of-range is ignored."""
    preds = [Bool("a0"), Bool("a1"), Bool("a2")]
    # length=1 → only preds[0] matters
    fired = val_bool(tvl_all(IntVal(1), preds))
    s = Solver()
    s.add(fired)
    assert s.check() == sat
    m = s.model()
    assert m.eval(preds[0])


def test_three_valued_and_leaf_collapse():
    """AND with a missing-field comparison: missing → False → false AND x = False."""
    role = TVLInt.Missing
    is_admin = tvl_eq(role, TVLInt.Def(Int("admin_val")))
    other = TVLBool.Def(Bool("other"))
    combined = tvl_and(is_admin, other)
    s = Solver()
    s.add(val_bool(combined))
    assert s.check() == unsat


def test_tvl_any_semantics():
    assert is_false(simplify(val_bool(tvl_any(IntVal(0), []))))  # E8: any([]) = False
    one_true = [BoolVal_True(), BoolVal_False()]
    assert is_true(simplify(val_bool(tvl_any(IntVal(2), one_true))))


def test_tvl_none_semantics():
    assert is_false(simplify(val_bool(tvl_none(IntVal(0), []))))  # E8: none([]) = False
    no_true = [BoolVal_False(), BoolVal_False()]
    assert is_true(simplify(val_bool(tvl_none(IntVal(2), no_true))))


def BoolVal_True():
    from z3 import BoolVal
    return BoolVal(True)


def BoolVal_False():
    from z3 import BoolVal
    return BoolVal(False)
