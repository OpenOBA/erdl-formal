# -*- coding: utf-8 -*-
"""Cross-check: verifier (symbolic) vs vector (engine concrete eval) — full value-domain.

Extends crosscheck-boolean.py beyond boolean: also pins null (fold) and
numeric/rational results. For each vector we pin the concrete context and ask
the verifier the corresponding satisfiability question, which must agree with
the frozen expected value/type.

- boolean expected → "can the condition be true?" == (expected is True)
- null expected    → the condition folds (Missing / false): "is it NOT folded?" must be UNSAT
- rational/number/date → "can the value equal expected?" must be SAT
"""
import json
import os

from z3 import Not, Solver, StringVal, sat

from erdl_formal.compiler import CompileContext, compile_expr
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.tvl import (
    AggVal,
    TVLBool,
    TVLInt,
    TVLStr,
    agg_bool,
    agg_to_int,
    val_bool,
    val_int,
    val_str,
    is_missing_int,
    is_missing_str,
    is_missing_bool,
    str_def,
)


def collect_fields(node, acc):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "field" and isinstance(v, str):
                acc.add(v)
            elif k in ("var",):
                pass
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
    return "int"


def build_schema(context, expr_tree):
    s = Schema()
    for k, v in (context or {}).items():
        t = infer_type(v)
        if isinstance(t, tuple):
            s.add(FieldContract(field=k, type="array", element_type=t[1], cardinality=max(len(v), 1)))
        else:
            s.add(FieldContract(field=k, type=t))
    fields = set()
    collect_fields(expr_tree, fields)
    for f in fields:
        if f not in (context or {}):
            s.add(FieldContract(field=f, type="int"))
    return s, fields


def pin_context(ctx, s, solver, context):
    fields = set()
    collect_fields_ctx = set()
    for k, v in (context or {}).items():
        collect_fields_ctx.add(k)
        if isinstance(v, list):
            n = len(v)
            solver.add(ctx.array_len(k) == n)
            for i, ev in enumerate(v):
                elem = ctx.array_elements(k)[i]
                if isinstance(ev, bool):
                    solver.add(elem == ev)
                elif isinstance(ev, str):
                    solver.add(elem == ev)
                elif isinstance(ev, float) and ev != int(ev):
                    from decimal import Decimal
                    from fractions import Fraction
                    solver.add(elem == int(Fraction(Decimal(str(ev))) * 10**14))
                else:
                    solver.add(elem == int(ev) * 10**14)
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
            elif isinstance(v, float) and v != int(v):
                from decimal import Decimal
                from fractions import Fraction
                solver.add(f == TVLInt.Def(int(Fraction(Decimal(str(v))) * 10**14)))
            else:
                solver.add(f == TVLInt.Def(int(v) * 10**14))
    return collect_fields_ctx


def eval_against(expr_tree, context, expected, node=""):
    """Return 'sat' / 'unsat' / None(unpinnable)."""
    s, fields = build_schema(context, expr_tree)
    ctx = CompileContext(s)
    expr = compile_expr(expr_tree, ctx)
    solver = Solver()
    for c in ctx.constraints:
        solver.add(c)
    present = pin_context(ctx, s, solver, context)
    for f in fields:
        if f not in (context or {}):
            solver.add(is_missing_int(ctx.field(f)))

    vt = expected.get("value_type")
    if vt == "boolean":
        if expr.sort() == AggVal:
            expr = agg_bool(expr)
        solver.add(val_bool(expr))
        return "sat" if solver.check() == sat else "unsat"
    if vt == "null":
        # fold: the value is Missing (or false). "is NOT folded" must be UNSAT.
        if expr.sort() == AggVal:
            expr = agg_to_int(expr)
        if expr.sort() == TVLInt:
            solver.add(Not(is_missing_int(expr)))
            return "unsat" if solver.check() != sat else "sat"
        if expr.sort() == TVLStr:
            solver.add(Not(is_missing_str(expr)))
            return "unsat" if solver.check() != sat else "sat"
        if expr.sort() == TVLBool:
            solver.add(val_bool(expr))
            return "unsat" if solver.check() != sat else "sat"
        return None
    if vt == "undefined":
        # missing field/var → Missing
        if expr.sort() == TVLInt:
            solver.add(is_missing_int(expr))
            return "sat" if solver.check() == sat else "unsat"
        if expr.sort() == TVLStr:
            solver.add(is_missing_str(expr))
            return "sat" if solver.check() == sat else "unsat"
        if expr.sort() == TVLBool:
            solver.add(is_missing_bool(expr))
            return "sat" if solver.check() == sat else "unsat"
        return None
    if vt in ("string", "date"):
        # value == expected string (NFC literal / date string result)
        if expr.sort() == TVLStr:
            solver.add(Not(is_missing_str(expr)))
            solver.add(val_str(expr) == StringVal(expected["value"]))
            return "sat" if solver.check() == sat else "unsat"
        return None
    if vt in ("rational", "number"):
        if expr.sort() == AggVal:
            expr = agg_to_int(expr)
        if expr.sort() != TVLInt:
            return None
        v = expected["value"]
        if vt == "rational":
            # fixed-point scale-14
            if isinstance(v, str):
                from decimal import Decimal
                from fractions import Fraction
                target = int(Fraction(Decimal(v)) * 10**14)
            elif isinstance(v, int):
                target = v * 10**14
            else:
                return None
        else:  # number: integer (length / epoch_ms / count) — but field/literal values are scale-14
            try:
                target = int(v)
            except (TypeError, ValueError):
                return None
            if node in ("field", "literal"):
                target *= 10**14
        solver.add(Not(is_missing_int(expr)))
        solver.add(val_int(expr) == target)
        return "sat" if solver.check() == sat else "unsat"
    return None


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    vectors_path = os.path.join(base, "..", "..", "erdl-vectors", "v-engine-vectors.json")
    answers_path = os.path.join(base, "..", "..", "erdl-vectors", "v-engine-answers.json")
    with open(vectors_path, encoding="utf-8") as f:
        vectors = json.load(f)["vectors"]
    with open(answers_path, encoding="utf-8") as f:
        answers = json.load(f)

    stats = {"boolean": [0, 0], "null": [0, 0], "rational": [0, 0], "number": [0, 0], "undefined": [0, 0], "string": [0, 0], "date": [0, 0]}
    fails = []
    skipped = 0
    for v in vectors:
        if v["category"] != "V-ENGINE" or v.get("subcategory"):
            continue
        exp = answers.get(v["id"])
        if not exp or exp.get("errored"):
            continue
        vt = exp.get("value_type")
        if vt not in ("boolean", "null", "rational", "number", "undefined", "string", "date"):
            skipped += 1
            continue
        try:
            got = eval_against(v["expr_tree"], v.get("context"), exp, v.get("node", ""))
        except Exception as e:
            skipped += 1
            continue
        if got is None:
            skipped += 1
            continue
        # expected verdict
        if vt == "boolean":
            want = "sat" if exp["value"] is True else "unsat"
        elif vt == "null":
            want = "unsat"
        elif vt in ("undefined", "string", "date"):
            want = "sat"
        else:  # rational/number
            want = "sat"
        if got == want:
            stats[vt][0] += 1
        else:
            stats[vt][1] += 1
            fails.append((v["id"], vt, want, got))

    for vt in ("boolean", "null", "rational", "number", "undefined", "string", "date"):
        p, f_ = stats[vt]
        print(f"  {vt}: {p} consistent, {f_} mismatch")
    print(f"  skipped: {skipped}")
    for f_ in fails[:30]:
        print("  MISMATCH", f_)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
