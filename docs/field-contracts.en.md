# Verification schema (Field Contracts)

> Basis: [erdl-language-spec](https://github.com/OpenOBA/erdl-landing/blob/main/spec/erdl-language-spec-v2.0.en.md) §3 / §7.0.1 field contracts (fact object) · this repo's `erdl_formal/field_contracts.py`

## 1. Positioning

ERDL v2.0's `EntityFieldContract` (field/display_name/type/description) serves rule production. This verifier defines a **verification schema** on top of it: extended field type + cardinality + optionality, as the premise for SMT decidability.

## 2. Contract structure

```
FieldContract {
  field: str                 # field path (e.g. tool.args.amount)
  type: 'int' | 'rational' | 'string' | 'bool' | 'array'
  element_type: str | None   # element type for 'array'
  cardinality: int | None    # array cardinality upper bound (premise for SMT index expansion)
  optional: bool             # whether the field may be absent (E11; default true)
}
```

## 3. Two categories

| Category | Required contract | When missing |
|---|---|---|
| Scalar rules | type (field presence + type) | comparison collapses false (E11) |
| Array / quantifier / aggregate | type + **cardinality** | cannot index-expand |

## 4. Connection to the SMT encoding

- **Scalar**: `field` → UF (schema-typed constraint); absent → `Missing` → comparison collapses false.
- **Array**: `cardinality` = concrete bound N → `all/any/none` expand into an N-way conjunction/disjunction (`quantifiers.py`).
- **Missing semantics**: with `optional=true` the field may be `Missing` (E11); with `optional=false` the field MUST be present (schema premise; Missing is not considered during verification).

## 5. Verification assumptions

The verification conclusion is a **conditional guarantee**:

> Assuming the field `tool.args.amount` is present and numeric, the rule satisfies property P.

At runtime the type checker ensures the assumption holds; the verifier only proves "the property holds when the assumption holds". The cardinality upper bound for array / quantifier / aggregate rules is explicitly declared via `cardinality` (the premise for SMT index expansion).
