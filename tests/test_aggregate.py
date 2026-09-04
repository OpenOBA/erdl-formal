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

"""Aggregate (count/sum/avg/min/max) over a fixed-length array."""

from z3 import IntVal, is_true, simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import is_missing_int, tvl_aggregate, val_int

_SCALE = 10 ** 14


def _scaled(x):
    """decimal string → scale-14 int"""
    from erdl_formal.fixed_point import parse
    return int(parse(x) * _SCALE)


def test_count():
    elems = [IntVal(1), IntVal(2), IntVal(3)]
    assert simplify(val_int(tvl_aggregate("count", elems))).as_long() == 3


def test_count_empty():
    assert simplify(val_int(tvl_aggregate("count", []))).as_long() == 0  # count([])=0


def test_sum():
    elems = [IntVal(1), IntVal(2), IntVal(3)]
    assert simplify(val_int(tvl_aggregate("sum", elems))).as_long() == 6


def test_sum_empty():
    assert simplify(val_int(tvl_aggregate("sum", []))).as_long() == 0  # sum([])=0


def test_compiler_aggregate_sum_gt():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    # sum(amounts) > 100 → satisfiable
    expr = ["gt", ["aggregate", "sum", "amounts"], ["lit", 100]]
    assert can_fire(expr, s) is True


def test_avg_exact():
    elems = [IntVal(_scaled("1")), IntVal(_scaled("2")), IntVal(_scaled("3"))]
    assert simplify(val_int(tvl_aggregate("avg", elems))).as_long() == _scaled("2")


def test_avg_half():
    elems = [IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert simplify(val_int(tvl_aggregate("avg", elems))).as_long() == _scaled("1.5")


def test_avg_rounds_half_even():
    # 1+1+2 = 4/3 ≈ 1.33333333333333 (scale-14)
    elems = [IntVal(_scaled("1")), IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert simplify(val_int(tvl_aggregate("avg", elems))).as_long() == _scaled("1.33333333333333")


def test_min_max():
    elems = [IntVal(_scaled("3")), IntVal(_scaled("1")), IntVal(_scaled("2"))]
    assert simplify(val_int(tvl_aggregate("min", elems))).as_long() == _scaled("1")
    assert simplify(val_int(tvl_aggregate("max", elems))).as_long() == _scaled("3")


def test_avg_min_max_empty_fold_false():
    # spec §7.3(e): avg/min/max over empty → Missing (E11 leaf-collapse folds comparisons false)
    for fn in ("avg", "min", "max"):
        assert is_true(simplify(is_missing_int(tvl_aggregate(fn, []))))


def test_compiler_aggregate_avg_min_max():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    assert can_fire(["gt", ["aggregate", "avg", "amounts"], ["lit", 1]], s) is True
    assert can_fire(["gt", ["aggregate", "max", "amounts"], ["lit", 0]], s) is True
    assert can_fire(["gt", ["aggregate", "min", "amounts"], ["lit", 0]], s) is True
