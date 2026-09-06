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

"""Symbolic compiler: ERDL S-expression → Z3 TVL.

Compiles the expression tree to Z3 three-valued logic, following the
denotational semantics (`docs/semantics.md`). Covers the full 34-node kernel:
field / literal / and / or / not / comparison / in / string / exists / length /
between / quantifier / arithmetic / time / aggregate.

S-expression form (SPEC §12 external form — single-key object, aligned with
the engine's ``s-expression.ts`` ``fromSExpr``):

    {"field": "path"} · {"var": "path"} · bare value = literal
    {"and": [...]} · {"or": [...]} · {"not": arg}
    {"eq"|"ne"|"gt"|"gte"|"lt"|"lte": [left, right]}
    {"in": [left, members]}                       (members = bare array literal)
    {"contains"|"match"|"starts_with"|"ends_with": [left, right]}
    {"exists": arg} · {"length": arg} · {"between": [value, min, max]}
    {"all"|"any"|"none": {"binding": "x", "over": field, "predicate": expr}}
    {"add"|"sub"|"mul"|"div"|"round": [...]}
    {"days_between": [from, to]} · {"epoch_ms": arg}
    {"date_add": {"unit", "base", "amount"}} · {"date_part": {"unit", "arg"}}
    {"month_last_day": arg}
    {"count"|"sum"|"avg"|"min"|"max": over}       (over = array field)

Array modeling (length-variable, not a fixed-length tuple): an array field with
``cardinality`` N contributes a **runtime length** free variable ``len ∈ [0, N]``
and N raw-τ element variables; only indices ``i < len`` participate in
quantifier/aggregate evaluation. This makes E8 (empty-array fold) and §7.3(e)
(empty-array aggregate fold) reachable — they were previously dead code because
the array was modeled as exactly-N elements.
"""

from decimal import Decimal
from fractions import Fraction

from z3 import BoolSort, Const, Int, IntSort, Not, StringSort

from .field_contracts import Schema
from .fixed_point import to_scale14_int
from .quantifiers import tvl_all, tvl_any, tvl_none
from .tvl import (
    AggVal,
    _agg_cmp_bool,
    _agg_cmp_num,
    agg_bool,
    agg_exists,
    agg_is_empty,
    agg_num,
    agg_to_int,
    TVLBool,
    TVLInt,
    TVLStr,
    exists_bool,
    exists_int,
    exists_str,
    is_missing_bool,
    is_missing_int,
    is_missing_str,
    str_def,
    tvl_add,
    tvl_aggregate,
    tvl_and,
    tvl_between,
    tvl_contains,
    tvl_days_between,
    tvl_div,
    tvl_ends_with,
    tvl_eq,
    tvl_eq_bool,
    tvl_eq_str,
    tvl_gt,
    tvl_gt_str,
    tvl_gte,
    tvl_gte_str,
    tvl_in,
    tvl_in_bool,
    tvl_in_str,
    tvl_length,
    tvl_lt,
    tvl_lt_str,
    tvl_lte,
    tvl_lte_str,
    tvl_match,
    tvl_mul,
    tvl_ne,
    tvl_ne_bool,
    tvl_ne_str,
    tvl_not,
    tvl_or,
    tvl_round,
    tvl_starts_with,
    tvl_sub,
    val_bool,
    val_int,
)

from .calendar import tvl_date_add, tvl_date_part, tvl_epoch_ms, tvl_month_last_day
from .regex import RegexError

_COMPARE_OPS = ["eq", "ne", "gt", "gte", "lt", "lte"]
_STRING_OPS = ["contains", "match", "starts_with", "ends_with"]
_ARITH_OPS = ["add", "sub", "mul", "div", "round"]
_QUANT_KINDS = ["all", "any", "none"]
_AGGREGATE_FNS = ["count", "sum", "avg", "min", "max"]


