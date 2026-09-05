# Three-valued logic SMT encoding spec

> Basis: [erdl-language-spec](https://github.com/OpenOBA/erdl-landing/blob/main/erdl-spec.en.md) §7.2 E11/E12

## 1. Encoding carrier

```
TVL(τ) = Def(value: τ) | Missing
```

- `Def(v)` — has a value (is_defined = true)
- `Missing` — no value (field absent / undefined sentinel)

Z3 ADT implementation: `TVLInt = Def(int) | Missing`, `TVLBool = Def(bool) | Missing`.

## 2. E11 leaf collapse (core semantics)

**Comparison nodes** (eq/ne/gt/gte/lt/lte): any operand `Missing` → `Def(false)`.

**Arithmetic nodes** (add/sub/mul/div/round): any operand `Missing` → `Missing` (SMT approximation of `EvalError`; condition context folds `false`).

**Boolean operators** (and/or/not): **two-valued logic** — operands are already-collapsed `Def(true/false)`; undefined does not propagate to the boolean layer. Hence `not(field-absent == x)` = `not(false)` = `true`.

## 3. E12 tier fold (runtime; not modeled in the kernel)

`EvalError` → tier≤2 / Guard defaults fail-close (DENY); tier 3–5 folds to `false`. **This SMT kernel has no EvalError constructor** — `EvalError` such as division by zero folds to `Missing` (equivalent to tier 3–5 fold-false); tier≤2 fail-close is runtime behavior, not modeled in the kernel.

## 4. `not`'s exists guard (§11.4)

The core Expression tree's `not` does not auto-add an exists guard. Writing `not(field==x)` in an **ALLOW rule** when the field is absent makes `not(false)=true` **fail-open**; you MUST manually write `exists(field) AND not(field==x)` to guarantee fail-closed. The Simple projection's derived `not_*` operators are already covered by §11.4's compile-layer exists guard.

## 5. Decision: leaf collapse (not Kleene)

This encoding uses **leaf collapse** (spec E11 "field-absent uniformly returns false"), **not Kleene propagation**. Rationale ([erdl-language-spec](https://github.com/OpenOBA/erdl-landing/blob/main/erdl-spec.en.md) §7.2 E11):

| Model | `not(absent)` | Positioning | For Guard scenarios |
|---|---|---|---|
| Leaf collapse (this spec) | `true` | Rego NAF, safe policy language | fail-closed ✅ |
| Kleene | `undefined` | SQL query language | fail-open ⚠️ |

## 6. Mapping to code

| Spec item | Code |
|---|---|
| TVL ADT | `tvl.TVLInt` / `tvl.TVLBool` |
| Comparison collapse | `tvl.tvl_gt` / `tvl_eq` etc. (`_collapse_binary`); string/bool equality `tvl_eq_str/ne_str` / `tvl_eq_bool/ne_bool`; string ordering `tvl_gt_str/gte_str/lt_str/lte_str` (Unicode code-point order) |
| Two-valued boolean | `tvl.tvl_and` / `tvl_or` / `tvl_not` |
| Existence | `tvl.exists_int` / `exists_str` / `exists_bool` (type-dispatched, the only operator sensing field presence) |
| Quantifier E8 | `quantifiers.tvl_all` / `tvl_any` / `tvl_none` |
