# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.20] - 2026-09-07

### Added
- **Mutation testing for `catch_all_inert_when_explicit`**: `ResolutionFold` gains a `gate` parameter (`global` + 4 mutants `none`/`invert`/`same_ring`/`same_priority`), proving the property is a detector rather than a restatement of the gate embedded in the fold — each broken gate yields a SAT counterexample, replayed as a regression fixture.
- **`catch_all_then_irrelevant_when_explicit`**: §7.1 item 6 restated over the SPEC's own decision observable — a catch-all's `then` value is irrelevant to the final decision when an explicit rule is present (counterfactual, independent of the fold's internal `effective` flag).
- **`catch_all_override_irrelevant_when_explicit`**: the second §7.1.6 quantifier — a catch-all's `override` value is likewise irrelevant to the final decision (surfaced by mechanical per-quantifier extraction).
- **Obligation map** (`docs/obligation-map.md` / `.en.md`): every §7.1 / §7.0.2 obligation mapped to its proving property, with gaps listed explicitly.
- **§7.1.5b capability reachability**: non-vacuity tests for the cross-ring and same-ring override ALLOW covering a DENY (the positive half `override_soundness` does not assert).

### Changed
- **Bounded-proof wording**: `_prove` / module docstring, README, and CHANGELOG now state that resolution properties are proven UNSAT at cardinalities n∈{2,3,4} — a bounded exhaustive proof, not an unbounded claim over arbitrary length (no induction/padding argument exists).

### Fixed
- **README / DEVELOPER-GUIDE drift**: property list and API table updated from the stale `catch_all_neutral` (removed) to the current seven resolution properties; §7.1 count corrected from five to seven.

## [0.1.19] - 2026-09-06

### Fixed
- **S-expression form rewritten from list to SPEC §12 single-key object**.
- **Empty-array `avg`/`min`/`max` fold to `false` (G2)**.
- **Type-mismatched comparison folds + null asymmetry fixed**; **ReDoS detection added**.
- **`not_exists` key added (38-key S-expr parity)**.
- **`sub`/`div` arity fixed + unified scale-14 fixed-point**; **string NFC normalization**; **date nodes now string semantics**.

### Changed
- SPEC section refs aligned to erdl-spec.md v2.1.
- Added badges, POC-welcome note and support contact.

## [0.1.18] - 2026-09-05

### Fixed

- **Catch-all (empty-condition) ALLOW never overrides an explicit DENY (relax direction)**: `resolution.py` / `resolution_smt.py` guarded the DENY direction (catch-all DENY never overrides explicit ALLOW) but left the ALLOW direction open — a catch-all ALLOW with `override: critical/high` rewrote an explicit DENY across rings, the "fallback swallowing an explicit block". The ALLOW branch now carries a symmetric catch-all guard (and the Z3 `allow_relax` conjunct gained `Not(catch_all)`). Aligned with erdl-landing `evaluator.ts` and §7.1 item 6.

### Added

- **`catch_all_neutral` resolution property**: a catch-all rule never rewrites an established decision in either direction (EMERGENCY_HALT excepted, as it is the terminal fail-closed brake). This closes the "relax direction has zero property coverage" gap — previously `ring_respect` / `override_soundness` watched only the tighten (DENY) direction.

## [0.1.17] - 2026-09-05

### Added

- **String ordering (gt/gte/lt/lte)**: implemented per spec §5 — lexicographic (Unicode code-point) order, so `"2" gt "10"` is true, with E11 leaf collapse (Missing → false). Previously non-int fields raised `NotImplementedError`.
- **GitHub Actions CI**: two jobs — pytest unit tests + engine/vector cross-check (checks out erdl-landing, builds it, runs the `replay/` cross-checks).

### Fixed

- **Resolution catch-all semantics aligned with erdl-landing `evaluator.ts` (R1/R2)**: `resolution.py` / `resolution_smt.py` now model the v1.3 catch-all semantics — empty-condition rules sort last within a ring; a catch-all DENY never overrides an explicit ALLOW. The `ring_respect` property excludes catch-all DENY. Differential tests sweep catch_all ∈ {False, True}.
- Fixed the README's misleading "resolution ↔ erdl Evaluator" claim: the differential is actually `resolution.py` vs its Z3 model (`resolution_smt.py`), aligned to the erdl-landing engine.
- Fixed the `replay/*.mjs` engine cross-check import paths (`repos/erdl` was deleted → `erdl-landing`), and expanded the resolution cross-check to 10 cases (including catch-all).

### Changed

- **Documented EvalError/E12 accurately**: the SMT kernel has no EvalError constructor — division by zero / non-array aggregate collapse to `Missing` (or a compile-time `TypeError`); the README no longer claims "E1–E12 exact semantics" (tier≤2 fail-close is runtime behavior, not modeled).
- `semantics.md` literal wording: fixed-point decimals enter as `float`/`Fraction`/`Decimal`, not a "decimal string".
- Final doc alignment: `semantics.en.md` / `tvl-encoding` / `field-contracts` bilingual sync (dropped the unimplemented `rational` type, added string-ordering mapping, fixed style/branch inconsistencies).
- English README is now the default (`README.md`); Chinese moved to `README.zh-CN.md`; added a version badge to the README header.

## [0.1.16] - 2026-09-05

### Fixed

- **`\b` boundary semantics diverged from JS (non-word edge chars)**: `_LEFT_BOUNDARY` / `_RIGHT_BOUNDARY` assumed the body starts/ends with a word char, so `\b` followed by a non-word char (e.g. `\b!`) diverged from JS `RegExp.test` in BOTH directions: missed "a!b" (word→non-word boundary) and falsely matched "!a" (no flip at start). Now the body is split by its first/last char word-ness and the adjacent prefix/suffix is constrained to the opposite word-ness. Anchors `^\b` / `\b$` pin the boundary to the string edge (start/end count as non-word).
- +1 regression test (`test_word_boundary_nonword_edges`).

## [0.1.15] - 2026-09-05

### Added

- **Decimal literals (E2 money)**: `["lit", 0.5]` previously raised `NotImplementedError`; users had to hand-convert to scale-14 integers. Now `float` / `Fraction` / `Decimal` literals auto-convert to scale-14 (`float` via `Decimal(str(value))` — shortest round-trip, scientific-notation safe; `Fraction` / `Decimal` exact; NaN/inf rejected). Added `fixed_point.to_scale14_int`.
- +2 regression tests (decimal-literal equivalence + non-finite rejection).

### Changed

- `test_compile_unsupported_literal_raises` now uses a genuinely unsupported type (`None`), since `float` is supported.

## [0.1.14] - 2026-09-05

### Fixed

- **`always_denies` premise∩missing contradiction false fail-open**: when `missing_field` was also in `premises`, the probe asserted `premise(field) ∧ missing(field)` — always UNSAT — so a rule that never references the field was falsely reported fail-open. The probe now drops `missing_field` from `premises` (missing overrides premise).
- +1 regression test (`test_always_denies_missing_field_not_referenced`).

## [0.1.13] - 2026-09-05

### Fixed

- **Quantifier resource limit (E4)**: `{m}` / `{m,}` / `{m,n}` bounds beyond `MAX_REPEAT` (10000) raise `RegexError` (fail-closed), fixing the `{m,}` O(m) Concat compile-time DoS (`a{5000000,}` previously built a 5M-element Concat tree).
- **`{m,}` lazy encoding**: `Concat(Loop(atom,m,m), Star(atom))` replaces `_concat(*([atom]*m), Star(atom))`, removing the O(m) expansion.
- **`{m,n}` with m > n**: raises `RegexError` (JS SyntaxError semantics), fixing the previous `Z3Exception: loop lower bound must not exceed upper bound` crash.
- +3 regression tests (open-range lazy semantics / resource limit / m>n).

## [0.1.12] - 2026-09-05

### Added

- **Resolution-layer properties as SMT proofs** (`resolution_smt.py`): encodes `resolve()`'s ring / override / priority ordering as Z3 constraints; `override_soundness` / `ring_respect` / `emergency_shortcut` are proven UNSAT over every rule-set of exactly n modeled positions (bounded exhaustive proof at n∈{2,3,4}) — from 10 handwritten samples to a bounded symbolic proof.
- Differential verification (`test_resolution_smt.py`): exhaustive + random cross-check of the Z3 fold against the reference `resolve()`, guaranteeing no divergence; non-vacuity (antecedent reachable) is also asserted.

### Removed

- Removed `never-errors` and `always-allows` rows from the README's "what you can prove" table: neither has an API, and the SMT encoding is total (`Def | Missing`), so "never raises EvalError" is a design invariant, not a provable property. Removed to avoid claiming more than is measured.

## [0.1.11] - 2026-09-05

### Fixed

- **`can_fire` crashed forcing non-int fields Missing**: `can_fire(missing=[...])` unconditionally used `is_missing_int(ctx.field(m))` to force a field Missing, so string/bool guard fields raised `Z3Exception: Sort mismatch` (a crash, not a result). `always_denies(missing_field=...)` is its direct caller (the README's fail-closed probe) and crashed on common guards like `status == "active"`. `CompileContext.missing(path)` now type-dispatches (int/string/bool), `premise(path)` reuses `Not(missing(path))`, and `can_fire` uses `ctx.missing(m)`.
- 3 regression tests (string/bool missing don't crash + `always_denies` string missing fail-open).

## [0.1.10] - 2026-09-04

### Added

- **`epoch_ms` node (date string → epoch ms)**: `calendar.py` adds `tvl_epoch_ms`, parsing fixed-length date strings (date-only `YYYY-MM-DD`, datetime `YYYY-MM-DDTHH:MM:SS`, with `Z`, with `±HH:MM` offset) using Z3 `StrToInt` + `Extract` + a digit-regex guard, reusing `days_from_civil` for epoch; invalid/missing → `Missing`. `compiler.py` routes `["epoch_ms", arg]`. All 34 nodes are now encoded.
- 6 tests (`tests/test_epoch_ms.py`): date-only/datetime/leap-day/offset/invalid/missing/compiler integration, cross-checked against Python `datetime.fromisoformat`.

## [0.1.9] - 2026-09-04

### Added

- **`var` node (`$`/`$.path` context variable)**: `CompileContext.var(path)` returns a free TVLInt (spec §5.3 leaves the `$` namespace untyped, defaulting to int, consistent with an untyped field); `compiler.py` routes `["var", path]`. 33 of 34 nodes encoded, leaving only `epoch_ms`.
- 2 tests (`test_var_node_is_free_int_variable` / `test_var_node_can_fire`).

## [0.1.8] - 2026-09-04

### Fixed

- **`mul`/`div` arithmetic nodes silently unrouted (found in full review)**: `tvl_mul`/`tvl_div` were implemented and tested (`test_mul_div.py`), but `compiler.py`'s S-expression compiler never routed `["mul", …]`/`["div", …]` — rules using multiply/divide (E2 fixed-point "money" arithmetic) raised `NotImplementedError`. Now routed + integration test.

### Changed

- README "all 34 nodes have SMT encodings" corrected to "32/34": `var` and `epoch_ms` were not yet encoded.

## [0.1.7] - 2026-09-04

### Added

- **`aggregate` `avg`/`min`/`max` completed (spec §7.3(e))**: `tvl_aggregate` extended from `count`/`sum` to all 5 aggregate functions. `avg` empty → `Missing` (E11 leaf collapse makes comparisons false); non-empty → `Def(round_half_even(sum/count))` (scale-14 fixed-point); `min`/`max` empty → `Missing`, non-empty → `Def(If fold)`. The `None` type is no longer needed — spec §7.3(e)'s "fold false" semantics matches `Missing`'s E11 collapse.
- 7 new tests (avg exact / half / half-even rounding, min/max, empty-array folding, compiler integration); updated `test_aggregate_unsupported_fn_raises` to a genuinely unsupported `median`.

## [0.1.6] - 2026-09-04

### Added

- **`match` safe-regex subset → Z3 Re** (spec §7.3(d)): new `regex.py` with a hand-written recursive-descent parser compiling the safe-regex subset (a regular language) to Z3 regexes, encoding JS `RegExp.test()` no-flag semantics — unanchored substring search, `.` excluding line terminators (`\n \r \u2028 \u2029`), `\d\w\s` (and complements) ASCII semantics, `^`/`$` anchors, `\b` ASCII word boundary, quantifiers (including `{m,n}`/`{m,}`/lazy), alternation, groups (including `(?<name>)` named groups). `tvl_match` upgraded from literal exact-match to the full safe subset.
- **Non-regular construct rejection**: backreferences (`\1`–`\9`/`\k<…>`), lookaround (`(?=)`/`(?! )`/`(?<=)`/`(?<!)`), atomic groups, conditionals, inline flags, `\B`, mid-pattern `^`/`$` all raise `RegexError` (fail-closed, aligned with the runtime safeRegExp load-time rejection).
- 24 new tests (`tests/test_regex.py`): substring/anchors/`.`/classes/shorthands/quantifiers/word-boundary/real-rule-corpus/rejection cases.

## [0.1.5] - 2026-09-04

### Fixed

- **`in` set membership type-dispatched (third-party audit)**: `tvl_in` only supported int; string/bool field `in` raised `Z3Exception: Sort mismatch`. Added `tvl_in_str`/`tvl_in_bool`; `compiler.py` dispatches `in` by operand sort; mismatched member sorts raise `TypeError`.
- **`div` negative divisor half-even rounding (third-party audit)**: `_round_half_even_div` assumed a positive divisor; with a negative divisor, `num % den` carries the sign and rounds the wrong way. Added `_round_half_even_div_signed` which normalizes the sign, rounds, then reapplies it (half-even is symmetric: round(-x) = -round(x)).
- **Array elements modeled as raw τ (not TVL(τ))**: `array_element` returning TVL made `val_bool/val_int(Missing)` an undefined accessor (`value(Missing)`) — potentially unsound. Changed to return raw Bool/Int/String; quantifiers and aggregates no longer unwrap TVL on elements.

### Changed

- README: `aggregate` table honestly notes `avg/min/max` as pending; added a "known limitations" section (`match` literal-only, `length` non-ASCII bytes); removed dangling version/test counts.

## [0.1.4] - 2026-09-04

### Added

- **String/bool comparison and existence SMT encoding (third-party audit)**: previously `eq/ne/exists` only supported int fields; a string field's `eq(tool.name, …)` raised `Z3Exception: Sort mismatch`. Added `tvl_eq_str/ne_str/eq_bool/ne_bool` + `exists_str/exists_bool`; `compiler.py` dispatches `eq/ne/exists` by operand sort; `gt/gte/lt/lte` remain int-only, raising a clear `NotImplementedError` for string/bool (instead of a Z3 sort mismatch crash); mismatched operand sorts raise `TypeError`.

## [0.1.3] - 2026-09-04

### Fixed

- **`always_denies` safety-direction bug (third-party audit)**: the original implementation treated "missing field → guard always false" as fail-closed, ignoring the document's unmatched fallback decision. With an `ALLOW` fallback (the `resolution.resolve` default), a silenced guard falls through — the rule actually fails open. `always_denies` now takes `default_decision` (default `"ALLOW"`): with a `DENY` fallback a missing field does not bypass (fail-closed holds); with an `ALLOW` fallback a missing field does bypass (property is False).

## [0.1.2] - 2026-09-03

### Changed

- README rewritten with a developer-first narrative (bilingual) + a three-way Cedar/OPA comparison table.
- All spec references re-anchored from v2.0 to the ERDL language spec v2.1 (§7.2 / §7.3 / §5 / §7 / Appendix A); external links point to `erdl-spec.md` / `erdl-spec.en.md` at the erdl-landing repo root.
- `field_contracts.py` basis now points to the v2.1 language spec (was the v2.0 product spec).

### Added

- 34-node SMT encoding: values / logic / comparison / set / string / existence / quantifier / arithmetic / time / aggregate (`tvl.py`, `compiler.py`, `quantifiers.py`, `calendar.py`).
- Property verification: never-errors / always-denies / always-allows / subsumption / equivalence / disjointness, plus ERDL-specific override-soundness / ring-respect / emergency-shortcut (`properties.py`).
- Rule-resolution reference model (`resolution.py`).
- Fixed-point arithmetic, scale=14 + half-even rounding (`fixed_point.py`).
- Gregorian calendar civil algorithm: date_part / date_add / month_last_day (`calendar.py`).
- Verification schema field contracts (`field_contracts.py`).
- Cross-validation harness against the erdl reference engine and erdl-vectors frozen vectors (`replay/`).

### Documentation

- `README.md` / `README.en.md`
- `docs/semantics.md` — denotational semantics
- `docs/tvl-encoding.md` — three-valued logic SMT encoding
- `docs/field-contracts.md` — verification schema
- `docs/DEVELOPER-GUIDE.md` — developer guide
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `style_guide.md`

## [0.1.0] - unreleased

Initial release (pre-publication).

### Changed

- License: MIT → Apache-2.0 (explicit patent grant; aligns with the Cedar/OPA policy-verification ecosystem).
