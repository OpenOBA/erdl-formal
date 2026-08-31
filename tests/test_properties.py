"""Property tests — subsumption / equivalence / disjointness (Cedar 6)."""

from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import disjoint, equivalent, subsumes


def _schema():
    s = Schema()
    s.add(FieldContract(field="amount", type="int"))
    return s


def test_subsumes_amount_gt_100_implies_gt_50():
    s = _schema()
    a = ["gt", ["field", "amount"], ["lit", 100]]  # amount > 100
    b = ["gt", ["field", "amount"], ["lit", 50]]   # amount > 50
    # amount>100 ⇒ amount>50 (a is stricter)
    assert subsumes(a, b, s) is True
    assert subsumes(b, a, s) is False


def test_equivalent_same_expr():
    s = _schema()
    a = ["gt", ["field", "amount"], ["lit", 100]]
    b = ["gt", ["field", "amount"], ["lit", 100]]
    assert equivalent(a, b, s) is True


def test_equivalent_different_not_equiv():
    s = _schema()
    a = ["gt", ["field", "amount"], ["lit", 100]]
    b = ["gt", ["field", "amount"], ["lit", 50]]
    assert equivalent(a, b, s) is False


def test_disjoint_amount_lt_10_and_gt_100():
    s = _schema()
    a = ["lt", ["field", "amount"], ["lit", 10]]
    b = ["gt", ["field", "amount"], ["lit", 100]]
    assert disjoint(a, b, s) is True


def test_not_disjoint_overlapping():
    s = _schema()
    a = ["gt", ["field", "amount"], ["lit", 50]]
    b = ["lt", ["field", "amount"], ["lit", 100]]
    # amount in (50, 100) satisfies both → not disjoint
    assert disjoint(a, b, s) is False
