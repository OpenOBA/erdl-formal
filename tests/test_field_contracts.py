"""Field contracts (verification schema) tests."""

import pytest

from erdl_formal.field_contracts import FieldContract, Schema


def test_scalar_contract_type():
    s = Schema()
    s.add(FieldContract(field="amount", type="int"))
    assert s.requires("amount").type == "int"


def test_array_contract_cardinality():
    s = Schema()
    s.add(FieldContract(field="approvers", type="array", element_type="bool", cardinality=3))
    assert s.cardinality("approvers") == 3


def test_array_without_cardinality_raises():
    s = Schema()
    s.add(FieldContract(field="approvers", type="array", element_type="bool"))
    with pytest.raises(ValueError):
        s.cardinality("approvers")


def test_cardinality_on_scalar_raises():
    s = Schema()
    s.add(FieldContract(field="amount", type="int"))
    with pytest.raises(TypeError):
        s.cardinality("amount")


def test_missing_contract_raises():
    s = Schema()
    with pytest.raises(KeyError):
        s.requires("nope")
