# erdl-formal

There are two kinds of determinism: the determinism tests cover, and the determinism mathematics proves. erdl-formal provides the latter.

> ERDL is the deterministic rule language for enterprise AI agents (a 34-node typed expression tree + E1–E12 evaluation constraints). This repo answers one question: **over *all* inputs, does this rule ever error, ever fail open, or ever miss a block it should make?**

## Why now: LLMs have brute force. They don't have direction.

LLMs are probabilistic: same input, different answers. Hand enterprise decisions to a probability distribution, and the auditors will eventually ask — *"on what basis was this decision made?"*

The industry is converging on an answer: **let the LLM understand; let a deterministic rule engine decide.** But a rule engine's "determinism" is usually underwritten by unit tests — and tests only prove the inputs you happened to write.

In regulated industries — finance, insurance, government — the audit question is singular:

> **Does this rule hold for every input?**

Sampled tests can't answer that. Only a proof can. Cedar Analysis proved this approach works inside AWS (Lean formalization + SMT symbolic analysis). erdl-formal does the same for the ERDL expression kernel — lifting determinism from **sampled testing** to **exhaustive proof**.

**Same road as Cedar Analysis (formal policy analysis), different battlefield: we prove an enterprise rule kernel built for money, time, and decision objects.**

## One proof in 30 seconds

The G3 classification gate: file classification > operator classification → DENY. We want to prove the rule is both **reachable** and **fail-closed**:

```python
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies

schema = Schema()
schema.add(FieldContract(field="file_cls", type="int"))
schema.add(FieldContract(field="op_cls", type="int"))

# when: file_cls > op_cls  →  DENY
rule = ["gt", ["field", "file_cls"], ["field", "op_cls"]]

# One assertion, two properties at once:
# 1) reachable — with both fields present, a higher classification fires the block
# 2) fail-closed — with op_cls missing, the comparison collapses to false (E11),
#    and no permissive bypass can ever open
assert always_denies(rule, schema, premises=["file_cls", "op_cls"], missing_field="op_cls")
```

No test cases. No sampling. Z3 searches the space of **all integers** for an input violating the property: if one exists, you get a **concrete, replayable counterexample** (re-checkable against the real engine); if not, UNSAT — the property holds for every input. QED.

## What you can prove

| Property | Meaning | Origin |
|---|---|---|
| never-errors | evaluation never raises an EvalError | Cedar |
| always-denies | fires whenever its guard can — including fail-closed: a missing field never opens a bypass | Cedar + E11 |
| always-allows / subsumption / equivalence / disjointness | permissive / implication / equivalence / mutual exclusion | Cedar |
| override-soundness | overrides go DENY→ALLOW only (never toward a less-safe state) | **ERDL-specific** |
| ring-respect | without overrides, ring order is honored in the DENY direction | **ERDL-specific** |
| emergency-shortcut | EMERGENCY_HALT short-circuits the moment it fires | **ERDL-specific** |

Every property can synthesize a concrete counterexample, and every counterexample can be replayed against the real engine — proof plus differential testing, double insurance.

## 34/34 nodes, exact E1–E12 semantics

- **All 34 nodes have SMT encodings**: value / logic / comparison / set / string / existence / quantifier / arithmetic / time / aggregate.
- The hard semantics aren't "roughly right" — they are **bit-exact**:
  - **E2** fixed-point decimals: scale=14 + half-even — money is not allowed `0.1 + 0.2` drift;
  - **E8** quantifier empty-array folding: anti-vacuous-truth — `all([])` is false, not true;
  - **E11** three-valued logic: missing fields collapse to false at the leaves (not Kleene — no fail-open);
  - **E12** tier folding, **E10** NFC normalization.

## Independent verifier: three-way, byte-for-byte

A verifier is only credible if it **never peeks at the examinee's answers**. erdl-formal encodes the spec alone ([`erdl-spec-v2.0`](https://github.com/OpenOBA/erdl-landing/blob/main/spec/erdl-spec-v2.0.md)), with zero dependency on any ERDL engine implementation, forming a three-way independent cross-check with `erdl` (the TS engine) and `erdl-vectors` (frozen vectors):

| Cross-check | Pair | Result |
|---|---|---|
| Fixed-point | `fixed_point.py` ↔ erdl `fixed-point.js` | byte-identical |
| Resolution | `resolution.py` ↔ erdl `Evaluator` | 4 scenarios |
| Arithmetic vectors | ↔ erdl-vectors V-ENGINE | 7/7 |
| Calendar vectors | ↔ erdl-vectors V-ENGINE | 6/6 |
| G3 counterexample replay | `tvl.py` ↔ erdl engine | scenario-identical |

**Measurements, not endorsements.** Three independently built systems agreeing byte-for-byte means the spec is precise enough to sustain exact independent reimplementation.

## How it differs from Cedar / OPA

| | Cedar Analysis | OPA / Rego | **erdl-formal** |
|---|---|---|---|
| Formal verification | ✅ Lean + SMT (the field's benchmark) | ❌ no formal semantics — the implementation *is* the spec | ✅ SMT (Z3) |
| Money | decimals only via extension plugin | float64 loses precision | ✅ scale=14 fixed-point + half-even |
| Decision object | policy IDs only | unsigned logs | ✅ rich Decision Object (DO) |
| Natural language | one-way (NL→policy) | one-way | ✅ deterministic gloss, anchored round-trip (two-way) |

The difference is not "more formal" — Cedar's stack is the benchmark, and we say so. The difference is **what gets formalized**: ERDL is an enterprise rule kernel built for money, time, aggregation, quantifiers, decision objects, and two-way natural language — none of which exist in the Cedar / OPA world.

## Architecture

```
ERDL rule (S-expression)
   │
   ▼  compiler.py (symbolic compiler: schema-driven field typing + quantifier index unfolding)
Z3 TVL expressions (TVL(τ) = Def | Missing, leaf collapse)
   │
   ▼  properties.py (property checks) / resolution.py (resolution reference model)
sat / unsat + counterexample (replayed against the real engine)
```

## Installation

**Users** (from PyPI, one command):

```bash
pip install erdl-formal
```

**Developers** (from source, editable install, changes take effect immediately):

```bash
git clone https://github.com/OpenOBA/erdl-formal.git
cd erdl-formal
python -m pip install -e ".[dev]"   # Python ≥3.11 (developed on 3.14), z3-solver ≥4.13 (verified on 5.1.0)
```

**Build a distribution** (wheel + sdist, for release / offline distribution):

```bash
python -m pip install build
python -m build        # produces dist/erdl_formal-0.1.1-py3-none-any.whl + .tar.gz
```

## Quick start

```bash
pytest                               # 130 passing
python examples/verify_g3.py         # prove the G3 classification rule (reachable + fail-closed)
python replay/crosscheck-vectors.py  # cross-check against erdl-vectors frozen vectors
```

## Documentation

- `docs/semantics.en.md` — denotational semantics for all 34 nodes
- `docs/tvl-encoding.en.md` — three-valued logic SMT encoding
- `docs/field-contracts.en.md` — verification schema contracts
- `docs/DEVELOPER-GUIDE.en.md` — developer guide (architecture / adding nodes / properties / API / build & publish)

## Contributing & security

- `CONTRIBUTING.md` — contribution process (issue-first, review)
- `SECURITY.md` — report vulnerabilities privately, no public issue
- `CHANGELOG.md` — changelog (Keep a Changelog)
- `CODE_OF_CONDUCT.md` / `style_guide.md`

## License

Apache-2.0 · © 2026 深圳市秒镜科技有限公司 (Shenzhen Miaojing Technology Co., Ltd.)
