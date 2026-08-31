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

"""Between (closed interval) + days_between (timestamp layer)."""

from z3 import is_false, is_true, simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import (
    TVLInt,
    is_missing_int,
    tvl_between,
    tvl_days_between,
    val_bool,
    val_int,
)


# --- between ---


def test_between_in_range():
    assert is_true(simplify(val_bool(tvl_between(TVLInt.Def(5), TVLInt.Def(3), TVLInt.Def(10)))))


def test_between_out_of_range():
    assert is_false(simplify(val_bool(tvl_between(TVLInt.Def(20), TVLInt.Def(3), TVLInt.Def(10)))))


def test_between_missing_collapses_false():
    assert is_false(simplify(val_bool(tvl_between(TVLInt.Def(5), TVLInt.Missing, TVLInt.Def(10)))))


# --- days_between ---


def test_days_between_exact_day():
    # days_between(from=0, to=86400000) = (to - from) = 1 day (erdl semantics = to − from)
    r = tvl_days_between(TVLInt.Def(0), TVLInt.Def(86400000))
    assert simplify(val_int(r)).as_long() == 1


def test_days_between_negative_floor():
    # days_between(from=86400000, to=0) = -1 day
    r = tvl_days_between(TVLInt.Def(86400000), TVLInt.Def(0))
    assert simplify(val_int(r)).as_long() == -1


def test_days_between_missing_is_missing():
    r = tvl_days_between(TVLInt.Missing, TVLInt.Def(0))
    assert is_true(simplify(is_missing_int(r)))


# --- compiler integration ---


def test_compiler_between():
    s = Schema()
    s.add(FieldContract(field="amount", type="int"))
    expr = ["between", ["field", "amount"], ["lit", 100], ["lit", 500]]
    assert can_fire(expr, s, premises=["amount"]) is True