class CompileContext:
    """Maps field paths to free variables (schema-typed), lazily created.

    Scalar fields → TVL (Def | Missing). Array fields → a length free variable
    ``len ∈ [0, cardinality]`` + ``cardinality`` raw-τ element variables.
    Quantifier bindings are held in ``self._bindings`` during predicate compile.
    All array length constraints accumulate in ``self.constraints`` (assert via
    ``assume()``).
    """

    def __init__(self, schema: Schema):
        self.schema = schema
        self._fields = {}
        self._array_lens = {}
        self._array_elems = {}
        self._bindings = {}
        self.constraints = []

    def _sort(self, type_name):
        if type_name == "bool":
            return TVLBool
        if type_name == "int":
            return TVLInt
        if type_name == "string":
            return TVLStr
        raise NotImplementedError(
            f"field type {type_name!r} not in the supported subset (int/bool/string)"
        )

    def _raw_sort(self, type_name):
        """Raw (non-TVL) sort for array elements — Array<τ> elements are τ, not TVL(τ)."""
        if type_name == "bool":
            return BoolSort()
        if type_name == "int":
            return IntSort()
        if type_name == "string":
            return StringSort()
        raise NotImplementedError(
            f"array element type {type_name!r} not in the supported subset (int/bool/string)"
        )

    def field(self, path):
        if path not in self._fields:
            c = self.schema.get(path)
            self._fields[path] = Const(f"field[{path}]", self._sort(c.type if c else "int"))
        return self._fields[path]

    def var(self, path):
        """Var node — a quantifier binding, or the '$' context namespace.

        In a quantifier predicate, ``var(binding)`` resolves to the current
        element (already wrapped as a TVL by ``_quantifier``). Outside a
        quantifier, ``var('$')`` / ``var('$.path')`` is a free context variable
        (default int — the '$' namespace has no declared type source yet).
        """
        if path in self._bindings:
            return self._bindings[path]
        key = f"$[{path}]"
        if key not in self._fields:
            self._fields[key] = Const(f"var[{path}]", self._sort("int"))
        return self._fields[key]

    def array_len(self, path):
        """Runtime length free variable for an array field (0..cardinality)."""
        if path not in self._array_lens:
            n = self.schema.cardinality(path)
            v = Int(f"len[{path}]")
            self._array_lens[path] = v
            self.constraints.append(v >= 0)
            self.constraints.append(v <= n)
        return self._array_lens[path]

    def array_elements(self, path):
        """The ``cardinality`` raw-τ element variables of an array field."""
        if path not in self._array_elems:
            n = self.schema.cardinality(path)
            c = self.schema.get(path)
            elem_ty = (c.element_type if c else None) or "int"
            self._array_elems[path] = [
                Const(f"elem[{path}][{i}]", self._raw_sort(elem_ty)) for i in range(n)
            ]
        return self._array_elems[path]

    def missing(self, path):
        """Schema absence: the field is Missing (type-dispatched by field type)."""
        f = self.field(path)
        c = self.schema.get(path)
        ty = c.type if c else "int"
        if ty == "bool":
            return is_missing_bool(f)
        if ty == "string":
            return is_missing_str(f)
        return is_missing_int(f)

    def premise(self, path):
        """Schema premise: the field is present (not Missing)."""
        return Not(self.missing(path))

    def assume(self, solver):
        """Assert all accumulated array-length constraints on ``solver``."""
        for c in self.constraints:
            solver.add(c)


def _wrap_tvl(raw, elem_ty):
    """Wrap a raw-τ array element as a present (Def) TVL value."""
    if elem_ty == "bool":
        return TVLBool.Def(raw)
    if elem_ty == "string":
        return TVLStr.Def(raw)
    return TVLInt.Def(raw)


def _array_path(over):
    """Extract the array field path from an ``over`` operand (a field node)."""
    if isinstance(over, dict) and "field" in over and len(over) == 1:
        return str(over["field"])
    raise NotImplementedError(
        f"quantifier/aggregate `over` must be a {{field: ...}} node, got {over!r}"
    )


def _is_array_field(ctx, path):
    """True iff ``path`` is contracted as an array field (not scalar / missing)."""
    c = ctx.schema.get(path)
    return c is not None and c.type == "array"


def _fold(fn, args):
    acc = args[0]
    for a in args[1:]:
        acc = fn(acc, a)
    return acc


