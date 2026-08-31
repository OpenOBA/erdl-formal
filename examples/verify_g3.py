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

"""Runnable example: prove the G3 classification rule is reachable and fail-closed.

    when: file_cls > op_cls  ->  DENY

The `always_denies` property proves two things at once:
1. reachable  — with both fields present, a higher classification fires the block;
2. fail-closed — a missing operator classification does NOT open a bypass.

Run:  python examples/verify_g3.py
"""
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies


def main():
    schema = Schema()
    schema.add(FieldContract(field="file_cls", type="int"))
    schema.add(FieldContract(field="op_cls", type="int"))

    rule = ["gt", ["field", "file_cls"], ["field", "op_cls"]]

    holds = always_denies(rule, schema, premises=["file_cls", "op_cls"], missing_field="op_cls")
    print(f"G3 reachable + fail-closed: {holds}")
    return 0 if holds else 1


if __name__ == "__main__":
    raise SystemExit(main())
