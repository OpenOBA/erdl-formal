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
denotational semantics (`docs/semantics.md`). Covers the supported subset:
field / literal / and / or / not / comparison / exists / quantifier.
Arithmetic / string / time / aggregate are also encoded.

S-expression form (aligned with the erdl external form):
  ["field", "path"] · ["lit", value] · ["and", a, b] · ["or", a, b] ·
  ["not", a] · ["eq"|"ne"|"gt"|"gte"|"lt"|"lte", a, b] · ["exists", a] ·
  ["all"|"any"|"none", "array_field"]
"""

from decimal import Decimal
from fractions import Fraction

from z3 import BoolSort, Const, IntSort, Not, StringSort

from .field_contracts import Schema
from .fixed_point import to_scale14_int
from .quantifiers import tvl_all, tvl_any, tvl_none
from .tvl import (
    TVLBool,
    TVLInt,
    TVLStr,
    exists_bool,
    exists_int,
    exists_str,
    is_missing_bool,
    is_missing_int,
    is_missing_str,
    tvl_and,
    tvl_between,
    tvl_contains,
    tvl_days_between,
    tvl_ends_with,
    tvl_eq,
    tvl_eq_bool,
    tvl_eq_str,
    tvl_gt,
    tvl_gte,
    tvl_in,
    tvl_in_bool,
    tvl_in_str,
    tvl_length,
    tvl_lt,
    tvl_lte,
    tvl_ne,
    tvl_ne_bool,
    tvl_ne_str,
    tvl_not,
    tvl_or,
    tvl_add,
    tvl_div,
    tvl_mul,
    tvl_starts_with,
    tvl_sub,
    tvl_aggregate,
    tvl_round,
    tvl_match,
    str_def,
    val_bool,
)

from .calendar import tvl_date_add, tvl_date_part, tvl_epoch_ms, tvl_month_last_day


class CompileContext:
    """Maps field paths to free TVL variables (schema-typed), lazily created."""

    def __init__(self, schema: Schema):
        self.schema = schema
        self._fields = {}

    def _sort(self, type_name):
        if type_name == "bool":
            return TVLBool
        if type_name == "int":
            return TVLInt
        if type_name == "string":
            return TVLStr
        raise NotImplementedError(
            f"field type {type_name!r} not in the supported subset (int/bool/string); "
            "rational/array need cardinality support"
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
        """Context variable (var node; '$' or '$.path') — a free TVL variable.

        spec §5.3 defines var(v) = Def(ctx.$[v]) with no declared type, and the
        verification schema (field-contracts) has no '$' entries, so the type
        defaults to int (same fallback as an untyped field). var is currently
        unused in rules; when it is, the '$' namespace needs a type source.
        """
        key = f"$[{path}]"
        if key not in self._fields:
            self._fields[key] = Const(f"var[{path}]", self._sort("int"))
        return self._fields[key]

    def array_element(self, path, i):
        key = f"{path}[{i}]"
        if key not in self._fields:
            c = self.schema.get(path)
            elem_ty = (c.element_type if c else None) or "bool"
            self._fields[key] = Const(f"field[{key}]", self._raw_sort(elem_ty))
        return self._fields[key]

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


_EQ_NE_INT = {"eq": tvl_eq, "ne": tvl_ne}
_EQ_NE_STR = {"eq": tvl_eq_str, "ne": tvl_ne_str}
_EQ_NE_BOOL = {"eq": tvl_eq_bool, "ne": tvl_ne_bool}
_ORDER = {"gt": tvl_gt, "gte": tvl_gte, "lt": tvl_lt, "lte": tvl_lte}


def _cmp_eq(op, a, b):
    """Type-dispatched equality/inequality (int / string / bool)."""
    sa, sb = a.sort(), b.sort()
    if sa != sb:
        raise TypeError(f"eq/ne operand sort mismatch: {sa} vs {sb}")
    if sa == TVLInt:
        return _EQ_NE_INT[op](a, b)
    if sa == TVLStr:
        return _EQ_NE_STR[op](a, b)
    if sa == TVLBool:
        return _EQ_NE_BOOL[op](a, b)
    raise NotImplementedError(f"eq/ne on sort {sa!r} not supported")


def _cmp_order(op, a, b):
    """Numeric ordering (gt/gte/lt/lte) — int fields only."""
    sa, sb = a.sort(), b.sort()
    if sa != sb:
        raise TypeError(f"ordering op {op!r} operand sort mismatch: {sa} vs {sb}")
    if sa != TVLInt:
        raise NotImplementedError(f"ordering op {op!r} only supports int fields, got {sa!r}")
    return _ORDER[op](a, b)


def _exists(x):
    """Type-dispatched field-presence sense (int / string / bool)."""
    s = x.sort()
    if s == TVLInt:
        return exists_int(x)
    if s == TVLStr:
        return exists_str(x)
    if s == TVLBool:
        return exists_bool(x)
    raise NotImplementedError(f"exists on sort {s!r} not supported")


def _in(x, members):
    """Type-dispatched set membership (int / string / bool)."""
    s = x.sort()
    if members and any(m.sort() != s for m in members):
        raise TypeError(f"in: member sort mismatch (field {s} vs member)")
    if s == TVLInt:
        return tvl_in(x, members)
    if s == TVLStr:
        return tvl_in_str(x, members)
    if s == TVLBool:
        return tvl_in_bool(x, members)
    raise NotImplementedError(f"in on sort {s!r} not supported")


def compile_expr(expr, ctx: CompileContext):
    """Compile an S-expression to a Z3 TVL expression."""
    if isinstance(expr, list):
        op = expr[0]
        if op == "field":
            return ctx.field(expr[1])
        if op == "var":
            return ctx.var(expr[1])
        if op == "lit":
            return _lit(expr[1])
        if op == "and":
            return tvl_and(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "or":
            return tvl_or(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "not":
            return tvl_not(compile_expr(expr[1], ctx))
        if op == "eq" or op == "ne":
            return _cmp_eq(op, compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op in ("gt", "gte", "lt", "lte"):
            return _cmp_order(op, compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "exists":
            return _exists(compile_expr(expr[1], ctx))
        if op == "between":
            return tvl_between(
                compile_expr(expr[1], ctx), compile_expr(expr[2], ctx), compile_expr(expr[3], ctx)
            )
        if op == "days_between":
            return tvl_days_between(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "contains":
            return tvl_contains(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "starts_with":
            return tvl_starts_with(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "ends_with":
            return tvl_ends_with(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "length":
            return tvl_length(compile_expr(expr[1], ctx))
        if op == "in":
            x = compile_expr(expr[1], ctx)
            members = [compile_expr(m, ctx) for m in expr[2]]
            return _in(x, members)
        if op == "add":
            return tvl_add(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "sub":
            return tvl_sub(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "mul":
            return tvl_mul(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "div":
            return tvl_div(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "aggregate":
            fn, array_field = expr[1], expr[2]
            n = ctx.schema.cardinality(array_field)
            elems = [ctx.array_element(array_field, i) for i in range(n)]
            return tvl_aggregate(fn, elems)
        if op == "round":
            return tvl_round(compile_expr(expr[1], ctx))
        if op == "match":
            return tvl_match(compile_expr(expr[1], ctx), expr[2])
        if op == "date_part":
            return tvl_date_part(expr[1], compile_expr(expr[2], ctx))
        if op == "month_last_day":
            return tvl_month_last_day(compile_expr(expr[1], ctx))
        if op == "epoch_ms":
            return tvl_epoch_ms(compile_expr(expr[1], ctx))
        if op == "date_add":
            return tvl_date_add(expr[1], compile_expr(expr[2], ctx), compile_expr(expr[3], ctx))
        if op in ("all", "any", "none"):
            return _quantifier(op, expr[1], ctx)
        raise NotImplementedError(f"op {op!r} not in the supported subset")
    # bare literal
    return _lit(expr)


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


def _quantifier(op, array_field, ctx):
    n = ctx.schema.cardinality(array_field)
    elems = [ctx.array_element(array_field, i) for i in range(n)]
    fn = {"all": tvl_all, "any": tvl_any, "none": tvl_none}[op]
    return fn(elems)
