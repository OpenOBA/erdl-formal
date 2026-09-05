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

"""End-to-end: S-expression → symbolic compile → property verification."""

import pytest

from decimal import Decimal
from fractions import Fraction

from z3 import BoolSort, is_expr

from erdl_formal.compiler import CompileContext, compile_expr
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies, can_fire, equivalent


def _g3_schema():
    s = Schema()
    s.add(FieldContract(field="file_cls", type="int"))
    s.add(FieldContract(field="op_cls", type="int"))
    return s


def _g3_rule():
    # when: file_cls > op_cls  →  DENY
    return ["gt", ["field", "file_cls"], ["field", "op_cls"]]


def test_g3_can_fire_with_premise():
    s = _g3_schema()
    assert can_fire(_g3_rule(), s, premises=["file_cls", "op_cls"]) is True


def test_g3_fail_closed_when_op_missing():
    s = _g3_schema()
    # op_cls Missing → gt collapses False → guard never fires (leaf collapse, E11)
    assert can_fire(_g3_rule(), s, premises=["file_cls"], missing=["op_cls"]) is False


def test_g3_always_denies():
    s = _g3_schema()
    # DENY fallback → a silenced guard still denies (fail-closed holds).
    assert (
        always_denies(
            _g3_rule(), s, premises=["file_cls", "op_cls"],
            missing_field="op_cls", default_decision="DENY",
        )
        is True
    )


def test_g3_always_denies_fails_open_with_allow_default():
    s = _g3_schema()
    # ALLOW fallback (resolution default) → a missing op_cls silences the guard
    # and falls through to ALLOW → the rule fails open (property must be False).
    assert (
        always_denies(
            _g3_rule(), s, premises=["file_cls", "op_cls"],
            missing_field="op_cls", default_decision="ALLOW",
        )
        is False
    )


def test_bool_eq_field():
    s = Schema()
    s.add(FieldContract(field="flag", type="bool"))
    assert can_fire(["eq", ["field", "flag"], ["lit", True]], s, premises=["flag"]) is True


def test_bool_exists_field():
    s = Schema()
    s.add(FieldContract(field="flag", type="bool"))
    assert can_fire(["exists", ["field", "flag"]], s, premises=["flag"]) is True


def test_decimal_literal_compiles():
    """Decimal literals (money thresholds) enter the verifier, auto-converted to scale-14."""
    s = Schema()
    s.add(FieldContract(field="amount", type="int"))
    half = ["gt", ["field", "amount"], ["lit", 50000000000000]]
    # float 0.5 == scale-14 50000000000000
    assert equivalent(["gt", ["field", "amount"], ["lit", 0.5]], half, s) is True
    # 0.1 / 12.34 (float precision absorbed by scale-14 rounding)
    assert equivalent(
        ["gt", ["field", "amount"], ["lit", 0.1]],
        ["gt", ["field", "amount"], ["lit", 10000000000000]], s,
    ) is True
    assert equivalent(
        ["gt", ["field", "amount"], ["lit", 12.34]],
        ["gt", ["field", "amount"], ["lit", 1234000000000000]], s,
    ) is True
    # scientific-notation float (very small)
    assert equivalent(
        ["gt", ["field", "amount"], ["lit", 0.00001]],
        ["gt", ["field", "amount"], ["lit", 1000000000]], s,
    ) is True
    # exact paths: Decimal / Fraction
    assert equivalent(
        ["gt", ["field", "amount"], ["lit", Decimal("0.5")]], half, s,
    ) is True
    assert equivalent(
        ["gt", ["field", "amount"], ["lit", Fraction(1, 2)]], half, s,
    ) is True


def test_decimal_literal_rejects_non_finite():
    s = Schema()
    s.add(FieldContract(field="amount", type="int"))
    for bad in (float("nan"), float("inf"), float("-inf")):
        try:
            can_fire(["gt", ["field", "amount"], ["lit", bad]], s, premises=["amount"])
            assert False, f"{bad!r} should be rejected"
        except ValueError:
            pass


def test_missing_string_field_does_not_crash():
    """forcing a string field Missing must be type-dispatched, not int (regression: Sort mismatch)."""
    s = Schema()
    s.add(FieldContract(field="name", type="string"))
    assert can_fire(["eq", ["field", "name"], ["lit", "x"]], s, missing=["name"]) is False


def test_missing_bool_field_does_not_crash():
    s = Schema()
    s.add(FieldContract(field="active", type="bool"))
    assert can_fire(["eq", ["field", "active"], ["lit", True]], s, missing=["active"]) is False


def test_always_denies_string_missing_fails_open():
    s = Schema()
    s.add(FieldContract(field="status", type="string"))
    # status == "active" with a missing status + ALLOW fallback -> fail-open (property False)
    assert (
        always_denies(
            ["eq", ["field", "status"], ["lit", "active"]], s,
            missing_field="status", default_decision="ALLOW",
        )
        is False
    )


def test_always_denies_missing_field_not_referenced():
    """Forcing an *unreferenced* field Missing must not report fail-open.

    Regression: when missing_field is also in premises, the probe previously
    asserted premise(field) ∧ missing(field) — always UNSAT — so even a rule
    that never reads the field was reported fail-open.
    """
    s = Schema()
    s.add(FieldContract(field="a", type="int"))
    s.add(FieldContract(field="b", type="int"))
    # a > 0 never references b; forcing b Missing cannot silence the guard.
    assert (
        always_denies(
            ["gt", ["field", "a"], ["lit", 0]], s,
            premises=["a", "b"], missing_field="b", default_decision="ALLOW",
        )
        is True
    )


