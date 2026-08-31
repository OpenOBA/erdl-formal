"""Symbolic compiler (M3): ERDL S-expression → Z3 TVL.

Compiles the expression tree to Z3 three-valued logic, following the
denotational semantics (`docs/semantics.md`). Covers the POC subset:
field / literal / and / or / not / comparison / exists / quantifier.
Arithmetic / string / time / aggregate are M3.1+.

S-expression form (aligned with the erdl external form):
  ["field", "path"] · ["lit", value] · ["and", a, b] · ["or", a, b] ·
  ["not", a] · ["eq"|"ne"|"gt"|"gte"|"lt"|"lte", a, b] · ["exists", a] ·
  ["all"|"any"|"none", "array_field"]
"""

from z3 import Const, Not

from .field_contracts import Schema
from .quantifiers import tvl_all, tvl_any, tvl_none
from .tvl import (
    TVLBool,
    TVLInt,
    TVLStr,
    exists_int,
    is_missing_bool,
    is_missing_int,
    is_missing_str,
    tvl_and,
    tvl_between,
    tvl_contains,
    tvl_days_between,
    tvl_ends_with,
    tvl_eq,
    tvl_gt,
    tvl_gte,
    tvl_length,
    tvl_lt,
    tvl_lte,
    tvl_ne,
    tvl_not,
    tvl_or,
    tvl_starts_with,
    str_def,
    val_bool,
)


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
            f"field type {type_name!r} not in POC subset (int/bool/string); "
            "rational/array need M3.1"
        )

    def field(self, path):
        if path not in self._fields:
            c = self.schema.get(path)
            self._fields[path] = Const(f"field[{path}]", self._sort(c.type if c else "int"))
        return self._fields[path]

    def array_element(self, path, i):
        key = f"{path}[{i}]"
        if key not in self._fields:
            c = self.schema.get(path)
            elem_ty = (c.element_type if c else None) or "bool"
            self._fields[key] = Const(f"field[{key}]", self._sort(elem_ty))
        return self._fields[key]

    def premise(self, path):
        """Schema premise: the field is present (not Missing)."""
        f = self.field(path)
        c = self.schema.get(path)
        ty = c.type if c else "int"
        if ty == "bool":
            return Not(is_missing_bool(f))
        if ty == "string":
            return Not(is_missing_str(f))
        return Not(is_missing_int(f))


_BINARY = {
    "eq": tvl_eq,
    "ne": tvl_ne,
    "gt": tvl_gt,
    "gte": tvl_gte,
    "lt": tvl_lt,
    "lte": tvl_lte,
}


def compile_expr(expr, ctx: CompileContext):
    """Compile an S-expression to a Z3 TVL expression."""
    if isinstance(expr, list):
        op = expr[0]
        if op == "field":
            return ctx.field(expr[1])
        if op == "lit":
            return _lit(expr[1])
        if op == "and":
            return tvl_and(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "or":
            return tvl_or(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "not":
            return tvl_not(compile_expr(expr[1], ctx))
        if op in _BINARY:
            return _BINARY[op](compile_expr(expr[1], ctx), compile_expr(expr[2], ctx))
        if op == "exists":
            return exists_int(compile_expr(expr[1], ctx))
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
        if op in ("all", "any", "none"):
            return _quantifier(op, expr[1], ctx)
        raise NotImplementedError(f"op {op!r} not in POC subset")
    # bare literal
    return _lit(expr)


def _lit(value):
    if isinstance(value, bool):
        return TVLBool.Def(value)
    if isinstance(value, int):
        return TVLInt.Def(value)
    if isinstance(value, str):
        return str_def(value)
    raise NotImplementedError(f"literal {value!r}")


def _quantifier(op, array_field, ctx):
    n = ctx.schema.cardinality(array_field)
    elems = [ctx.array_element(array_field, i) for i in range(n)]
    fn = {"all": tvl_all, "any": tvl_any, "none": tvl_none}[op]
    return fn(elems)
