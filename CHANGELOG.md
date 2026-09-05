# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.14] - 2026-09-05

### Fixed

- **`always_denies` 的 premise∩missing 矛盾误报 fail-open**：`still_fires` 探测时若 `missing_field` 也在 `premises` 中，会同时断言 `premise(field) ∧ missing(field)` → 恒 UNSAT → 即使规则根本不引用该字段也误报 fail-open。现在探测时把 `missing_field` 从 `premises` 剔除（missing 覆盖 premise），按字段真缺失重判。
- +1 回归测试（`test_always_denies_missing_field_not_referenced`）。

## [0.1.13] - 2026-09-05

### Fixed

- **量化符资源上限（E4）**：`{m}` / `{m,}` / `{m,n}` 的 lo/hi 超过 `MAX_REPEAT`（10000）时抛 `RegexError`（fail-closed），修复 `{m,}` 的 O(m) Concat 编译期膨胀 DoS 面（`a{5000000,}` 原先构建 500 万元组 Concat 树）。
- **`{m,}` 改惰性编码**：`Concat(Loop(atom,m,m), Star(atom))` 取代 `_concat(*([atom]*m), Star(atom))`，消除 O(m) 展开。
- **`{m,n}` 当 m > n**：抛 `RegexError`（JS SyntaxError 语义），修复原先的 `Z3Exception: loop lower bound must not exceed upper bound` 崩溃。
- +3 回归测试（开区间惰性语义 / 资源上限 / m>n）。

## [0.1.12] - 2026-09-05

### Added

- **裁决层三条性质纳入 SMT 全量证明**（`resolution_smt.py`）：把 `resolve()` 的 ring / override / priority 排序编码成 Z3 约束，`override_soundness` / `ring_respect` / `emergency_shortcut` 三条 ERDL 特有性质对**全部规则集**判 UNSAT——从 10 个手写单测升级为全量证明。
- 差分验证（`test_resolution_smt.py`）：Z3 fold 与参考实现 `resolve()` 穷举 + 随机对拍，保证符号模型零漂移；每条性质的非空性（antecedent 可达）亦被断言。

### Removed

- README「能证明什么」表删除 `never-errors` 与 `always-allows` 两行：二者无对应 API（`never_errors` / `always_allows` 在代码中不存在），且 SMT 编码为全函数（`Def | Missing`），「永不产生 EvalError」是模型的设计不变量、非可证性质。删除以避免「宣称大于测量」。

## [0.1.11] - 2026-09-05

### Fixed

- **`can_fire` 对非 int 字段强制 Missing 时崩溃**：`can_fire(missing=[...])` 无条件用 `is_missing_int(ctx.field(m))` 强制字段 Missing，string/bool 守卫字段直接 `Z3Exception: Sort mismatch`（崩溃而非返回验证结果）。`always_denies(missing_field=...)` 是其直接调用方（README 首页 fail-closed 探针），对 `status == "active"` 这类极常见守卫必崩。现 `CompileContext.missing(path)` 按字段类型分派（int/string/bool），`premise(path)` 复用为 `Not(missing(path))`，`can_fire` 改走 `ctx.missing(m)`。
- 3 个回归测试（string/bool 字段 missing 不崩 + `always_denies` string missing fail-open）。

## [0.1.10] - 2026-09-04

### Added

- **`epoch_ms` 节点（日期字符串→epoch 毫秒）编码**：`calendar.py` 新增 `tvl_epoch_ms`，用 Z3 `StrToInt` + `Extract` + 数字正则守卫解析固定长度日期字符串（date-only `YYYY-MM-DD`、datetime `YYYY-MM-DDTHH:MM:SS`、带 `Z`、带 `±HH:MM` 时区偏移），复用 `days_from_civil` 算 epoch；非法/缺失→`Missing`。`compiler.py` 补 `["epoch_ms", arg]` 路由。至此 **34 节点全部编码**。
- 6 个测试（`tests/test_epoch_ms.py`）：date-only/datetime/闰日/时区偏移/非法/缺失/编译器集成，交叉验证 Python `datetime.fromisoformat`。

## [0.1.9] - 2026-09-04

### Added

