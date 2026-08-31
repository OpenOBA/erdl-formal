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

"""Fixed-point (E2) reference semantics tests: scale=14 + half-even + minimal."""

from fractions import Fraction

import pytest

from erdl_formal.fixed_point import (
    add,
    div,
    mul,
    parse,
    serialize,
    sub,
    to_scale14_half_even,
)


def test_parse_rejects_scientific():
    with pytest.raises(ValueError):
        parse("1.5e3")


def test_serialize_minimal_no_trailing_zero():
    assert serialize(Fraction(5, 10)) == "0.5"  # not "0.50"
    assert serialize(Fraction(1, 1)) == "1"      # not "1.0"
    assert serialize(Fraction(100, 4)) == "25"


def test_parse_serialize_roundtrip():
    assert serialize(parse("0.5")) == "0.5"
    assert serialize(parse("123.456")) == "123.456"


def test_scale14_half_even_round_down():
    # 0.000000000000005 (5 at 15th decimal) → round to even (0 at 14th) → 0
    v = Fraction(5, 10 ** 15)
    assert serialize(to_scale14_half_even(v)) == "0"


def test_scale14_half_even_round_up():
    # 0.000000000000015 (15 at 15th decimal, 1 odd at 14th) → round up to even → 2
    v = Fraction(15, 10 ** 15)
    assert serialize(to_scale14_half_even(v)) == "0.00000000000002"


def test_scale14_exact_third():
    # 1/3 → 0.33333333333333 (14 threes)
    assert serialize(to_scale14_half_even(Fraction(1, 3))) == "0.33333333333333"


def test_arithmetic_exact_no_float_error():
    # 0.1 + 0.2 == 0.3 exactly (no IEEE-754 error)
    assert serialize(add(parse("0.1"), parse("0.2"))) == "0.3"
    # (1/3) * 3 == 1 exactly
    assert serialize(mul(Fraction(1, 3), Fraction(3, 1))) == "1"
    # 1 / 8 == 0.125
    assert serialize(div(Fraction(1, 1), Fraction(8, 1))) == "0.125"


def test_division_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        div(Fraction(1, 1), Fraction(0, 1))


def test_serialize_negative():
    assert serialize(Fraction(-1, 2)) == "-0.5"
    assert serialize(Fraction(-3, 1)) == "-3"


def test_scale14_negative_half_even():
    # -0.000000000000005 → round half-even toward even → 0
    assert serialize(to_scale14_half_even(Fraction(-5, 10 ** 15))) == "0"


def test_scale14_exact_14_decimals_no_rounding():
    v = Fraction(12345678901234, 10 ** 14)  # 0.12345678901234
    assert serialize(to_scale14_half_even(v)) == "0.12345678901234"


def test_serialize_large_integer():
    assert serialize(Fraction(10 ** 20, 1)) == "100000000000000000000"


def test_div_rounding():
    assert serialize(to_scale14_half_even(div(Fraction(1, 1), Fraction(3, 1)))) == "0.33333333333333"
    assert serialize(div(Fraction(10, 1), Fraction(4, 1))) == "2.5"


def test_scale14_half_even_round_up_above_half():
    # 7 at the 15th decimal → more than halfway → round up (the `else` branch, not exact-half)
    assert serialize(to_scale14_half_even(Fraction(7, 10 ** 15))) == "0.00000000000001"


def test_serialize_non_terminating_raises():
    # 1/3 has no terminating decimal form → safety cap raises
    with pytest.raises(ValueError):
        serialize(Fraction(1, 3))


def test_sub_exact():
    assert serialize(sub(Fraction(5, 1), Fraction(3, 1))) == "2"
