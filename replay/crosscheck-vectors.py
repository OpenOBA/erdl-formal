"""Cross-check: erdl-formal reference semantics vs erdl-vectors V-ENGINE frozen vectors.

Validates `fixed_point.py` (scale=14 + half-even + exact rational) against the
frozen V-ENGINE arithmetic vectors — the "formal model == frozen runtime vector"
convergence.

Note: JSON numbers are parsed with `parse_float=str` so `0.1` stays the exact
decimal "0.1" (1/10), not an IEEE-754 float.
"""

import json
import os

from erdl_formal.fixed_point import (
    add,
    div,
    mul,
    parse,
    serialize,
    sub,
    to_scale14_half_even,
)

VECTORS = os.path.join(os.path.dirname(__file__), "..", "..", "erdl-vectors", "v-engine-vectors.json")

_OPS = {"add": add, "sub": sub, "mul": mul, "div": div}


def eval_expr(expr):
    """Evaluate a literal-only arithmetic expr (no field/context)."""
    if isinstance(expr, dict):
        for op, fn in _OPS.items():
            if op in expr:
                args = [eval_expr(a) for a in expr[op]]
                if any(a is None for a in args):
                    return None  # missing/type-mismatch (not covered here)
                try:
                    return fn(*args)
                except ZeroDivisionError:
                    return None
    if isinstance(expr, str):
        return parse(expr) if _is_decimal(expr) else None
    if isinstance(expr, (int, float)):
        return parse(str(expr))
    return None


def _is_decimal(s):
    try:
        parse(s)
        return True
    except ValueError:
        return False


def main():
    with open(VECTORS, encoding="utf-8") as f:
        vectors = json.load(f, parse_float=str)["vectors"]

    total = passed = 0
    for v in vectors:
        if v["category"] != "V-ENGINE" or v.get("node") not in ("add", "sub", "mul", "div"):
            continue
        if v["scenario"] not in ("normal", "boundary"):
            continue
        exp = v["expected"]
        if exp["errored"] or exp["value_type"] != "rational":
            continue  # only clean rational results (not type_mismatch/div-by-zero)

        got = eval_expr(v["expr_tree"])
        if got is None:
            continue
        got_s = serialize(to_scale14_half_even(got))
        total += 1
        if got_s == exp["value"]:
            passed += 1
        else:
            print(f"  ❌ {v['id']}: got {got_s} expected {exp['value']}")

    print(f"算术向量交叉验证: {passed}/{total} 一致")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
