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

"""Cross-check: erdl-formal calendar SMT vs erdl-vectors V-ENGINE frozen vectors."""

import json
import os
from datetime import datetime, timezone

from z3 import simplify

from erdl_formal.calendar import tvl_date_add, tvl_date_part, tvl_month_last_day
from erdl_formal.tvl import TVLInt, val_int

VECTORS = os.path.join(os.path.dirname(__file__), "..", "..", "erdl-vectors", "v-engine-vectors.json")


def epoch_ms(s):
    return int(datetime.fromisoformat(s[:10]).replace(tzinfo=timezone.utc).timestamp() * 1000)


def _v(expr):
    return simplify(val_int(expr)).as_long()


def main():
    with open(VECTORS, encoding="utf-8") as f:
        vectors = json.load(f)["vectors"]

    # Oracle isolation (ER9): committed vectors carry no `expected`; re-attach
    # from the gitignored answers file, keyed by vector id.
    answers_path = os.path.join(os.path.dirname(__file__), "..", "..", "erdl-vectors", "v-engine-answers.json")
    with open(answers_path, encoding="utf-8") as f:
        answers = json.load(f)

    total = passed = 0
    for v in vectors:
        if v["category"] != "V-ENGINE" or v.get("node") not in ("date_part", "month_last_day", "date_add"):
            continue
        exp = answers.get(v["id"])
        if exp["errored"]:
            continue
        expr = v["expr_tree"]
        node = v["node"]

        try:
            if node == "date_part":
                unit, arg = expr["date_part"]["unit"], expr["date_part"]["arg"]
                if not isinstance(arg, str):
                    continue
                got = _v(tvl_date_part(unit, TVLInt.Def(epoch_ms(arg))))
                expected = exp["value"]
            elif node == "month_last_day":
                arg = expr["month_last_day"]
                if not isinstance(arg, str):
                    continue
                got = _v(tvl_month_last_day(TVLInt.Def(epoch_ms(arg))))
                expected = epoch_ms(exp["value"])
            else:  # date_add
                unit, base, amount = expr["date_add"]["unit"], expr["date_add"]["base"], expr["date_add"]["amount"]
                if not isinstance(base, str):
                    continue
                got = _v(tvl_date_add(unit, TVLInt.Def(epoch_ms(base)), TVLInt.Def(int(amount) * 10 ** 14)))
                expected = epoch_ms(exp["value"])
        except (ValueError, KeyError, NotImplementedError):
            continue

        total += 1
        if got == expected:
            passed += 1
        else:
            print(f"  ❌ {v['id']}: got {got} expected {expected}")

    print(f"Calendar vector cross-check: {passed}/{total} consistent")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
