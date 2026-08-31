# erdl-formal

A **formal verifier** for the ERDL expression kernel — SMT (Z3) static property proofs. Not "we tested it", but "mathematically, no counterexample exists".

> ERDL is the deterministic rule language for enterprise AI agents (a 34-node typed expression tree + E1–E12 evaluation constraints). This repository answers one question: **does this rule, over *all* inputs, ever error, ever fail-open, or ever miss a block it should make?**

## Why

LLMs are probabilistic; rule engines must be deterministic. Hand-written if/else + unit tests only prove the *tested* inputs. Formal verification lifts "determinism" from sampled testing to exhaustive proof — the same value Cedar Analysis delivers inside AWS, and the "always-true" guarantee regulated industries (finance / insurance / government) require from audits.

## Features

- **All 34 nodes encoded**: value / logic / comparison / set / string / existence / quantifier / arithmetic / time / aggregate.
- **Exact E1–E12 semantics**: E2 fixed-point scale=14 + half-even, E8 empty-array folding (anti-vacuous-truth), E11 three-valued logic (leaf collapse), E12 tier folding.
- **Cedar's 6 properties + ERDL-specific**: never-errors / always-allows / always-denies / subsumption / equivalence / disjointness + override-soundness / ring-respect / emergency-shortcut.
- **Independent verifier**: encodes the spec (`erdl-spec-v2.0`) with zero dependency on any ERDL engine — forming a three-way independent cross-check with `erdl` (TS engine) and `erdl-vectors` (frozen vectors).

## Quick start

```python
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies

# G3 classification check: file_cls > op_cls → DENY
schema = Schema()
schema.add(FieldContract(field="file_cls", type="int"))
schema.add(FieldContract(field="op_cls", type="int"))

rule = ["gt", ["field", "file_cls"], ["field", "op_cls"]]

# proves two properties at once:
# 1) reachable — with both fields present, a higher classification fires the block
# 2) fail-closed — a missing operator classification does NOT open a bypass
assert always_denies(rule, schema, premises=["file_cls", "op_cls"], missing_field="op_cls")
```

## Guarantees (Measurements, not endorsements)

Three independent systems agree byte-for-byte:

| Cross-check | Pair | Result |
|---|---|---|
| Fixed-point | `fixed_point.py` ↔ erdl `fixed-point.js` | byte-identical |
| Resolution | `resolution.py` ↔ erdl `Evaluator` | 4 scenarios |
| Arithmetic vectors | ↔ erdl-vectors V-ENGINE | 7/7 |
| Calendar vectors | ↔ erdl-vectors V-ENGINE | 6/6 |
| G3 replay | `tvl.py` ↔ erdl engine | scenario-identical |

## Documentation

- `docs/DELIVERY-REPORT.md` — delivery summary (milestones / 34-node matrix / cross-checks / pitfalls)
- `docs/semantics.md` — denotational semantics
- `docs/tvl-encoding.md` — three-valued logic SMT encoding
- `docs/field-contracts.md` + `docs/schema-assumption.md` — verification schema

## Development

```bash
python -m pip install -e ".[dev]"
pytest                               # 102 passing
python replay/crosscheck-vectors.py  # cross-check against erdl-vectors
```

## License

MIT · © 2026 Shenzhen Miaojing Technology Co., Ltd.
