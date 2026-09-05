# erdl-formal

[![Version](https://img.shields.io/badge/version-v0.1.17-blue)](https://github.com/OpenOBA/erdl-formal/releases) [![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

A formal verifier for the ERDL expression kernel — proving rule safety over all inputs with Z3.

There are two kinds of determinism: the determinism tests cover, and the determinism mathematics proves. erdl-formal provides the latter.

>"erdl-formal formally verifies ERDL v2.1's expression kernel and evaluation semantics (§5, §7, Appendix A), covering all 34 nodes and the E1–E12 constraints. The spec's other layers (document structure, gloss rendering, integration modes) are guaranteed by test vectors and engineering verification."

## Why now: LLMs have brute force. They don't have direction.

LLMs are probabilistic: same input, different answers. Hand enterprise decisions to a probability distribution, and the auditors will eventually ask — *"on what basis was this decision made?"*

The industry is converging on an answer: **let the LLM understand; let a deterministic rule engine decide.** But a rule engine's "determinism" is usually underwritten by unit tests — and tests only prove the inputs you happened to write.

In regulated industries — finance, insurance, government — the audit question is singular:

> **Does this rule hold for every input?**

Sampled tests can't answer that. Only a proof can. Cedar Analysis proved this approach works inside AWS (Lean formalization + SMT symbolic analysis). erdl-formal does the same for the ERDL expression kernel — lifting determinism from **sampled testing** to **exhaustive proof**.

- **Cedar Analysis**: used inside AWS, Lean + SMT, not open to the public, serving only AWS's own policy language.
- **OPA/Rego**: no formal semantics — "the implementation is the spec."
- **erdl-formal**: open source, 34-node full coverage, ERDL-specific semantics (money, time, decision objects, bidirectional gloss).

## One proof in 30 seconds

The G3 classification gate: file classification > operator classification → DENY. We want to prove the rule is both **reachable** and **fail-closed** (a missing field never opens a bypass):

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
# 2) fail-closed — a missing field never opens a bypass. This depends on the
#    document's unmatched fallback (default_decision): under a DENY fallback the
#    silenced guard still denies; under the ALLOW fallback (resolution default)
#    the missing field falls through to ALLOW — the rule fails open.
assert always_denies(
    rule, schema,
    premises=["file_cls", "op_cls"],
    missing_field="op_cls",
    default_decision="DENY",
)
assert not always_denies(
    rule, schema,
    premises=["file_cls", "op_cls"],
    missing_field="op_cls",
    default_decision="ALLOW",
)
```

No test cases. No sampling. Z3 searches the space of **all integers** for an input violating the property: if one exists, you get a **concrete, replayable counterexample** (re-checkable against the real engine); if not, UNSAT — the property holds for every input. QED.

## What you can prove

| Property | Meaning | Origin |
|---|---|---|
| always-denies | fires whenever its guard can — whether a missing field opens a bypass is resolved against `default_decision` | Cedar + E11 |
| subsumption / equivalence / disjointness | implication / equivalence / mutual exclusion | Cedar |
| override-soundness | overrides go DENY→ALLOW only (never toward a less-safe state) | **ERDL-specific** |
| ring-respect | a higher-ring DENY overrides a lower-ring ALLOW (ring order honored in the DENY direction) | **ERDL-specific** |
| emergency-shortcut | EMERGENCY_HALT short-circuits the moment it fires | **ERDL-specific** |
| catch-all-neutral | a catch-all (empty-condition) rule never rewrites an established decision, in either direction (EMERGENCY_HALT excepted) | **ERDL-specific** |

Expression-layer properties (`always_denies` / `subsumes` / …) are proven by writing the negation as constraints and checking UNSAT; the ERDL-specific resolution properties (`override_soundness` / `ring_respect` / `emergency_shortcut` / `catch_all_neutral`) are encoded in `resolution_smt.py`, which compiles `resolve()`'s ring / override / priority ordering into Z3 constraints and proves them UNSAT over **all rule-sets** — not sampling, a full proof. Any SAT counterexample is a concrete rule-set replayed against the real engine — proof plus differential testing, double insurance.

## 34/34 nodes, E1–E12 semantics

- **All 34 nodes have SMT encodings**: value / logic / comparison / set / string / existence / quantifier / arithmetic / time / aggregate (comparison and existence dispatch by field type: int / string / bool; `epoch_ms` supports date-only and ISO 8601 datetime with time / offset).
- The hard semantics aren't "roughly right" — they are **bit-exact**:
  - **E2** fixed-point decimals: scale=14 + half-even — money is not allowed `0.1 + 0.2` drift;
  - **E8** quantifier empty-array folding: anti-vacuous-truth — `all([])` is false, not true;
  - **E11** three-valued logic: missing fields collapse to false at the leaves (not Kleene); whether a missing field fails open is resolved by the document fallback (see `always_denies`'s `default_decision`);
  - **E10** NFC normalization; **E12** evaluation errors collapse to `Missing` (tier≤2 fail-close is runtime behavior, not modeled in the kernel).

## Independent verifier: three-way, byte-for-byte

A verifier is only credible if it **never peeks at the examinee's answers**. erdl-formal encodes the spec alone ([`erdl-language-spec`](https://github.com/OpenOBA/erdl-landing/blob/main/erdl-spec.en.md)), with zero dependency on any ERDL engine implementation, forming a three-way independent cross-check with [`erdl`](https://www.npmjs.com/package/@openoba/erdl) (the TS engine) and [`erdl-vectors`](https://github.com/OpenOBA/erdl-vectors) (frozen vectors):

| Cross-check | Pair | Result |
|---|---|---|
| Fixed-point | `fixed_point.py` ↔ erdl `fixed-point.js` | byte-identical |
| Resolution | `resolution.py` ↔ `resolution_smt.py` (Z3 model; semantics aligned to erdl-landing `evaluator.ts`) | exhaustive + random differential (`test_resolution_smt.py`) |
| Arithmetic vectors | ↔ erdl-vectors V-ENGINE | 7/7 |
| Calendar vectors | ↔ erdl-vectors V-ENGINE | 6/6 |
| G3 counterexample replay | `tvl.py` ↔ erdl engine | scenario-identical |

**Measurements, not endorsements.** Three independently built systems agreeing byte-for-byte means the spec is precise enough to sustain exact independent reimplementation.

## How it differs from Cedar / OPA

| Dimension | Cedar Analysis | OPA / Rego | **erdl-formal** |
|---|---|---|---|
| Formal verification | ✅ Lean + SMT (the field's benchmark, closed) | ❌ no formal semantics — the implementation *is* the spec | ✅ SMT (Z3), open source |
| Fixed-point (money) | decimals only via extension plugin | float64 loses precision | ✅ scale=14 + half-even |
| Time / calendar | — | — | ✅ UTC calendar (days_between / date_add / date_part / month-end) |
| Aggregation | — | — | ✅ aggregate (count / sum / avg / min / max) |
| Quantifiers | — | — | ✅ all / any / none (E8 empty-array fold) |
| Decision object | policy IDs only | unsigned logs | ✅ rich DO + hash chain |
| Natural language | one-way (NL→policy) | one-way | ✅ deterministic gloss, anchored round-trip (two-way) |

The difference is not "more formal" — Cedar's stack is the benchmark, and we say so. The difference is **what gets formalized**: ERDL is an enterprise rule kernel built for money, time, aggregation, quantifiers, decision objects, and two-way natural language — none of which exist in the Cedar / OPA world (the `—` rows above).

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
python -m build        # produces dist/erdl_formal-<version>-py3-none-any.whl + .tar.gz
```

## Quick start

```bash
pytest                               # all passing
python examples/verify_g3.py         # prove the G3 classification rule (reachable + fail-closed)
python replay/crosscheck-vectors.py  # cross-check against erdl-vectors frozen vectors
```

## Documentation

- `docs/semantics.en.md` — denotational semantics for all 34 nodes
- `docs/tvl-encoding.en.md` — three-valued logic SMT encoding
- `docs/field-contracts.en.md` — verification schema contracts
- `docs/DEVELOPER-GUIDE.en.md` — developer guide (architecture / adding nodes / properties / API / build & publish)

## Acknowledgments

The resolution-layer properties (`override_soundness` / `ring_respect` /
`emergency_shortcut` / `catch_all_neutral`) were shaped in part by external
review. In particular, **ANP2 Network** ([dev.to/anp2network](https://dev.to/anp2network))
provided three rounds of precise, reproducible review of the resolution
semantics, each identifying a concrete boundary in the kernel:

- **string/bool `eq`/`ne`/`exists`** (v0.1.2) — the kernel only compiled int
  equality/existence, raising `Sort mismatch` on string equality;
- **`always_denies` fail-closure direction** (v0.1.2) — the property proved
  silence rather than fail-closure, backwards under an ALLOW fallback;
- **the catch-all relax-direction gap** (v0.1.17) — a catch-all (empty-
  condition) ALLOW could rewrite an explicit DENY across rings, and the
  relax direction had no property watching it.

Each finding moved from a spec/engine/property gap to a fix, a test, and
a proof. The project is sharper for it.

## Contributing & security

- `CONTRIBUTING.md` — contribution process (issue-first, review)
- `SECURITY.md` — report vulnerabilities privately, no public issue
- `CHANGELOG.md` — changelog (Keep a Changelog)
- `CODE_OF_CONDUCT.md` / `style_guide.md`

## License

Apache-2.0 · © 2026 深圳市秒镜科技有限公司 (Shenzhen Miaojing Technology Co., Ltd.)
