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
