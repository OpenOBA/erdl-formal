# erdl-formal Developer Guide

> For developers who want to extend or build on erdl-formal. After reading this you can: add a new node, add a new property, add a cross-check.

---

## 1. Architecture overview

```
ERDL rule (S-expression)
   │  compile_expr (compiler.py: schema-driven field types + quantifier index expansion)
   ▼
Z3 TVL expression (tvl.py: TVL(τ) = Def | Missing, leaf collapse)
   │  can_fire / always_denies / subsumes / ... (properties.py)
   ▼
sat / unsat + counterexample → replayed against the real engine (replay/)
```

**Module responsibilities**:

| Module | Responsibility | Depends on |
|---|---|---|
| `tvl.py` | Three-valued logic + Z3 encoding of the 34 nodes (core) | z3 |
| `quantifiers.py` | Quantifiers all/any/none (E8 empty-array collapse) | tvl |
| `fixed_point.py` | Fixed-point reference semantics (scale=14 + half-even) | fractions |
| `calendar.py` | Gregorian calendar civil algorithm + time nodes | tvl |
| `field_contracts.py` | Verification schema (field type / cardinality) | — |
| `compiler.py` | S-expression → Z3 TVL compiler | tvl, quantifiers, calendar, field_contracts |
| `properties.py` | Property verification (satisfiability + counterexamples) | compiler |
| `resolution.py` | Rule-resolution reference model (§7.1) | — |
| `resolution_smt.py` | Resolution-layer SMT proofs (§7.1 seven properties) | z3 |

**Dependency direction**: `compiler` → `tvl/quantifiers/calendar/field_contracts`; `properties` → `compiler`; `resolution` / `resolution_smt` are standalone.

---

## 2. Core abstractions

### 2.1 TVL (three-valued logic)

```python
TVL(τ) = Def(value: τ) | Missing   # τ ∈ {Int, Bool, String}
```

- `Def(v)`: has a value; `Missing`: field absent / undefined sentinel.
- **Leaf collapse**: comparison nodes collapse `Missing` to `false`; boolean operators are two-valued (not Kleene).
- Three types: `TVLInt` / `TVLBool` / `TVLStr` (each with `is_missing_*` / `val_*` / `str_def`).

### 2.2 Schema (field contracts)

```python
schema = Schema()
schema.add(FieldContract(field="amount", type="int"))          # scalar
schema.add(FieldContract(field="approvers", type="array", element_type="bool", cardinality=3))  # array (cardinality drives quantifier expansion)
```

### 2.3 S-expression (IR)

`["gt", ["field", "file_cls"], ["field", "op_cls"]]` — a nested `[op, args...]` list, aligned with the erdl external form.

---

## 3. How to add a new node

Using "adding `between` (closed interval)" as an example, three steps:

**Step 1 — add the encoding in `tvl.py`**:

```python
def tvl_between(x, a, b):
    """Closed interval [a, b] (numeric only); any Missing → Def(False)."""
    return TVLBool.Def(
        If(Or(is_missing_int(x), is_missing_int(a), is_missing_int(b)),
           False, And(val_int(a) <= val_int(x), val_int(x) <= val_int(b)))
    )
```

**Step 2 — add the dispatch in `compiler.py`**:

```python
if op == "between":
    return tvl_between(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx), compile_expr(expr[3], ctx))
```

**Step 3 — write tests** (`tests/test_between_days.py`):

```python
def test_between_in_range():
    assert is_true(simplify(val_bool(tvl_between(TVLInt.Def(5), TVLInt.Def(3), TVLInt.Def(10)))))
```

**Key point**: a new node must cover the three cases "normal / boundary / Missing collapse".

---

## 4. How to add a new property

Properties live in `properties.py`, following the pattern "build a Solver + compile the condition + add constraints + check sat/unsat":

```python
def disjoint(a_expr, b_expr, schema):
    """a ∧ b is unsatisfiable (mutually exclusive)."""
    ctx = CompileContext(schema)
    a = compile_expr(a_expr, ctx)
    b = compile_expr(b_expr, ctx)
    s = Solver()
    s.add(val_bool(a), val_bool(b))
    return s.check() != sat
```

**Key point**: a property = "write the negation of what you want to prove as a constraint, then check whether it is unsat". `unsat` = the property holds.

---

## 5. API reference

| Module | Key APIs | Purpose |
|---|---|---|
| tvl | `tvl_gt/eq/...` `tvl_and/or/not` `tvl_add/mul/div/round` `tvl_contains/match` `tvl_date_*` | Z3 encoding of the 34 nodes |
| tvl | `TVLInt/Bool/Str` `str_def` `val_int/val_bool/val_str` | TVL construction + deconstruction |
| quantifiers | `tvl_all/any/none` | Quantifiers (E8 empty-array collapse) |
| fixed_point | `parse/serialize/to_scale14_half_even` `add/sub/mul/div` | Fixed-point reference semantics (cross-check baseline) |
| calendar | `days_from_civil/civil_from_days/is_leap/days_in_month` | Civil algorithm |
| field_contracts | `FieldContract/Schema` | Verification schema |
| compiler | `CompileContext/compile_expr` | S-expression → Z3 |
| properties | `can_fire/always_denies/subsumes/equivalent/disjoint` | Property verification |
| resolution | `resolve` | Resolution (§7.1 ring/override/catch-all) |
| resolution_smt | `ResolutionFold` `override_soundness/ring_respect/catch_all_inert_when_explicit/catch_all_then_irrelevant_when_explicit/catch_all_override_irrelevant_when_explicit/emergency_shortcut/workflow_shortcut` | Resolution-layer SMT proofs |

---

## 6. How to add a cross-check

Cross-checks live in `replay/`, following the pattern "load erdl-vectors frozen vectors → recompute with this repo's reference semantics → compare item by item".

See `replay/crosscheck-vectors.py` (arithmetic) or `replay/crosscheck-calendar.py` (calendar):

```python
with open(VECTORS) as f:
    vectors = json.load(f, parse_float=str)["vectors"]
for v in vectors:
    if v["category"] != "V-ENGINE" or v["node"] not in (...):
        continue
    got = evaluate(v["expr_tree"])       # this repo's reference semantics
    assert got == v["expected"]["value"]  # item-by-item comparison against frozen answers
```

**Run**: `python replay/crosscheck-*.py` (requires `PYTHONPATH=src`).

---

## 7. Testing conventions

- One `test_*.py` per module, covering "normal / boundary / Missing / exception".
- Cross-checks live in `replay/` (not `tests/`, because they depend on erdl-vectors frozen vectors).
- Run everything: `python -m pytest -q` (currently 249 passing).

---

## 8. Build & publish

**Three install methods**:

```bash
# Users (from PyPI, one command)
pip install erdl-formal

# Developers (from source, editable install)
git clone https://github.com/OpenOBA/erdl-formal.git
cd erdl-formal
python -m pip install -e ".[dev]"

# Build a distribution from source (wheel + sdist)
python -m pip install build
python -m build        # produces dist/erdl_formal-<version>-py3-none-any.whl + .tar.gz
```

**Publish to PyPI**:

```bash
python -m pip install twine
twine upload --repository testpypi dist/*   # dry-run on TestPyPI first
twine upload dist/*                         # then real PyPI
```

> Publishing requires a PyPI account + API token (free, generated at `pypi.org/manage/account/token/`, project-scoped; the token is shown only once).
>
> A pure-Python project → a single `py3-none-any` universal wheel covers all platforms, no multi-platform matrix. `dist/`, `build/` are gitignored; artifacts don't go into git, only to PyPI / GitHub Releases.
