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

"""String group (TVLString + contains/starts_with/ends_with/length)."""

from z3 import is_false, is_true, simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import (
    TVLStr,
    str_def,
    tvl_contains,
    tvl_ends_with,
    tvl_length,
    tvl_starts_with,
    val_bool,
    val_int,
)


def test_contains():
    assert is_true(simplify(val_bool(tvl_contains(str_def("hello world"), str_def("world")))))
    assert is_false(simplify(val_bool(tvl_contains(str_def("hello"), str_def("xyz")))))


def test_starts_with():
    assert is_true(simplify(val_bool(tvl_starts_with(str_def("hello"), str_def("he")))))
    assert is_false(simplify(val_bool(tvl_starts_with(str_def("hello"), str_def("lo")))))


def test_ends_with():
    assert is_true(simplify(val_bool(tvl_ends_with(str_def("hello"), str_def("lo")))))


def test_length():
    assert simplify(val_int(tvl_length(str_def("hello")))).as_long() == 5


def test_string_missing_collapses_false():
    assert is_false(simplify(val_bool(tvl_contains(TVLStr.Missing, str_def("x")))))


def test_compiler_string_field():
    s = Schema()
    s.add(FieldContract(field="tool.name", type="string"))
    expr = ["starts_with", ["field", "tool.name"], ["lit", "read"]]
    assert can_fire(expr, s, premises=["tool.name"]) is True


def test_match_literal():
    from erdl_formal.tvl import tvl_match
    assert is_true(simplify(val_bool(tvl_match(str_def("read_file"), "read_file"))))
    assert is_false(simplify(val_bool(tvl_match(str_def("read_file"), "write"))))


def test_string_eq():
    from erdl_formal.tvl import tvl_eq_str
    assert is_true(simplify(val_bool(tvl_eq_str(str_def("abc"), str_def("abc")))))
    assert is_false(simplify(val_bool(tvl_eq_str(str_def("abc"), str_def("abd")))))


def test_string_ne():
    from erdl_formal.tvl import tvl_ne_str
    assert is_true(simplify(val_bool(tvl_ne_str(str_def("abc"), str_def("abd")))))
    assert is_false(simplify(val_bool(tvl_ne_str(str_def("abc"), str_def("abc")))))


def test_string_eq_missing_collapses_false():
    from erdl_formal.tvl import tvl_eq_str
    assert is_false(simplify(val_bool(tvl_eq_str(TVLStr.Missing, str_def("x")))))


def test_compiler_string_eq_field():
    s = Schema()
    s.add(FieldContract(field="tool.name", type="string"))
    assert can_fire(["eq", ["field", "tool.name"], ["lit", "issue_refund"]], s, premises=["tool.name"]) is True


def test_compiler_string_ne_field():
    s = Schema()
    s.add(FieldContract(field="tool.name", type="string"))
    assert can_fire(["ne", ["field", "tool.name"], ["lit", "issue_refund"]], s, premises=["tool.name"]) is True


def test_compiler_string_exists_field():
    s = Schema()
    s.add(FieldContract(field="tool.name", type="string"))
    assert can_fire(["exists", ["field", "tool.name"]], s, premises=["tool.name"]) is True
