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

"""Three-valued logic (E11) — leaf-collapse semantics.

The ERDL kernel (spec v2.1 §7.2 E11 / §7.3(a)) uses *leaf collapse*: a comparison whose
operand is a missing field collapses to ``false``; arithmetic collapses to
``EvaluationError`` (→ E12 tier folding). Boolean operators (and/or/not) are
therefore **two-valued** — they only ever see collapsed booleans.

Encoding: ADT ``TVL(τ) = Def(value: τ) | Missing``.

This is the spec-accurate model (NOT Kleene propagation; leaf collapse per
spec v2.1 §7.2 E11).
"""

from z3 import (
    And,
    BoolSort,
    Contains,
    Datatype,
    If,
    InRe,
    IntSort,
    IntVal,
    Length,
    Not,
    Or,
    PrefixOf,
    StringSort,
    StringVal,
    SuffixOf,
    Sum,
)

# --- TVL datatypes --------------------------------------------------------

TVLInt = Datatype("TVLInt")
TVLInt.declare("Def", ("value", IntSort()))
TVLInt.declare("Missing")
TVLInt = TVLInt.create()

TVLBool = Datatype("TVLBool")
TVLBool.declare("Def", ("value", BoolSort()))
TVLBool.declare("Missing")
TVLBool = TVLBool.create()

TVLStr = Datatype("TVLStr")
TVLStr.declare("Def", ("value", StringSort()))
TVLStr.declare("Missing")
TVLStr = TVLStr.create()


def is_missing_str(x):
    return TVLStr.is_Missing(x)


def val_str(x):
    return TVLStr.value(x)


def str_def(s):
    """Wrap a Python str into a TVLStr.Def (Z3 5.x does not auto-coerce str)."""
    return TVLStr.Def(StringVal(s))


def is_missing_int(x):
    return TVLInt.is_Missing(x)


def val_int(x):
    return TVLInt.value(x)


def is_missing_bool(x):
    return TVLBool.is_Missing(x)


def val_bool(x):
    return TVLBool.value(x)


# --- E11 leaf collapse: comparisons --------------------------------------

def _collapse_binary(a, b, op):
    """Binary comparison with leaf collapse: any Missing operand → Def(False)."""
    return TVLBool.Def(
        If(
            Or(is_missing_int(a), is_missing_int(b)),
            False,
            op(val_int(a), val_int(b)),
        )
    )


def tvl_gt(a, b):
    return _collapse_binary(a, b, lambda x, y: x > y)


def tvl_gte(a, b):
    return _collapse_binary(a, b, lambda x, y: x >= y)


def tvl_lt(a, b):
    return _collapse_binary(a, b, lambda x, y: x < y)


def tvl_lte(a, b):
    return _collapse_binary(a, b, lambda x, y: x <= y)


def tvl_eq(a, b):
    return _collapse_binary(a, b, lambda x, y: x == y)


def tvl_ne(a, b):
    return _collapse_binary(a, b, lambda x, y: x != y)


def _collapse_bool_binary(a, b, op):
    """Boolean comparison with leaf collapse: any Missing operand → Def(False)."""
    return TVLBool.Def(
        If(Or(is_missing_bool(a), is_missing_bool(b)), False, op(val_bool(a), val_bool(b)))
    )


def tvl_eq_bool(a, b):
    return _collapse_bool_binary(a, b, lambda x, y: x == y)


def tvl_ne_bool(a, b):
    return _collapse_bool_binary(a, b, lambda x, y: x != y)


# --- existence (the ONLY operator that senses field presence) -------------

def exists_int(x):
    """exists(field) = field is not Missing (E11: only way to sense presence)."""
    return TVLBool.Def(Not(is_missing_int(x)))


def exists_str(x):
    return TVLBool.Def(Not(is_missing_str(x)))


def exists_bool(x):
    return TVLBool.Def(Not(is_missing_bool(x)))


# --- two-valued boolean operators (leaves already collapsed) --------------

def tvl_and(a, b):
    """Standard two-valued AND — operands are Def(Bool), never Missing."""
    return TVLBool.Def(val_bool(a) & val_bool(b))


def tvl_or(a, b):
    return TVLBool.Def(val_bool(a) | val_bool(b))


