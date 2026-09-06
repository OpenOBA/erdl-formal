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

    # Oracle isolation (ER9): committed vectors carry no `expected`; re-attach
    # from the gitignored answers file, keyed by vector id.
    answers_path = os.path.join(os.path.dirname(__file__), "..", "..", "erdl-vectors", "v-engine-answers.json")
    with open(answers_path, encoding="utf-8") as f:
        answers = json.load(f)

    total = passed = 0
    for v in vectors:
        if v["category"] != "V-ENGINE" or v.get("node") not in ("add", "sub", "mul", "div"):
            continue
        if v["scenario"] not in ("normal", "boundary"):
            continue
        exp = answers.get(v["id"])
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

    print(f"Arithmetic vector cross-check: {passed}/{total} consistent")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
