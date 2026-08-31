"""M3.1 — string group (TVLString + contains/starts_with/ends_with/length)."""

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
