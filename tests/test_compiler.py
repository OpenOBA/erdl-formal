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

from z3 import is_expr

from erdl_formal.compiler import CompileContext, compile_expr
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies, can_fire


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
    with pytest.raises(NotImplementedError):
        _compile(["lit", 1.5], _int_schema())


def test_compile_unsupported_field_type_raises():
    s = Schema()
    s.add(FieldContract(field="ratio", type="rational"))
    with pytest.raises(NotImplementedError):
        _compile(["field", "ratio"], s)


def test_premise_bool_field():
    s = Schema()
    s.add(FieldContract(field="flag", type="bool"))
    assert can_fire(["field", "flag"], s, premises=["flag"]) is True