def tvl_not(a):
    return TVLBool.Def(Not(val_bool(a)))


# --- existence/dimension + timestamp layer (Int) ---

def tvl_between(x, a, b):
    """Closed interval [a, b] (numeric only); any Missing → Def(False)."""
    return TVLBool.Def(
        If(
            Or(is_missing_int(x), is_missing_int(a), is_missing_int(b)),
            False,
            And(val_int(a) <= val_int(x), val_int(x) <= val_int(b)),
        )
    )


def tvl_days_between(t1, t2):
    """UTC day difference: floor((t2−t1)/86400000) (erdl semantics = to − from); any Missing → Missing."""
    return If(
        Or(is_missing_int(t1), is_missing_int(t2)),
        TVLInt.Missing,
        TVLInt.Def((val_int(t2) - val_int(t1)) / 86400000),
    )


# --- string (contains/starts_with/ends_with + length) ---

def _collapse_str_binary(a, b, op):
    return TVLBool.Def(
        If(Or(is_missing_str(a), is_missing_str(b)), False, op(val_str(a), val_str(b)))
    )


def tvl_contains(s, t):
    return _collapse_str_binary(s, t, lambda x, y: Contains(x, y))


def tvl_starts_with(s, t):
    return _collapse_str_binary(s, t, lambda x, y: PrefixOf(y, x))


def tvl_ends_with(s, t):
    return _collapse_str_binary(s, t, lambda x, y: SuffixOf(y, x))


def tvl_eq_str(a, b):
    """String equality (leaf collapse: any Missing operand → Def(False))."""
    return _collapse_str_binary(a, b, lambda x, y: x == y)


def tvl_ne_str(a, b):
    return _collapse_str_binary(a, b, lambda x, y: x != y)


def tvl_gt_str(a, b):
    """String ordering, lexicographic (Unicode code-point order); Missing → Def(False)."""
    return _collapse_str_binary(a, b, lambda x, y: x > y)


def tvl_gte_str(a, b):
    return _collapse_str_binary(a, b, lambda x, y: x >= y)


def tvl_lt_str(a, b):
    return _collapse_str_binary(a, b, lambda x, y: x < y)


def tvl_lte_str(a, b):
    return _collapse_str_binary(a, b, lambda x, y: x <= y)


def tvl_length(s):
    """length (Unicode code points — Z3 StringSort is Seq(Char), Length counts code points)."""
    return If(is_missing_str(s), TVLInt.Missing, TVLInt.Def(Length(val_str(s))))


def tvl_match(s, pattern):
    """match: ERDL safe-regex subset → Z3 Re (JS RegExp.test semantics, §7.3(d)).

    Raises RegexError for patterns outside the safe subset (backreferences /
    lookaround / inline flags), matching the runtime's load-time rejection.
    """
    from .regex import compile_match
    re_ = compile_match(pattern)
    return TVLBool.Def(If(is_missing_str(s), False, InRe(val_str(s), re_)))


# --- set (in) + linear arithmetic (add/sub, exact) ---

def tvl_in(x, members):
    """x ∈ members (finite set, scalar members); x Missing → Def(false)."""
    return TVLBool.Def(
        If(is_missing_int(x), False, Or(*[val_int(x) == val_int(m) for m in members]))
    )


def tvl_in_str(x, members):
    """String set membership (leaf collapse: Missing → Def(False))."""
    return TVLBool.Def(
        If(is_missing_str(x), False, Or(*[val_str(x) == val_str(m) for m in members]))
    )


def tvl_in_bool(x, members):
    """Bool set membership (leaf collapse: Missing → Def(False))."""
    return TVLBool.Def(
        If(is_missing_bool(x), False, Or(*[val_bool(x) == val_bool(m) for m in members]))
    )


def _arith_binary(a, b, op):
    """Linear fixed-point arithmetic (unified scale, exact add/sub); any Missing → Missing."""
    return If(
        Or(is_missing_int(a), is_missing_int(b)),
        TVLInt.Missing,
        TVLInt.Def(op(val_int(a), val_int(b))),
    )


def tvl_add(a, b):
    return _arith_binary(a, b, lambda x, y: x + y)


def tvl_sub(a, b):
    return _arith_binary(a, b, lambda x, y: x - y)


