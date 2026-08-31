# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- 34-node SMT encoding: values / logic / comparison / set / string / existence /
  quantifier / arithmetic / time / aggregate (`tvl.py`, `compiler.py`,
  `quantifiers.py`, `calendar.py`).
- Property verification: never-errors / always-denies / always-allows /
  subsumption / equivalence / disjointness, plus ERDL-specific
  override-soundness / ring-respect / emergency-shortcut (`properties.py`).
- Rule-resolution reference model (`resolution.py`).
- Fixed-point arithmetic, scale=14 + half-even rounding (`fixed_point.py`).
- Gregorian calendar civil algorithm: date_part / date_add / month_last_day
  (`calendar.py`).
- Verification schema field contracts (`field_contracts.py`).
- Cross-validation harness against the erdl reference engine and erdl-vectors
  frozen vectors (`replay/`).

### Documentation

- `README.md` / `README.en.md`
- `docs/semantics.md` — denotational semantics
- `docs/tvl-encoding.md` — three-valued logic SMT encoding
- `docs/field-contracts.md` — verification schema
- `docs/DEVELOPER-GUIDE.md` — developer guide
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `style_guide.md`

## [0.1.0] - unreleased

Initial release (pre-publication).
