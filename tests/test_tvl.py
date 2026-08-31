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

"""TVL (E11) direct unit tests — leaf-collapse semantics, exhaustive per-op."""

from z3 import is_false, is_true, simplify

from erdl_formal.tvl import (
    TVLBool,
    TVLInt,
    exists_int,
    tvl_and,
    tvl_eq,
    tvl_gt,
    tvl_gte,
    tvl_lt,
    tvl_lte,
    tvl_ne,
    tvl_not,
    tvl_or,
    val_bool,
)


def _b(v):
    return val_bool(v)


# --- comparison: collapse on Missing (E11) ---


def test_gt_missing_collapses_false():
    assert is_false(simplify(_b(tvl_gt(TVLInt.Def(5), TVLInt.Missing))))


def test_gte_missing_collapses_false():
    assert is_false(simplify(_b(tvl_gte(TVLInt.Def(5), TVLInt.Missing))))


def test_lt_missing_collapses_false():
    assert is_false(simplify(_b(tvl_lt(TVLInt.Def(5), TVLInt.Missing))))


def test_lte_missing_collapses_false():
    assert is_false(simplify(_b(tvl_lte(TVLInt.Def(5), TVLInt.Missing))))


def test_eq_missing_collapses_false():
    assert is_false(simplify(_b(tvl_eq(TVLInt.Def(5), TVLInt.Missing))))


def test_ne_missing_collapses_false():
    # note: ne ALSO collapses to false on missing (E11: everything except exists collapses to false)
    assert is_false(simplify(_b(tvl_ne(TVLInt.Def(5), TVLInt.Missing))))


# --- comparison: normal ---


def test_gt_normal():
    assert is_true(simplify(_b(tvl_gt(TVLInt.Def(5), TVLInt.Def(3)))))
    assert is_false(simplify(_b(tvl_gt(TVLInt.Def(3), TVLInt.Def(5)))))


def test_eq_normal():
    assert is_true(simplify(_b(tvl_eq(TVLInt.Def(5), TVLInt.Def(5)))))
    assert is_false(simplify(_b(tvl_eq(TVLInt.Def(5), TVLInt.Def(3)))))


def test_ne_normal():
    assert is_true(simplify(_b(tvl_ne(TVLInt.Def(5), TVLInt.Def(3)))))


# --- logic: two-valued (operands are Def(Bool)) ---


def test_and_two_valued():
    assert is_true(simplify(_b(tvl_and(TVLBool.Def(True), TVLBool.Def(True)))))
    assert is_false(simplify(_b(tvl_and(TVLBool.Def(True), TVLBool.Def(False)))))


def test_or_two_valued():
    assert is_true(simplify(_b(tvl_or(TVLBool.Def(False), TVLBool.Def(True)))))
    assert is_false(simplify(_b(tvl_or(TVLBool.Def(False), TVLBool.Def(False)))))


def test_not_two_valued():
    assert is_true(simplify(_b(tvl_not(TVLBool.Def(False)))))
    assert is_false(simplify(_b(tvl_not(TVLBool.Def(True)))))


# --- exists: the ONLY operator that senses presence ---


def test_exists_present():
    assert is_true(simplify(_b(exists_int(TVLInt.Def(5)))))


def test_exists_missing():
    assert is_false(simplify(_b(exists_int(TVLInt.Missing))))


# --- the canonical not(missing) semantics (leaf collapse → not(false)=true) ---


def test_not_of_missing_comparison_is_true():
    # not(gt(5, Missing)) = not(False) = True  (collapse, then two-valued not)
    r = tvl_not(tvl_gt(TVLInt.Def(5), TVLInt.Missing))
    assert is_true(simplify(_b(r)))
