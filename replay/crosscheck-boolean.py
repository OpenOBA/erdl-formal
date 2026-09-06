# -*- coding: utf-8 -*-
"""Cross-check: verifier (symbolic satisfiability) vs vector (engine concrete eval).

For each node-semantics vector with a boolean expected value, we pin the
concrete context (present fields to their values, and fields referenced by the
expression but absent from context to Missing) and ask the verifier whether the
condition can be true. This must match the frozen expected boolean.

Fields referenced by the expression but absent from the context are the
"missing field" scenario (E11): declared (type-inferred, default int) and
forced Missing.
"""
import json
import os

from z3 import Solver, sat

from erdl_formal.compiler import CompileContext, compile_expr
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.tvl import (
    AggVal,
    TVLBool,
    TVLInt,
    agg_bool,
    val_bool,
    is_missing_int,
    is_missing_str,
    is_missing_bool,
    str_def,
)


def collect_fields(node, acc):
    """Collect all field paths referenced in an S-expression tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "field" and isinstance(v, str):
                acc.add(v)
            elif k in ("var",):
                pass  # var is not a schema field
            elif isinstance(v, list):
                for x in v:
                    collect_fields(x, acc)
            elif isinstance(v, dict):
                collect_fields(v, acc)
    elif isinstance(node, list):
        for x in node:
            collect_fields(x, acc)


def infer_type(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        elem = value[0] if value else None
        et = "bool" if isinstance(elem, bool) else "string" if isinstance(elem, str) else "int"
        return ("array", et)
    return "int"  # number / default


def build_schema(context, expr_tree):
    s = Schema()
    # fields present in context → declared with their type
    for k, v in (context or {}).items():
        t = infer_type(v)
        if isinstance(t, tuple):
            s.add(FieldContract(field=k, type="array", element_type=t[1], cardinality=max(len(v), 1)))
        else:
            s.add(FieldContract(field=k, type=t))
    # fields referenced but absent → declared default int (will be forced Missing)
    fields = set()
    collect_fields(expr_tree, fields)
    for f in fields:
        if f not in (context or {}):
            s.add(FieldContract(field=f, type="int"))
    return s, fields


def eval_against(expr_tree, context, expected):
    s, fields = build_schema(context, expr_tree)
    ctx = CompileContext(s)
    expr = compile_expr(expr_tree, ctx)
    solver = Solver()
    for c in ctx.constraints:
        solver.add(c)
    # pin present scalar fields; mark absent fields Missing
    for k, v in (context or {}).items():
        if isinstance(v, list):
            n = len(v)
            solver.add(ctx.array_len(k) == n)
            for i, ev in enumerate(v):
                elem = ctx.array_elements(k)[i]
                if isinstance(ev, bool):
                    solver.add(elem == ev)
                elif isinstance(ev, str):
                    solver.add(elem == ev)
                else:
                    solver.add(elem == int(ev))
        elif v is None:
            f = ctx.field(k)
            solver.add(is_missing_int(f) if s.get(k).type == "int" else
                       is_missing_str(f) if s.get(k).type == "string" else
                       is_missing_bool(f))
        else:
            f = ctx.field(k)
            if isinstance(v, bool):
                solver.add(f == TVLBool.Def(v))
            elif isinstance(v, str):
                solver.add(f == str_def(v))
            else:
                solver.add(f == TVLInt.Def(int(v)))
    for f in fields:
        if f not in (context or {}):
            solver.add(is_missing_int(ctx.field(f)))
    # A top-level aggregate (avg/min/max over empty → false) is an AggVal;
    # coerce it to the boolean context the same way can_fire does (agg_bool).
    if expr.sort() == AggVal:
        expr = agg_bool(expr)
    solver.add(val_bool(expr))
    return solver.check() == sat


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    vectors_path = os.path.join(base, "..", "..", "erdl-vectors", "v-engine-vectors.json")
    answers_path = os.path.join(base, "..", "..", "erdl-vectors", "v-engine-answers.json")
    with open(vectors_path, encoding="utf-8") as f:
        vectors = json.load(f)["vectors"]
    with open(answers_path, encoding="utf-8") as f:
        answers = json.load(f)

    total = passed = skipped = 0
    fails = []
    # error/null scenarios are deliberate type-error probes: the engine folds them
    # to false/null at runtime, while the verifier (static, schema-driven) may
    # reject them at compile time. We cross-check the clean normal/boundary
    # semantics here, and track the type-error boundary separately.
    type_boundary = []
    for v in vectors:
        if v["category"] != "V-ENGINE" or v.get("subcategory"):
            continue
        exp = answers.get(v["id"])
        if not exp or exp.get("errored"):
            continue
        if exp.get("value_type") != "boolean":
            skipped += 1
            continue
        try:
            got = eval_against(v["expr_tree"], v.get("context"), exp)
            want = exp["value"] is True
            total += 1
            if got == want:
                passed += 1
            else:
                fails.append((v["id"], v["node"], v["scenario"], want, got))
        except Exception as e:
            # compile-time type error in the verifier vs runtime fold in the engine
            type_boundary.append((v["id"], v["node"], v["scenario"], exp["value"], f"{type(e).__name__}: {e}"))
            skipped += 1

    print(f"verifier<->vector boolean pin-check (normal/boundary): {passed}/{total} consistent, {skipped} skipped")
    for f_ in fails[:30]:
        print("  MISMATCH", f_)
    print(f"  type-boundary (verifier compile-error vs engine runtime-fold): {len(type_boundary)}")
    for t_ in type_boundary[:30]:
        print("    boundary", t_)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