# --- aggregate (count/sum/avg/min/max over a length-variable array) ---

def _guarded_sum(elements, length):
    """Σ elements[i] for i < length (0 for i >= length). length is a Z3 Int var."""
    if not elements:
        return IntVal(0)
    return Sum([If(i < length, elements[i], 0) for i in range(len(elements))])


def _fold_min(elements, length):
    """min over the first `length` elements (length >= 1 assumed; guarded by caller)."""
    m = elements[0]
    for i in range(1, len(elements)):
        m = If(And(i < length, elements[i] < m), elements[i], m)
    return m


def _fold_max(elements, length):
    """max over the first `length` elements (length >= 1 assumed; guarded by caller)."""
    m = elements[0]
    for i in range(1, len(elements)):
        m = If(And(i < length, elements[i] > m), elements[i], m)
    return m


def tvl_aggregate(fn, length, elements):
    """aggregate over an array of runtime length `length` (0..cardinality).

    `length` is a Z3 Int free variable; `elements` are `cardinality` raw-τ element
    variables (raw τ, not TVL). Only elements with index < length participate.

    count(empty)=0 · sum(empty)=0 — natural identities.
    avg/min/max(empty) → Missing (E11 leaf-collapse folds every comparison false),
    per SPEC §7.3(e) safe-failure folding (avoids div-by-zero / ±∞).
    """
    n = len(elements)
    if fn == "count":
        return TVLInt.Def(length)
    if fn == "sum":
        return TVLInt.Def(_guarded_sum(elements, length))
    if fn == "avg":
        s = _guarded_sum(elements, length)
        # round_half_even(sum / length) — length >= 1 (guarded), scale-14 fixed point
        return If(length == 0, TVLInt.Missing,
                  TVLInt.Def(_round_half_even_div_signed(s, length)))
    if fn == "min":
        if n == 0:
            return TVLInt.Missing
        return If(length == 0, TVLInt.Missing, TVLInt.Def(_fold_min(elements, length)))
    if fn == "max":
        if n == 0:
            return TVLInt.Missing
        return If(length == 0, TVLInt.Missing, TVLInt.Def(_fold_max(elements, length)))
    raise NotImplementedError(f"aggregate {fn!r} not supported")


# --- nonlinear fixed-point arithmetic (mul/div, QF_NIA + half-even rounding) ---

_SCALE = 10 ** 14


def _round_half_even_div(num, den):
    """round_half_even(num / den), den > 0; num/den are Z3 Ints (floor div + Euclidean mod)."""
    q = num / den
    r = num % den
    return If(2 * r < den, q, If(2 * r > den, q + 1, If(q % 2 == 0, q, q + 1)))


def _round_half_even_div_signed(num, den):
    """round_half_even(num / den) for arbitrary-sign den (den != 0).

    Normalizes to a positive denominator and applies the quotient sign after
    rounding (half-even is symmetric: round_half_even(-x) = -round_half_even(x)).
    """
    neg = (num < 0) != (den < 0)
    n = If(num < 0, -num, num)
    d = If(den < 0, -den, den)
    q = _round_half_even_div(n, d)
    return If(neg, -q, q)


def tvl_mul(a, b):
    """Fixed-point multiply: round_half_even(a_scaled * b_scaled / 10^14); Missing → Missing."""
    return If(
        Or(is_missing_int(a), is_missing_int(b)),
        TVLInt.Missing,
        TVLInt.Def(_round_half_even_div(val_int(a) * val_int(b), _SCALE)),
    )


def tvl_div(a, b):
    """Fixed-point divide: round_half_even(a_scaled * 10^14 / b_scaled); divide-by-zero/Missing → Missing."""
    return If(
        Or(is_missing_int(a), is_missing_int(b), val_int(b) == 0),
        TVLInt.Missing,
        TVLInt.Def(_round_half_even_div_signed(val_int(a) * _SCALE, val_int(b))),
    )


def tvl_round(a):
    """round node: half-even rounding to integer (erdl toDecimalString(scale=0)), result back at scale=14."""
    return If(
        is_missing_int(a),
        TVLInt.Missing,
        TVLInt.Def(_round_half_even_div(val_int(a), _SCALE) * _SCALE),
    )
