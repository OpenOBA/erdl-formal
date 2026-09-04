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

The `always_denies` property checks two things:
1. reachable  — with both fields present, a higher classification fires the block;
2. fail-closed — a missing operator classification does NOT open a bypass.

Whether a missing `op_cls` opens a bypass depends on the document's unmatched
fallback (`default_decision`): under a DENY fallback it stays closed; under the
ALLOW fallback (resolution default) the silenced guard falls through to ALLOW
and the rule fails open.

Run:  python examples/verify_g3.py
"""
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies


def main():
    schema = Schema()
    schema.add(FieldContract(field="file_cls", type="int"))
    schema.add(FieldContract(field="op_cls", type="int"))

    rule = ["gt", ["field", "file_cls"], ["field", "op_cls"]]

    closed = always_denies(
        rule, schema,
        premises=["file_cls", "op_cls"],
        missing_field="op_cls",
        default_decision="DENY",
    )
    open_ = always_denies(
        rule, schema,
        premises=["file_cls", "op_cls"],
        missing_field="op_cls",
        default_decision="ALLOW",
    )
    print(f"G3 reachable + fail-closed (DENY fallback): {closed}")
    print(f"G3 fails open (ALLOW fallback):             {open_}")
    return 0 if (closed and not open_) else 1


if __name__ == "__main__":
    raise SystemExit(main())
