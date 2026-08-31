"""In (set membership) + add/sub (linear fixed-point arithmetic)."""

from z3 import is_false, is_true, simplify

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire
from erdl_formal.tvl import (
    TVLInt,
    is_missing_int,
    tvl_add,
    tvl_in,
    tvl_sub,
    val_bool,
    val_int,
)


def test_in_member():
    assert is_true(simplify(val_bool(tvl_in(TVLInt.Def(5), [TVLInt.Def(3), TVLInt.Def(5)]))))


def test_in_not_member():
    assert is_false(simplify(val_bool(tvl_in(TVLInt.Def(7), [TVLInt.Def(3), TVLInt.Def(5)]))))


def test_in_missing_collapses_false():
    assert is_false(simplify(val_bool(tvl_in(TVLInt.Missing, [TVLInt.Def(3)]))))


def test_add_exact():
    assert simplify(val_int(tvl_add(TVLInt.Def(2), TVLInt.Def(3)))).as_long() == 5


def test_sub_exact():
    assert simplify(val_int(tvl_sub(TVLInt.Def(5), TVLInt.Def(3)))).as_long() == 2


def test_add_missing_is_missing():
    assert is_true(simplify(is_missing_int(tvl_add(TVLInt.Missing, TVLInt.Def(3)))))


def test_compiler_in():
    s = Schema()
    s.add(FieldContract(field="status", type="int"))
    # status in [1, 2, 3] → satisfiable
    expr = ["in", ["field", "status"], [["lit", 1], ["lit", 2], ["lit", 3]]]
    assert can_fire(expr, s, premises=["status"]) is True


def test_compiler_add_compare():
    s = Schema()
    s.add(FieldContract(field="a", type="int"))
    s.add(FieldContract(field="b", type="int"))
    # a + b > 100 → satisfiable
    expr = ["gt", ["add", ["field", "a"], ["field", "b"]], ["lit", 100]]
    assert can_fire(expr, s, premises=["a", "b"]) is True
