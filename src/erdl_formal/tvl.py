"""Three-valued logic (E11) — leaf-collapse semantics.

The ERDL kernel (spec v2.0 §10.2 E11) uses *leaf collapse*: a comparison whose
operand is a missing field collapses to ``false``; arithmetic collapses to
``EvaluationError`` (→ E12 tier folding). Boolean operators (and/or/not) are
therefore **two-valued** — they only ever see collapsed booleans.

Encoding: ADT ``TVL(τ) = Def(value: τ) | Missing``.

This is the spec-accurate model (NOT Kleene propagation — see the findings
document for the research that settled this).
"""

from z3 import (
    And,
    BoolSort,
    Contains,
    Datatype,
    If,
    IntSort,
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


# --- existence (the ONLY operator that senses field presence) -------------

def exists_int(x):
    """exists(field) = field is not Missing (E11: only way to sense presence)."""
    return TVLBool.Def(Not(is_missing_int(x)))


# --- two-valued boolean operators (leaves already collapsed) --------------

def tvl_and(a, b):
    """Standard two-valued AND — operands are Def(Bool), never Missing."""
    return TVLBool.Def(val_bool(a) & val_bool(b))


def tvl_or(a, b):
    return TVLBool.Def(val_bool(a) | val_bool(b))


def tvl_not(a):
    return TVLBool.Def(Not(val_bool(a)))


# --- 存在/量纲 + 时间戳层（Int）---

def tvl_between(x, a, b):
    """闭区间 [a, b]（仅数值）；任一 Missing → Def(False)."""
    return TVLBool.Def(
        If(
            Or(is_missing_int(x), is_missing_int(a), is_missing_int(b)),
            False,
            And(val_int(a) <= val_int(x), val_int(x) <= val_int(b)),
        )
    )


def tvl_days_between(t1, t2):
    """UTC 天数差：floor((t1−t2)/86400000)；任一 Missing → Missing（算术式折叠）。"""
    return If(
        Or(is_missing_int(t1), is_missing_int(t2)),
        TVLInt.Missing,
        TVLInt.Def((val_int(t1) - val_int(t2)) / 86400000),
    )


# --- 字符串（contains/starts_with/ends_with + length）---

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


def tvl_length(s):
    """length（Unicode 码点；Z3 字符串为 8-bit 序列，非 ASCII 时码点/字节有差异）。"""
    return If(is_missing_str(s), TVLInt.Missing, TVLInt.Def(Length(val_str(s))))


# --- 集合（in）+ 线性算术（add/sub，精确）---

def tvl_in(x, members):
    """x ∈ members（有限集合，标量成员）；x Missing → Def(false)."""
    return TVLBool.Def(
        If(is_missing_int(x), False, Or(*[val_int(x) == val_int(m) for m in members]))
    )


def _arith_binary(a, b, op):
    """线性定点算术（scale 统一，加减精确）；任一 Missing → Missing."""
    return If(
        Or(is_missing_int(a), is_missing_int(b)),
        TVLInt.Missing,
        TVLInt.Def(op(val_int(a), val_int(b))),
    )


def tvl_add(a, b):
    return _arith_binary(a, b, lambda x, y: x + y)


def tvl_sub(a, b):
    return _arith_binary(a, b, lambda x, y: x - y)


# --- 聚合（count/sum，空数组折叠）---

def tvl_aggregate(fn, elements):
    """aggregate over a fixed-length array. fn in {count, sum}.

    count(空)=0（len=0）；sum(空)=0（Sum([])=0）。avg/min/max 空数组折叠 false，
    需 None 类型，M3.1 暂不做。
    """
    if fn == "count":
        return TVLInt.Def(len(elements))
    if fn == "sum":
        return TVLInt.Def(Sum([val_int(e) for e in elements]))
    raise NotImplementedError(f"aggregate {fn!r} not in POC subset (avg/min/max need None folding)")


# --- 非线性定点算术（mul/div，QF_NIA + half-even 舍入）---

_SCALE = 10 ** 14


def _round_half_even_div(num, den):
    """round_half_even(num / den)，num/den 为 Z3 Int（floor div + 欧几里得 mod）。"""
    q = num / den
    r = num % den
    return If(2 * r < den, q, If(2 * r > den, q + 1, If(q % 2 == 0, q, q + 1)))


def tvl_mul(a, b):
    """定点乘法：round_half_even(a_scaled * b_scaled / 10^14)；Missing → Missing."""
    return If(
        Or(is_missing_int(a), is_missing_int(b)),
        TVLInt.Missing,
        TVLInt.Def(_round_half_even_div(val_int(a) * val_int(b), _SCALE)),
    )


def tvl_div(a, b):
    """定点除法：round_half_even(a_scaled * 10^14 / b_scaled)；除零/Missing → Missing."""
    return If(
        Or(is_missing_int(a), is_missing_int(b), val_int(b) == 0),
        TVLInt.Missing,
        TVLInt.Def(_round_half_even_div(val_int(a) * _SCALE, val_int(b))),
    )