- **`var` 节点（`$`/`$.path` 上下文变量）编码**：`CompileContext.var(path)` 返回自由 TVLInt 变量（spec §5.3 未声明 `$` 命名空间类型，默认 int，与未定型 field 一致）；`compiler.py` 补 `["var", path]` 路由。至此 34 节点中 33 个已编码，仅余 `epoch_ms`。
- 2 个测试（`test_var_node_is_free_int_variable` / `test_var_node_can_fire`）。

## [0.1.8] - 2026-09-04

### Fixed

- **`mul`/`div` 算术节点静默缺口（全面 review 发现）**：`tvl_mul`/`tvl_div` 早已实现并有测试（`test_mul_div.py`），但 `compiler.py` 的 S-expression 编译器从未路由 `["mul", …]`/`["div", …]`——规则一旦用到乘法/除法（E2 定点「钱」算术）会直接 `NotImplementedError`。现补路由 + 集成测试。

### Changed

- README「34 节点全部有 SMT 编码」修正为「32/34」：`var`（`$`/`$.path` 上下文变量）与 `epoch_ms`（日期字符串→毫秒解析）两个节点未在规则中使用、暂未编码，如实标注。

## [0.1.7] - 2026-09-04

### Added

- **`aggregate` `avg`/`min`/`max` 补全（对齐 spec §7.3(e)）**：`tvl_aggregate` 从只支持 `count`/`sum` 扩展为支持全部 5 个聚合函数。`avg` 空数组→`Missing`（E11 叶子折叠使比较为 false），非空→`Def(round_half_even(sum/count))`（scale-14 定点）；`min`/`max` 空数组→`Missing`，非空→`Def(If 折叠)`。不再需要 `None` 类型——spec §7.3(e) 的「折叠 false」语义与 `Missing` 的 E11 折叠一致。
- 7 个新测试（avg 精确/半值/half-even 舍入、min/max、空数组折叠、编译器集成）；更新 `test_aggregate_unsupported_fn_raises` 为真正不支持的 `median`。

## [0.1.6] - 2026-09-04

### Added

- **`match` 安全正则子集 → Z3 Re 编码**（对齐 spec §7.3(d)）：新增 `regex.py`，手写递归下降解析器把「安全正则子集」（正则语言）编译成 Z3 正则，精确编码 JS `RegExp.test()` 无 flag 语义——非锚定子串搜索、`.` 排除行终止符（`\n \r \u2028 \u2029`）、`\d\w\s`（及补集）ASCII 语义、`^`/`$` 锚点、`\b` ASCII 词边界、量词（含 `{m,n}`/`{m,}`/惰性）、交替、分组（含 `(?<name>)` 命名组）。`tvl_match` 从「字面量精确匹配」升级为完整安全子集匹配。
- **非正则构造拒绝**：反向引用（`\1`–`\9`/`\k<…>`）、环视（`(?=)`/`(?! )`/`(?<=)`/`(?<!)`）、原子组、条件组、内联标志、`\B`、中间位置 `^`/`$` 一律抛 `RegexError`（fail-closed，与运行时 safeRegExp 加载时拒绝对齐）。
- 24 个新测试（`tests/test_regex.py`）：子串/锚点/`.`/字符类/简写/量词/词边界/真实规则语料/拒绝用例。

## [0.1.5] - 2026-09-04

### Fixed

- **`in` 集合成员按字段类型分派（第三方审计）**：`tvl_in` 只支持 int，字符串/布尔字段的
  `in` 直接 `Z3Exception: Sort mismatch`。补 `tvl_in_str`/`tvl_in_bool`，`compiler.py` 对 `in`
  按操作数 sort 分派；成员 sort 不一致抛 `TypeError`。
- **`div` 负数除数 half-even 舍入（第三方审计）**：`_round_half_even_div` 假设正除数，负数
  除数时 `num % den` 带负号导致舍入方向错。补 `_round_half_even_div_signed` 将符号归一化后
  舍入再回贴符号（half-even 对称：round(-x) = -round(x)）。
- **数组元素建模为原始 τ（非 TVL(τ)）**：`array_element` 返回 TVL 类型导致量词/聚合的
  `val_bool/val_int(Missing)` 为未定义访问器（`value(Missing)`），潜在 unsound。改为返回
  原始 Bool/Int/String，量词与聚合不再对元素做 TVL 解包。

### Changed

- README：`aggregate` 表项如实标注 `avg/min/max` 待实现；新增「已知限制」段（`match` 仅
  字面量、`length` 非 ASCII 字节数）；版本/测试计数去悬空数字。

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