def test_array_element_is_raw_sort():
    """Array<τ> elements are raw τ, not TVL(τ) — no spurious Missing elements."""
    s = Schema()
    s.add(FieldContract(field="approvers", type="array", element_type="bool", cardinality=3))
    ctx = CompileContext(s)
    assert ctx.array_element("approvers", 0).sort() == BoolSort()


def test_var_node_is_free_int_variable():
    from erdl_formal.tvl import TVLInt
    s = Schema()
    ctx = CompileContext(s)
    v = ctx.var("$.amount")
    assert v.sort() == TVLInt  # free TVLInt (Def | Missing), defaults to int


def test_var_node_can_fire():
    s = Schema()
    # $.amount > 100 is satisfiable (the var can be any int)
    assert can_fire(["gt", ["var", "$.amount"], ["lit", 100]], s) is True


def _approval_schema():
    s = Schema()
    s.add(FieldContract(field="approvers", type="array", element_type="bool", cardinality=3))
    return s


def test_all_approvers_can_fire():
    s = _approval_schema()
    # all(approvers) — 3-way conjunction over approval booleans — satisfiable
    assert can_fire(["all", "approvers"], s) is True


def test_empty_approvers_fail_closed():
    # cardinality 0 → all([]) → False (E8), never fires
    s = Schema()
    s.add(FieldContract(field="approvers", type="array", element_type="bool", cardinality=0))
    assert can_fire(["all", "approvers"], s) is False


def test_not_compile():
    s = _g3_schema()
    expr = ["not", ["gt", ["field", "file_cls"], ["field", "op_cls"]]]
    assert can_fire(expr, s, premises=["file_cls", "op_cls"]) is True


def test_exists_compile():
    s = _g3_schema()
    expr = ["exists", ["field", "file_cls"]]
    assert can_fire(expr, s, premises=["file_cls"]) is True
    assert can_fire(expr, s, missing=["file_cls"]) is False


# --- compiler op dispatch coverage (S-expression → Z3) ---


def _int_schema(*fields):
    s = Schema()
    for f in fields:
        s.add(FieldContract(field=f, type="int"))
    return s


def _string_schema(*fields):
    s = Schema()
    for f in fields:
        s.add(FieldContract(field=f, type="string"))
    return s


def _compile(expr, schema):
    return compile_expr(expr, CompileContext(schema))


def test_compile_and():
    s = _int_schema("a", "b")
    expr = ["and", ["gt", ["field", "a"], ["lit", 0]], ["lt", ["field", "b"], ["lit", 10]]]
    assert can_fire(expr, s, premises=["a", "b"]) is True


def test_compile_or():
    s = _int_schema("a", "b")
    expr = ["or", ["eq", ["field", "a"], ["lit", 1]], ["eq", ["field", "b"], ["lit", 2]]]
    assert can_fire(expr, s, premises=["a", "b"]) is True


def test_compile_contains():
    s = _string_schema("name")
    assert can_fire(["contains", ["field", "name"], ["lit", "abc"]], s, premises=["name"]) is True


def test_compile_ends_with():
    s = _string_schema("name")
    assert can_fire(["ends_with", ["field", "name"], ["lit", ".json"]], s, premises=["name"]) is True


def test_compile_match():
    s = _string_schema("name")
    assert can_fire(["match", ["field", "name"], "read_file"], s, premises=["name"]) is True


def test_compile_length():
    s = _string_schema("name")
    assert is_expr(_compile(["length", ["field", "name"]], s))


def test_compile_sub():
    s = _int_schema("a", "b")
    assert is_expr(_compile(["sub", ["field", "a"], ["field", "b"]], s))


def test_compile_round():
    s = _int_schema("a")
    assert is_expr(_compile(["round", ["field", "a"]], s))


def test_compile_days_between():
    s = _int_schema("t1", "t2")
    assert is_expr(_compile(["days_between", ["field", "t1"], ["field", "t2"]], s))


def test_compile_date_part():
    s = _int_schema("t")
    assert is_expr(_compile(["date_part", "year", ["field", "t"]], s))


def test_compile_month_last_day():
    s = _int_schema("t")
    assert is_expr(_compile(["month_last_day", ["field", "t"]], s))


def test_compile_date_add():
    s = _int_schema("t", "n")
    assert is_expr(_compile(["date_add", "days", ["field", "t"], ["field", "n"]], s))


def test_compile_bool_literal():
    s = _int_schema()
    assert is_expr(_compile(["lit", True], s))
    assert is_expr(_compile(True, s))  # bare literal (non-list) → _lit


def test_compile_unknown_op_raises():
    with pytest.raises(NotImplementedError):
        _compile(["no_such_op", 1], _int_schema())


def test_compile_unsupported_literal_raises():
    # float / Fraction / Decimal are now supported (scale-14 fixed-point); a
    # genuinely unsupported literal type still raises.
    with pytest.raises(NotImplementedError):
        _compile(["lit", None], _int_schema())


def test_compile_unsupported_field_type_raises():
    s = Schema()
    s.add(FieldContract(field="ratio", type="rational"))
    with pytest.raises(NotImplementedError):
        _compile(["field", "ratio"], s)


def test_premise_bool_field():
    s = Schema()
    s.add(FieldContract(field="flag", type="bool"))
    assert can_fire(["field", "flag"], s, premises=["flag"]) is True
