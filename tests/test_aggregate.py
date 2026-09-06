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

"""Aggregate (count/sum/avg/min/max) over a length-variable array.

The SMT encoding takes a runtime length free variable `length` and `cardinality`
raw-τ element variables; only indices < length participate.

`tvl_aggregate` returns an :class:`AggVal` tagged union: count/sum are always
``num(value)`` (empty → num(0)); avg/min/max fold to ``empty`` (the boolean-false
safe fold, SPEC §7.3(e)) on an empty array.
"""

from z3 import Int, IntVal, is_false, is_true, simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import (
    AggVal,
    agg_is_empty,
    agg_num,
    tvl_aggregate,
)

_SCALE = 10 ** 14


def _scaled(x):
    """decimal string → scale-14 int"""
    from erdl_formal.fixed_point import parse
    return int(parse(x) * _SCALE)


def _num(r):
    """Extract the numeric value of an AggVal that is guaranteed to be num(...)."""
    return simplify(agg_num(r)).as_long()


def test_count_full():
    elems = [IntVal(1), IntVal(2), IntVal(3)]
    assert _num(tvl_aggregate("count", IntVal(3), elems)) == 3


def test_count_empty():
    # length=0 → count=0
    assert _num(tvl_aggregate("count", IntVal(0), [])) == 0


def test_sum_full():
    elems = [IntVal(1), IntVal(2), IntVal(3)]
    assert _num(tvl_aggregate("sum", IntVal(3), elems)) == 6


def test_sum_empty():
    assert _num(tvl_aggregate("sum", IntVal(0), [])) == 0


def test_compiler_aggregate_sum_gt():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    # sum(amounts) > 100 → satisfiable (length=3, elements large)
    expr = {"gt": [{"sum": {"field": "amounts"}}, 100]}
    assert can_fire(expr, s) is True


def test_avg_exact():
    elems = [IntVal(_scaled("1")), IntVal(_scaled("2")), IntVal(_scaled("3"))]
    assert _num(tvl_aggregate("avg", IntVal(3), elems)) == _scaled("2")


def test_avg_half():
    elems = [IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert _num(tvl_aggregate("avg", IntVal(2), elems)) == _scaled("1.5")


def test_avg_rounds_half_even():
    # 1+1+2 = 4/3 ≈ 1.33333333333333 (scale-14)
    elems = [IntVal(_scaled("1")), IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert _num(tvl_aggregate("avg", IntVal(3), elems)) == _scaled("1.33333333333333")


def test_min_max_full():
    elems = [IntVal(_scaled("3")), IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert _num(tvl_aggregate("min", IntVal(3), elems)) == _scaled("1")
    assert _num(tvl_aggregate("max", IntVal(3), elems)) == _scaled("3")


def test_avg_min_max_empty_fold_empty():
    """SPEC §7.3(e): avg/min/max over empty → the AggVal ``empty`` (boolean false) fold."""
    for fn in ("avg", "min", "max"):
        assert is_true(simplify(agg_is_empty(tvl_aggregate(fn, IntVal(0), []))))


def test_count_sum_never_empty():
    """count/sum are always numeric (never the boolean-false empty fold)."""
    for fn in ("count", "sum"):
        assert is_false(simplify(agg_is_empty(tvl_aggregate(fn, IntVal(0), []))))


def test_partial_length_guarded():
    """Only the first `length` elements participate in sum/min/max."""
    elems = [IntVal(1), IntVal(100), IntVal(100)]
    # length=1 → sum=1 (only element 0)
    assert _num(tvl_aggregate("sum", IntVal(1), elems)) == 1
    # length=1 → min=1 (element 0 only, elements 1..2 ignored)
    assert _num(tvl_aggregate("min", IntVal(1), elems)) == 1


def test_compiler_aggregate_avg_min_max():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    assert can_fire({"gt": [{"avg": {"field": "amounts"}}, 1]}, s) is True
    assert can_fire({"gt": [{"max": {"field": "amounts"}}, 0]}, s) is True
    assert can_fire({"gt": [{"min": {"field": "amounts"}}, 0]}, s) is True


def test_compiler_avg_empty_array_folds_false():
    """avg over an empty array (length=0) → empty (boolean false) → gt folds false."""
    from z3 import Solver, sat
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    from erdl_formal.compiler import CompileContext, compile_expr
    from erdl_formal.tvl import val_bool
    ctx = CompileContext(s)
    cond = compile_expr({"gt": [{"avg": {"field": "amounts"}}, 1]}, ctx)
    solver = Solver()
    solver.add(ctx.array_len("amounts") == 0)
    solver.add(val_bool(cond))
    assert solver.check() != sat


# --- G2 semantic matrix (engine ground truth, verified against @openoba/erdl) ---


def _compile_bool(expr, schema):
    from erdl_formal.compiler import CompileContext, compile_expr
    from erdl_formal.tvl import val_bool
    ctx = CompileContext(schema)
    return val_bool(compile_expr(expr, ctx))


def _assert_sat(expr, schema, length=None, expect=True):
    from z3 import Solver, sat, unsat
    from erdl_formal.compiler import CompileContext, compile_expr
    from erdl_formal.tvl import val_bool
    ctx = CompileContext(schema)
    cond = val_bool(compile_expr(expr, ctx))
    solver = Solver()
    for c in ctx.constraints:
        solver.add(c)
    if length is not None:
        solver.add(ctx.array_len("nums") == length)
    solver.add(cond)
    got = solver.check()
    assert (got == sat) == expect, f"{expr}: expected sat={expect}, got {got}"


def _nums_schema(cardinality):
    s = Schema()
    s.add(FieldContract(field="nums", type="array", element_type="int", cardinality=cardinality))
    return s


def test_g2_eq_empty_false_is_true():
    """min([]) == false → true (empty folds to the boolean false value)."""
    _assert_sat({"eq": [{"min": {"field": "nums"}}, False]}, _nums_schema(0), length=0, expect=True)


def test_g2_eq_empty_true_is_false():
    """min([]) == true → false."""
    _assert_sat({"eq": [{"min": {"field": "nums"}}, True]}, _nums_schema(0), length=0, expect=False)


def test_g2_ne_empty_true_is_true():
    """min([]) != true → true."""
    _assert_sat({"ne": [{"min": {"field": "nums"}}, True]}, _nums_schema(0), length=0, expect=True)


def test_g2_exists_empty_is_true():
    """exists(min([])) → true (the boolean false is a present value, not null/undefined)."""
    _assert_sat({"exists": {"min": {"field": "nums"}}}, _nums_schema(0), length=0, expect=True)


def test_g2_not_empty_is_true():
    """not(min([])) → true (toBoolean(false) = false → not = true)."""
    _assert_sat({"not": {"min": {"field": "nums"}}}, _nums_schema(0), length=0, expect=True)


def test_g2_eq_empty_zero_is_false():
    """min([]) == 0 → false (boolean false vs number → type mismatch)."""
    _assert_sat({"eq": [{"min": {"field": "nums"}}, 0]}, _nums_schema(0), length=0, expect=False)


def test_g2_gt_empty_zero_is_false():
    """min([]) > 0 → false."""
    _assert_sat({"gt": [{"min": {"field": "nums"}}, 0]}, _nums_schema(0), length=0, expect=False)


def test_g2_min_nonempty_eq_number():
    """min([1,2,3]) == 1 → true (non-empty numeric compare)."""
    _assert_sat({"eq": [{"min": {"field": "nums"}}, 1]}, _nums_schema(3), expect=True)
