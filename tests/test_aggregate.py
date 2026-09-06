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
"""

from z3 import Int, IntVal, is_true, simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import is_missing_int, tvl_aggregate, val_int

_SCALE = 10 ** 14


def _scaled(x):
    """decimal string → scale-14 int"""
    from erdl_formal.fixed_point import parse
    return int(parse(x) * _SCALE)


def _full(elements):
    """Aggregate over a *full* array (length == len(elements), all present)."""
    length = Int("len")
    from z3 import Solver
    s = Solver()
    s.add(length == len(elements))
    return length, elements, s


def test_count_full():
    elems = [IntVal(1), IntVal(2), IntVal(3)]
    r = tvl_aggregate("count", IntVal(3), elems)
    assert simplify(val_int(r)).as_long() == 3


def test_count_empty():
    # length=0 → count=0
    assert simplify(val_int(tvl_aggregate("count", IntVal(0), []))).as_long() == 0


def test_sum_full():
    elems = [IntVal(1), IntVal(2), IntVal(3)]
    assert simplify(val_int(tvl_aggregate("sum", IntVal(3), elems))).as_long() == 6


def test_sum_empty():
    assert simplify(val_int(tvl_aggregate("sum", IntVal(0), []))).as_long() == 0


def test_compiler_aggregate_sum_gt():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    # sum(amounts) > 100 → satisfiable (length=3, elements large)
    expr = {"gt": [{"sum": {"field": "amounts"}}, 100]}
    assert can_fire(expr, s) is True


def test_avg_exact():
    elems = [IntVal(_scaled("1")), IntVal(_scaled("2")), IntVal(_scaled("3"))]
    assert simplify(val_int(tvl_aggregate("avg", IntVal(3), elems))).as_long() == _scaled("2")


def test_avg_half():
    elems = [IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert simplify(val_int(tvl_aggregate("avg", IntVal(2), elems))).as_long() == _scaled("1.5")


def test_avg_rounds_half_even():
    # 1+1+2 = 4/3 ≈ 1.33333333333333 (scale-14)
    elems = [IntVal(_scaled("1")), IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert simplify(val_int(tvl_aggregate("avg", IntVal(3), elems))).as_long() == _scaled("1.33333333333333")


def test_min_max_full():
    elems = [IntVal(_scaled("3")), IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert simplify(val_int(tvl_aggregate("min", IntVal(3), elems))).as_long() == _scaled("1")
    assert simplify(val_int(tvl_aggregate("max", IntVal(3), elems))).as_long() == _scaled("3")


def test_avg_min_max_empty_fold_missing():
    # spec §7.3(e): avg/min/max over empty → Missing (E11 leaf-collapse folds comparisons false)
    for fn in ("avg", "min", "max"):
        assert is_true(simplify(is_missing_int(tvl_aggregate(fn, IntVal(0), []))))


def test_partial_length_guarded():
    """Only the first `length` elements participate in sum/min/max."""
    from z3 import And, Solver, sat
    elems = [IntVal(1), IntVal(100), IntVal(100)]
    # length=1 → sum=1 (only element 0)
    r = tvl_aggregate("sum", IntVal(1), elems)
    assert simplify(val_int(r)).as_long() == 1
    # length=1 → min=1 (element 0 only, elements 1..2 ignored)
    rm = tvl_aggregate("min", IntVal(1), elems)
    assert simplify(val_int(rm)).as_long() == 1


def test_compiler_aggregate_avg_min_max():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    assert can_fire({"gt": [{"avg": {"field": "amounts"}}, 1]}, s) is True
    assert can_fire({"gt": [{"max": {"field": "amounts"}}, 0]}, s) is True
    assert can_fire({"gt": [{"min": {"field": "amounts"}}, 0]}, s) is True


def test_compiler_avg_empty_array_folds_false():
    """avg over an empty array (length=0) → Missing → gt(Missing, 1) folds false."""
    from z3 import Solver, sat
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    ctx = None
    from erdl_formal.compiler import CompileContext, compile_expr
    ctx = CompileContext(s)
    cond = compile_expr({"gt": [{"avg": {"field": "amounts"}}, 1]}, ctx)
    # length=0 → avg=Missing → gt folds false (unsatisfiable under length=0)
    from erdl_formal.tvl import val_bool
    solver = Solver()
    solver.add(ctx.array_len("amounts") == 0)
    solver.add(val_bool(cond))
    assert solver.check() != sat
