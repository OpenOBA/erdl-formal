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
