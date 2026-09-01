# Denotational Semantics · 34-node kernel

> Basis: [erdl-spec-v2.0](https://github.com/OpenOBA/erdl-landing/blob/main/spec/erdl-spec-v2.0.md) §10 · this repo's `tvl.py` / `quantifiers.py` / `fixed_point.py`

This document defines the **denotational semantics** of the 34 nodes of the ERDL expression kernel — the "input → output" mathematical function of each node. It is the encoding basis of the symbolic compiler (ERDL → SMT-LIB) and the judgment baseline for counterexample replay.

## 1. Value domain

```
τ ∈ { Int, Rational, String, Bool, Array<τ>, Set<τ> }
V  = TVL(τ) = Def(value: τ) | Missing          # E11 undefined sentinel
E  = EvalError                                   # E12 evaluation error (distinct from Missing)
```

- `Rational` = high-precision bounded rational (128-bit numerator/denominator); intermediate computation is exact, only output nodes round to scale=14 + half-even (E2).
- `Missing` = field absent / undefined; `EvalError` = evaluation error (division by zero, type-mismatched arithmetic).

## 2. Node denotation (10 groups)

Let `ctx : Context` (field mapping), `⟦e⟧(ctx) : V`.

### Values (3)

| Node | Denotation |
|---|---|
| `field(f)` | `Def(ctx[f])` if `f ∈ ctx`; otherwise `Missing` |
| `var(v)` | `Def(ctx.$[v])` (`$` / `$.path`); `Missing` if absent |
| `literal(c)` | `Def(c)` (fixed-point decimal string → Rational / NFC string / Bool) |

### Logic (3, two-valued)

| Node | Denotation |
|---|---|
| `and(a,b)` | `Def(val(a) ∧ val(b))` (operands already collapsed to Def(Bool), two-valued) |
| `or(a,b)` | `Def(val(a) ∨ val(b))` |
| `not(a)` | `Def(¬val(a))` |

> **E11 leaf collapse**: logical operators are **two-valued** — their operands are already-collapsed booleans (comparison nodes collapse Missing to false); undefined does not propagate to the boolean layer.

### Comparison (6, E11 collapse)

| Node | Denotation |
|---|---|
| `eq(a,b)` `ne(a,b)` | `Def(false)` if either operand is Missing; otherwise `Def(val(a) = / ≠ val(b))` |
| `gt(a,b)` `gte` `lt` `lte` | `Def(false)` if either is Missing; otherwise `Def(val(a) > / ≥ / < / ≤ val(b))` (numeric order / string Unicode code-point order) |

### Set (1)

`in(x, S)` = `Def(false)` if `x` is Missing; otherwise `Def(val(x) ∈ S)`.

### String (4)

`contains(s,t)` / `starts_with(s,t)` / `ends_with(s,t)` = prefix/suffix/contains predicates (Missing → `Def(false)`); `match(s,re)` = safe regex (case-sensitive, ReDoS-protected, step count ≤10000).

### Existence / dimension (3)

| Node | Denotation |
|---|---|
| `exists(x)` | `Def(¬is_missing(x))` (the only operator that senses field presence) |
| `length(x)` | `Def(code point count)` (Unicode code points, not UTF-16 length) |
| `between(x,a,b)` | `Def(a ≤ val(x) ≤ b)` (closed interval, numeric only; Missing → false) |

### Quantifier (3, E8 empty-array collapse)

`all/any/none(array, pred)`: empty array → `Def(false)` (E8 anti-vacuous-truth); non-empty → `Def(∧/∨/¬∨_{i} pred(array[i]))`.

### Arithmetic (5, E2 fixed-point rational)

`add/sub/mul/div`: exact rational arithmetic (128-bit); `div` by zero → `EvalError`. `round`: half-even rounding. **No rounding in intermediates; only output nodes scale=14 + half-even**.

### Time (5)

`epoch_ms` / `days_between` = integer timestamp / `floor(diff/86400000)` (UTC); `date_add` / `date_part` / `month_last_day` = Gregorian calendar (UTC, civil algorithm).

### Aggregate (1)

`aggregate(fn, over)`: `count/sum` over an empty array → `Some(0)`; `avg/min/max` over an empty array → `None` (folds to false in condition context). Non-array `over` → `EvalError`.

## 3. E constraints (semantic layer)

| Constraint | Semantics |
|---|---|
| E1 | Pure functions (no side effects / no clock); within/rate state lives outside the tree, in GuardStateManager |
| E2 | Fixed-point scale=14 + half-even; 128-bit rational intermediates |
| E3/E12 | EvalError → tier≤2 fail-close / tier 3–5 fold to false |
| E4 | Resource limits (Grade A: tree depth ≤6 / nodes ≤64 / arrays ≤10000) |
| E5 | Type checking at load time |
| E8 | Quantifier over empty array is always false (all/none are deliberate safe deviations) |
| E10 | String NFC normalization |
| E11 | Undefined sentinel (leaf collapse) |

## 4. Decision: leaf collapse (not Kleene)

This semantics uses **leaf collapse** (E11 "field-absent uniformly returns false"), not Kleene propagation. See `docs/tvl-encoding.md` §5 for the rationale.