def _coerce_bool(x):
    """Coerce an operand to a boolean TVL via toBoolean (strict ``=== true``).

    - TVLBool → x (already boolean);
    - AggVal → agg_bool(x) (empty array == false, num == numeric);
    - TVLInt / TVLStr → Def(False) (no non-bool value is ``=== true``).
    """
    s = x.sort()
    if s == TVLBool:
        return x
    if s == AggVal:
        return agg_bool(x)
    # int / string operands are never === true (SPEC §11.2 no implicit conversion).
    return TVLBool.Def(False)


def _coerce_int(x):
    """Coerce an operand to an int TVL.

    - TVLInt → x;
    - AggVal → agg_to_int(x) (empty → Missing, num → Def(v));
    - TVLStr / TVLBool → Missing (engine toRational → null → EvalError).
    """
    s = x.sort()
    if s == TVLInt:
        return x
    if s == AggVal:
        return agg_to_int(x)
    # non-numeric (string / bool) → Missing (E12 EvalError approximation).
    return TVLInt.Missing


_EQ_NE_INT = {"eq": tvl_eq, "ne": tvl_ne}
_EQ_NE_STR = {"eq": tvl_eq_str, "ne": tvl_ne_str}
_EQ_NE_BOOL = {"eq": tvl_eq_bool, "ne": tvl_ne_bool}
_ORDER_INT = {"gt": tvl_gt, "gte": tvl_gte, "lt": tvl_lt, "lte": tvl_lte}
_ORDER_STR = {"gt": tvl_gt_str, "gte": tvl_gte_str, "lt": tvl_lt_str, "lte": tvl_lte_str}


def _cmp_eq(op, a, b):
    """Type-dispatched equality/inequality (int / string / bool / AggVal)."""
    sa, sb = a.sort(), b.sort()
    # AggVal operand (empty == boolean false; num == numeric).
    if sa == AggVal or sb == AggVal:
        agg, other = (a, b) if sa == AggVal else (b, a)
        so = other.sort()
        if so == TVLBool:
            return _agg_cmp_bool(op, agg, other)
        if so == TVLInt:
            return _agg_cmp_num(op, agg, other, is_missing_int(other), val_int(other))
        raise TypeError(f"eq/ne: AggVal vs {so} unsupported")
    if sa != sb:
        # SPEC §7.3(a): a type-mismatched comparison returns false (no implicit
        # conversion) — not a compile error. Aligns the verifier with the engine
        # (G4 fix) and with the frozen vectors.
        return TVLBool.Def(False)
    if sa == TVLInt:
        return _EQ_NE_INT[op](a, b)
    if sa == TVLStr:
        return _EQ_NE_STR[op](a, b)
    if sa == TVLBool:
        return _EQ_NE_BOOL[op](a, b)
    raise NotImplementedError(f"eq/ne on sort {sa!r} not supported")


def _cmp_order(op, a, b):
    """Ordering (gt/gte/lt/lte) — int / string / AggVal operands."""
    sa, sb = a.sort(), b.sort()
    if sa == AggVal or sb == AggVal:
        agg, other = (a, b) if sa == AggVal else (b, a)
        so = other.sort()
        if so == TVLBool:
            return _agg_cmp_bool(op, agg, other)
        if so == TVLInt:
            return _agg_cmp_num(op, agg, other, is_missing_int(other), val_int(other))
        raise TypeError(f"ordering op {op!r}: AggVal vs {so} unsupported")
    if sa != sb:
        # SPEC §7.3(a): type-mismatched ordering folds false (no implicit conversion).
        return TVLBool.Def(False)
    if sa == TVLInt:
        return _ORDER_INT[op](a, b)
    if sa == TVLStr:
        return _ORDER_STR[op](a, b)
    raise NotImplementedError(f"ordering op {op!r} only supports int/string fields, got {sa!r}")


def _exists(x):
    """Type-dispatched field-presence sense (int / string / bool / AggVal)."""
    s = x.sort()
    if s == AggVal:
        return agg_exists(x)
    if s == TVLInt:
        return exists_int(x)
    if s == TVLStr:
        return exists_str(x)
    if s == TVLBool:
        return exists_bool(x)
    raise NotImplementedError(f"exists on sort {s!r} not supported")


