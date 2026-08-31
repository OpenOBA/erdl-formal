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
    BoolSort,
    Datatype,
    If,
    IntSort,
    Not,
    Or,
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
