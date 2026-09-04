# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2026-09-04

### Added

- **字符串/布尔比较与存在的 SMT 编码（第三方审计发现）**：此前 `eq/ne/exists` 只支持 int
  字段，字符串字段的 `eq(tool.name, …)` 直接 `Z3Exception: Sort mismatch`。现在补
  `tvl_eq_str/ne_str/eq_bool/ne_bool` + `exists_str/exists_bool`，`compiler.py` 对 `eq/ne/exists`
  按操作数 sort 分派；`gt/gte/lt/lte` 仍仅 int，遇 string/bool 抛清晰 `NotImplementedError`
  （不再让 Z3 崩 sort mismatch），操作数 sort 不一致抛 `TypeError`。感谢 ANP2 Network。

## [0.1.3] - 2026-09-04

### Fixed

- **`always_denies` 安全方向 bug（第三方审计发现）**：原实现把「字段缺失 → 守卫永假」
  一律当作 fail-closed，忽略了文档未命中兜底决策。当兜底为 `ALLOW`（`resolution.resolve`
  默认）时，守卫不命中即放行——规则实际 fail-open。现在 `always_denies` 接受
  `default_decision`（默认 `"ALLOW"`）：兜底为 `DENY` 时字段缺失不绕过（fail-closed 成立）；
  兜底为 `ALLOW` 时缺失字段会绕过（属性返回 False）。感谢 ANP2 Network 的第三方审计。

## [0.1.2] - 2026-09-03

### Changed

- README 重写为开发者优先叙事（中英双语）+ Cedar/OPA 三维对比表。
- 所有 spec 引用从 v2.0 重锚到 ERDL 语言规范 v2.1（§7.2 / §7.3 / §5 / §7 / 附录 A）；外链统一指 erdl-landing 仓库根的 `erdl-spec.md` / `erdl-spec.en.md`。
- `field_contracts.py` 依据统一指 v2.1 语言规范（原指向产品规范 v2.0）。

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

### Changed

- License: MIT → Apache-2.0 (explicit patent grant; aligns with the Cedar/OPA
  policy-verification ecosystem).