def _in(x, members):
    """Type-dispatched set membership (int / string / bool).

    A member whose sort differs from the field is a type-mismatched comparison
    (SPEC §7.3(a)) → Def(False), not a compile error.
    """
    s = x.sort()
    if members and any(m.sort() != s for m in members):
        return TVLBool.Def(False)
    if s == TVLInt:
        return tvl_in(x, members)
    if s == TVLStr:
        return tvl_in_str(x, members)
    if s == TVLBool:
        return tvl_in_bool(x, members)
    raise NotImplementedError(f"in on sort {s!r} not supported")


def compile_expr(expr, ctx: CompileContext):
    """Compile a SPEC §12 S-expression (single-key object) to a Z3 TVL expression."""
    if isinstance(expr, dict):
        return _compile_node(expr, ctx)
    # bare value → literal
    return _lit(expr)


def _compile_node(expr, ctx):
    keys = list(expr.keys())
    if len(keys) != 1:
        raise NotImplementedError(
            f"each S-expression node must have exactly one key, got {keys}"
        )
    key = keys[0]
    val = expr[key]

    if key == "field":
        return ctx.field(str(val))
    if key == "var":
        return ctx.var(str(val))
    if key == "and":
        return _fold(tvl_and, [_coerce_bool(compile_expr(a, ctx)) for a in val])
    if key == "or":
        return _fold(tvl_or, [_coerce_bool(compile_expr(a, ctx)) for a in val])
    if key == "not":
        return tvl_not(_coerce_bool(compile_expr(val, ctx)))
    if key == "not_exists":
        # Simple operator not_exists → not(exists(...)) (SPEC §5.2 lenient alias;
        # the ONE not_* whose bare form is valid: it senses field absence, no
        # exists-guard needed). Aligns the verifier's 38-key set with the engine's
        # s-expression.ts and the SPEC S-expr key set.
        return tvl_not(_exists(compile_expr(val, ctx)))

    if key in _COMPARE_OPS:
        left, right = val[0], val[1]
        # null literal handling (SPEC §7.3(a) + §5.2, left-anchored fail-closed).
        # Engine semantics (verified against @openoba/erdl):
        #   left nullish & right nullish → eq=true, ne=false
        #   left nullish, right non-null → eq=false, ne=false (fail-closed)
        #   left non-null, right nullish → eq=false, ne=true (!= null senses presence)
        if left is None or right is None:
            if left is None and right is None:
                return TVLBool.Def(True) if key == "eq" else TVLBool.Def(False)
            if left is None:
                # null OP <non-null>: eq senses absence (eq = not exists), ne is always false.
                if key == "ne":
                    return TVLBool.Def(False)
                return tvl_not(_exists(compile_expr(right, ctx)))
            # right is None, left is non-null: == null senses absence; != null senses presence.
            sense = _exists(compile_expr(left, ctx))
            return sense if key == "ne" else tvl_not(sense)
        if key in ("eq", "ne"):
            return _cmp_eq(key, compile_expr(left, ctx), compile_expr(right, ctx))
        return _cmp_order(key, compile_expr(left, ctx), compile_expr(right, ctx))

    if key == "in":
        if not isinstance(val[1], list):
            # right operand is not an array → false (engine type_mismatch).
            return TVLBool.Def(False)
        x = compile_expr(val[0], ctx)
        members = [compile_expr(m, ctx) for m in val[1]]
        return _in(x, members)

    if key in _STRING_OPS:
        left = compile_expr(val[0], ctx)
        if key == "match":
            # match: left non-string → false; ReDoS / non-regular pattern → false
            # (engine folds both via safeRegExp catch + regex_re_dos warning).
            if left.sort() != TVLStr or not isinstance(val[1], str):
                return TVLBool.Def(False)
            try:
                return tvl_match(left, val[1])
            except RegexError:
                return TVLBool.Def(False)
        right = compile_expr(val[1], ctx)
        if left.sort() != TVLStr or right.sort() != TVLStr:
            # non-string operand → false (strict type matching §5.2/§11.2).
            return TVLBool.Def(False)
        fn = {
            "contains": tvl_contains,
            "starts_with": tvl_starts_with,
            "ends_with": tvl_ends_with,
        }[key]
        return fn(left, right)

    if key == "exists":
        return _exists(compile_expr(val, ctx))
    if key == "length":
        return tvl_length(compile_expr(val, ctx))
    if key == "between":
        return tvl_between(
            _coerce_int(compile_expr(val[0], ctx)),
            _coerce_int(compile_expr(val[1], ctx)),
            _coerce_int(compile_expr(val[2], ctx)),
        )

    if key in _QUANT_KINDS:
        return _quantifier(key, val, ctx)

    if key in _ARITH_OPS:
        return _arith(key, [_coerce_int(compile_expr(a, ctx)) for a in val])

    if key == "days_between":
        return tvl_days_between(compile_expr(val[0], ctx), compile_expr(val[1], ctx))
    if key == "epoch_ms":
        return tvl_epoch_ms(compile_expr(val, ctx))
    if key == "date_add":
        return tvl_date_add(val["unit"], compile_expr(val["base"], ctx), compile_expr(val["amount"], ctx))
    if key == "date_part":
        return tvl_date_part(val["unit"], compile_expr(val["arg"], ctx))
    if key == "month_last_day":
        return tvl_month_last_day(compile_expr(val, ctx))

    if key in _AGGREGATE_FNS:
        return _aggregate(key, val, ctx)

    raise NotImplementedError(f"unknown S-expression key: {key!r}")


