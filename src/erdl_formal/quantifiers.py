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

"""Quantifier encoding (E8): all / any / none over a length-variable array.

E8 (spec v2.1 §7.2 / §7.3(b)): empty array → **all / any / none ALL fold to false** —
a deliberate safe deviation from the standard ``all([])=true`` vacuous truth,
to prevent fail-open ("no elements to check → treated as all-pass").

The array has a runtime length ``length`` (a Z3 Int free variable in [0, cardinality])
and ``cardinality`` element variables. ``preds[i]`` is the predicate evaluated on
element ``i`` (as a raw Bool). Only indices ``i < length`` participate:

- all:  ∀i<length. preds[i]      (empty → false)
- any:  ∃i<length. preds[i]      (empty → false)
- none: ∀i<length. ¬preds[i]     (empty → false)
"""

from z3 import And, If, Not, Or

from .tvl import TVLBool


def _guarded_preds(preds, length):
    """For each i, a term that is true when i >= length (out of range, ignored)."""
    return [If(i < length, p, True) for i, p in enumerate(preds)]


def tvl_all(length, preds):
    """all — empty → false; else ∧_{i<length} preds[i] (out-of-range → true)."""
    if not preds:
        return TVLBool.Def(False)
    guarded = _guarded_preds(preds, length)
    return TVLBool.Def(If(length == 0, False, And(*guarded)))


def tvl_any(length, preds):
    """any — empty → false; else ∨_{i<length} preds[i] (out-of-range → false)."""
    if not preds:
        return TVLBool.Def(False)
    terms = [And(i < length, p) for i, p in enumerate(preds)]
    return TVLBool.Def(If(length == 0, False, Or(*terms)))


def tvl_none(length, preds):
    """none — empty → false; else ∧_{i<length} ¬preds[i] (out-of-range → true)."""
    if not preds:
        return TVLBool.Def(False)
    guarded = [If(i < length, Not(p), True) for i, p in enumerate(preds)]
    return TVLBool.Def(If(length == 0, False, And(*guarded)))
