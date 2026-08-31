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

"""Aggregate (count/sum) over a fixed-length array."""

from z3 import simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import TVLInt, tvl_aggregate, val_int


def test_count():
    elems = [TVLInt.Def(1), TVLInt.Def(2), TVLInt.Def(3)]
    assert simplify(val_int(tvl_aggregate("count", elems))).as_long() == 3


def test_count_empty():
    assert simplify(val_int(tvl_aggregate("count", []))).as_long() == 0  # count([])=0


def test_sum():
    elems = [TVLInt.Def(1), TVLInt.Def(2), TVLInt.Def(3)]
    assert simplify(val_int(tvl_aggregate("sum", elems))).as_long() == 6


def test_sum_empty():
    assert simplify(val_int(tvl_aggregate("sum", []))).as_long() == 0  # sum([])=0


def test_compiler_aggregate_sum_gt():
    s = Schema()
    s.add(FieldContract(field="amounts", type="array", element_type="int", cardinality=3))
    # sum(amounts) > 100 → satisfiable
    expr = ["gt", ["aggregate", "sum", "amounts"], ["lit", 100]]
    assert can_fire(expr, s) is True