def _arith(op, args):
    if op == "round":
        if len(args) != 1:
            raise NotImplementedError("round requires exactly one operand")
        return tvl_round(args[0])
    fn = {"add": tvl_add, "sub": tvl_sub, "mul": tvl_mul, "div": tvl_div}[op]
    if len(args) < 2:
        raise NotImplementedError(f"{op} requires at least two operands")
    return _fold(fn, args)


def _quantifier(kind, q, ctx):
    """Compile a quantifier {all|any|none: {binding, over, predicate}}.

    Binds ``binding`` to each of the ``cardinality`` raw-τ elements and compiles
    the predicate with that binding; only indices ``i < len`` participate (the
    guard is applied inside ``tvl_all/any/none`` via the length variable).

    ``over`` a non-array (scalar / missing) field → Def(False) (SPEC §7.3(e)
    type_mismatch, folded — the engine folds the same way).
    """
    binding = str(q["binding"])
    over = q["over"]
    predicate = q["predicate"]
    arr_path = _array_path(over)
    if not _is_array_field(ctx, arr_path):
        return TVLBool.Def(False)
    length = ctx.array_len(arr_path)
    elems = ctx.array_elements(arr_path)
    c = ctx.schema.get(arr_path)
    elem_ty = (c.element_type if c else None) or "int"

    preds = []
    for i in range(len(elems)):
        ctx._bindings[binding] = _wrap_tvl(elems[i], elem_ty)
        preds.append(val_bool(compile_expr(predicate, ctx)))
        del ctx._bindings[binding]

    fn = {"all": tvl_all, "any": tvl_any, "none": tvl_none}[kind]
    return fn(length, preds)


def _aggregate(fn, over, ctx):
    """Compile an aggregate {count|sum|avg|min|max: over} over a length-variable array.

    ``over`` a non-array field → Missing (SPEC §7.3(e): null + type_mismatch,
    folded).
    """
    arr_path = _array_path(over)
    if not _is_array_field(ctx, arr_path):
        return TVLInt.Missing
    length = ctx.array_len(arr_path)
    elems = ctx.array_elements(arr_path)
    return tvl_aggregate(fn, length, elems)


def _lit(value):
    if isinstance(value, bool):
        return TVLBool.Def(value)
    if isinstance(value, int):
        return TVLInt.Def(value)
    if isinstance(value, float):
        # Decimal literals (money thresholds) enter as float; convert through
        # the shortest round-trip decimal (str) so 0.1 stays exactly 1/10, and
        # scientific notation (str of very small/large floats) parses exactly.
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"literal {value!r} is not a finite decimal")
        return TVLInt.Def(to_scale14_int(Fraction(Decimal(str(value)))))
    if isinstance(value, Fraction):
        return TVLInt.Def(to_scale14_int(value))
    if isinstance(value, Decimal):
        return TVLInt.Def(to_scale14_int(Fraction(value)))
    if isinstance(value, str):
        return str_def(value)
    raise NotImplementedError(f"literal {value!r}")
