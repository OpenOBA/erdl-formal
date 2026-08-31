"""M3 end-to-end: S-expression → symbolic compile → property verification."""

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
    # op_cls Missing → gt collapses False → never fires → fail-closed (no bypass)
    assert can_fire(_g3_rule(), s, premises=["file_cls"], missing=["op_cls"]) is False


def test_g3_always_denies():
    s = _g3_schema()
    assert (
        always_denies(
            _g3_rule(), s, premises=["file_cls", "op_cls"], missing_field="op_cls"
        )
        is True
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
