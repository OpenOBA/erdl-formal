# ERDL 形式化验证方案 — 审查意见汇总（活文档）

> 汇总所有针对 `erdl-formal` POC 方案的审查意见（Henry 转来的交叉审查/第三方发现），逐条记录 + 处置状态。**单一权威源，避免意见分散。**
>
> 关联方案：`docs/research/erdl-formal-verification-plan-2026-08-31.md`（当前 v5）
> 关联审校：`deliverables/erdl-formal-verification-plan-review-2026-08-31.md`（Qwen3.8 首轮，已并入方案 v2/v3）
> 维护：OpenOBA

---

## 处置状态一览

| # | 意见 | 核实 | 处置 | 落点 |
|---|---|---|---|---|
| 1.1 | schema 层缺失导致验证根基不稳 | ✅ 成立 + 1 nuance | 已修 | spec §7 标注 + 方案 v4 §9 |
| 1.2 | 三值逻辑与规范语义存在实现鸿沟 | ✅ 成立 + 解法纠正 | 已修 | 方案 v5 §3 |
| 1.3 | 决策类型与策略集语义未对齐 | ✅ 成立 | 已修 | 方案 v6 §2 |
| 1.4 | 34 节点映射粒度不足 | ✅ 成立 | 已修 | 方案 v7 §3 |

---

## 1.1 schema 层缺失导致验证根基不稳

**原意见**：

ERDL 规范 v2.0（§3 Entity 定义）采用"预置类型 + 自由字段"设计，context 字段完全自由。规范 §7.3(a) 明确"字段缺失是常态"，E11 空值传播是核心安全机制。但形式化验证方案要求"field contracts 声明集合基数上限"作为可判定性前提。这意味着：

- **规范层面**：ERDL v2.0 不存在 schema 语言，无法声明字段存在性、类型、基数
- **验证层面**：没有 schema，SMT 无法做索引展开，量词无法 ground，空值传播无法编码为有限状态
- **结论**：形式化验证的"全量保证"承诺，在规范当前版本中技术上不可兑现

**核实结果**：✅ 核心成立；一处 nuance 修正——规范**有**「字段契约 `EntityFieldContract`（field/display_name/type/description）」，但定位是**规则生产约束源**（LLM 生成字段枚举），缺**「集合基数上限」**。分两类影响：**标量规则**（POC 首选）不受阻（type 已有）；**数组/量词/聚合**缺基数，「全量保证」不可兑现。

**处置**：
- spec §7「字段契约」小节加「〔验证缺口 · 2026-08-31 · erdl-formal〕」标注（权威源）。
- 方案 v4 §9：短期 schema 作「验证假设」（条件保证：假设字段存在且 type 匹配则 P 成立）/ 中期 v2.1 扩展 `EntityFieldContract` 补基数上限/数组元素类型/可选性 / 长期 schema 入规范。

---

## 1.2 三值逻辑与规范语义存在实现鸿沟

**原意见**：

规范 E11 定义了空值传播的行为表（字段缺失时除 exists 外统一返回 false），但方案仅提到"(有值标志, 值) 抬升编码"，未给出：
- 三值逻辑的真值表（true/false/undefined 的 and/or/not 组合）
- 与 E12 tier 折叠的交互（求值错误在 tier≤2 时 fail-close，tier 3–5 时折叠为 false）
- 算术表达式中 undefined 的处理（规范说"返回 EvaluationError"，但 SMT 通常不处理异常）

解决办法：显式定义三值逻辑编码。用二元组 (is_defined: Bool, value: τ) 编码，and/or/not 按短路语义处理：false AND undefined = false（安全失败），true OR undefined = true，其余情况为 undefined。在 SMT 中用代数数据类型（ADT）编码 TVL(Bool) 和 TVL(Int)。

**核实结果**：✅ 核心成立（原「抬升编码」确不完备）；⚠️ **解法纠正**——规范 E11 是「**叶子折叠**」（字段缺失统一返回 false），**不是 Kleene 传播**。undefined 在叶子（比较/算术）就被折叠，不传播到布尔层，故**无需 Kleene 真值表**。唯一行为差异在 `not`：规范用 §11.4 **exists 守卫**（编译层 `exists(field) AND not(...)`）兜底，而非 Kleene 运行时传播。

**处置**：
- 方案 v5 §3 补全「三值逻辑编码」：`TVL(τ) = Def(value) | Missing` ADT 哨兵 + 叶子折叠（比较→false / 算术→EvalError）+ 布尔两值 + E12 tier 折叠（EvalError → tier≤2 fail-close / tier 3-5 false）+ `not` 的 exists 守卫。
- 无需标注 spec（E11 已是权威且清晰，本意见是方案层补全）。

---

## 1.3 决策类型与策略集语义未对齐

**原意见**：

规范 §6 定义 13 种决策类型，§7.0.2 定义了 ring 分层执行（0 内核→3 建议）和 override 覆盖机制（仅 DENY→ALLOW 方向）。方案借鉴 Cedar 的 6 性质，但 Cedar 没有 ring 和 override 概念。这导致：

- **性质定义不完整**：subsumption 在 ERDL 中不仅是逻辑蕴含，还受 ring 层级和 override 方向约束
- **EMERGENCY_HALT 短路语义**：规范说"命中即短路"，但方案未说明如何在 SMT 中编码这种控制流
- **REQUEST_HUMAN 的验证语义**：在"恒触发"性质中，REQUEST_HUMAN 算"触发"还是"未触发"？

解决办法：重新定义 ERDL 特有性质：override-soundness（仅 DENY→ALLOW 方向覆盖）、ring-respect（低 ring 拦截不能被高 ring 放行覆盖）、emergency-shortcut（命中即控制流中断）。定义决策类型到布尔验证状态的映射：拦截性→false、放行→true、人工介入→按需映射。

**核实结果**：✅ 成立。规范确证：①13 决策类型（§27.5 权威枚举，line 1950）；②优先级冲突解决（§9：priority→override→定义顺序，override 仅 DENY→ALLOW，line 1155-1160）；③ring 分层（0内核/1恢复/2审批/3建议，line 1341）；④EMERGENCY_HALT = 无条件终止系统（§10.6 line 1304）+ 硬约束「违反即被拦截」（§6.1 line 616）。原意见的节号（§6/§7.0.2）与规范实际节号略有出入，但实质全部成立。

**处置**：
- 方案 v6 §2 补：①决策类型→布尔验证状态映射（13 种→拦截/放行/中间态 3 类）；②「触发 vs 拦截/放行/人工介入」三层区分（回答 REQUEST_HUMAN 之问）；③ERDL 特有性质 override-soundness / ring-respect / emergency-shortcut。

---

## 1.4 34 节点映射粒度不足

**原意见**：

方案 §3 的 SMT 映射以"节点组"为单位描述，但规范附录 A 要求精确到 34 个语义节点。当前映射存在：
- **取值组**：未区分 field（实体字段）/ var（上下文变量）/ 字面量（常量）的 SMT 编码差异
- **逻辑组**：and/or/not 的三值逻辑版本未展开
- **字符串组**：match（正则）被规避，但 contains/starts_with/ends_with 的 SMT 编码未给出
- **时间组**：5 个时间节点的 UTC 语义在 SMT 中如何保持跨实现一致性？

解决办法：在 SMT 映射中明确：field→未解释函数 UF（受 schema 类型约束）、var→自由变量（受上下文约束）、literal→SMT 常量。为每个节点给出独立的 SMT-LIB 编码模板。

**核实结果**：✅ 成立。§3 原为组级映射，未下沉到 34 节点。其中「逻辑组 and/or/not 三值逻辑版本未展开」一条：v5 已澄清逻辑组是**两值**（叶子折叠），非三值——但原意见要求「展开」的方向正确，逐节点模板已给出（and→∧/or→∨/not→¬，两值 + exists 守卫）。

**处置**：
- 方案 v7 §3 补「34 节点逐节点 SMT 编码模板」：field→UF（schema 约束 σ）、var→自由变量、字面量→SMT 常量；逐节点给编码（含字符串 str.contains/prefixof/suffixof、量词索引展开、算术 QF_LIA/NRA、时间 epoch_ms/days_between 可编码但 date_part/date_add/month_last_day 日历层规避）。
- 诚实边界：时间节点日历层无法纯 SMT 编码，跨实现一致性靠 §10.5 UTC 语义 + 双实现生成向量，非 SMT。

**追问（Henry）：时间是重要要素，有没有解决方案？** → 有，分层验证（方案 v8 §3）：①时区已由引擎转 UTC（§10.5），求值器只碰 epoch_ms 整数；②时间戳层（epoch_ms/days_between）全量 SMT；③日历层（date_part/date_add/month_last_day）路线 A=规范已选双实现生成向量（§10.5/§48.2）+ 路线 B=civil 算法 SMT 公理化（Hinnant days_from_civil/civil_from_days + Zeller，M2/M3）。

---

_后续审查意见继续追加到本文档，保持单一权威源。_

---

# 二、综合审查问题清单（P0/P1/P2 · 2026-09-01）

> 全量审查（Henry 转来），比 1.1–1.4 更系统。逐项处置已入方案 v9 §10。此处记录审查原意 + 处置状态。

## 处置总表（13 项 + POC 调整）

| # | 问题 | 处置 |
|---|---|---|
| P0-1 | schema 契约冲突 | ✅ 已处理（=1.1，v4 §9 + spec §7 标注）|
| P0-2 | translation validation 方法缺失 | ➕ 四层：差分测试/反例 harness/符号执行/Lean 证明 |
| P0-3 | 三值逻辑编码未具体化 | ⚠️ 部分处理 + **分歧（Kleene vs 折叠）** |
| P0-4 | 聚合返回类型不统一 | ➕ Option<Int> 统一 |
| P1-1 | override/ring 性质 | ✅ 已处理（=1.3，v6 §2）|
| P1-2 | POC 选题简单 | ➕ 两阶段 POC |
| P1-3 | E4 资源上限可表达性 | ➕ 分级（Grade A 静态检查 + schema max_cardinality）|
| P1-4 | scale=14+half-even 建模 | ➕ POC 避 round/div + 完整版 QF_BV |
| P1-5 | temporal_state 建模缺失 | ➕ POC/Grade A 不支持 within/rate |
| P1-6 | var 节点映射缺失 | ✅ 已处理（=1.4，v7 §3）|
| P2-1 | formal ↔ vectors 互补 | ➕ 分工 + 汇合点 |
| P2-2 | NFC 信任假设审计影响 | ➕ 解析层 + canonical_tree 标记 |
| P2-3 | 13 决策类型验证语义 | ✅ 已处理（=1.3，v6 §2），映射微调 |

## 唯一实质分歧（P0-3）— 已调研定案

审查给 Kleene 三值表（`比较→undefined`、`not(undefined)=undefined`、`false AND undefined=false`）；但规范 E11「字段缺失统一返回 false」是**叶子折叠**（比较→false），两者不符。

**调研定案（2026-09-01，三参照系）**：
- SQL = Kleene（`NOT UNKNOWN=UNKNOWN`，NULL 传播）——查询语言语义，fail-open。
- CEL = 显式 `has(field)` + 类型检查报错——对应 ERDL 的 `exists` 节点。
- **Rego = 否定即失败（NAF：`not(undefined)=true`）——安全策略语言语义，fail-closed**，官方例「`deny if not input.email`（邮箱缺失→DENY）」。

**决策：采纳规范 E11 折叠，否决 Kleene**。理由：①折叠 = Rego NAF（`not(缺失)=true`），是安全策略语言事实标准、fail-closed；②Kleene = SQL 查询语义、fail-open，对 Guard/安全场景有害；③E11「统一返回 false」是明确的，核心 `not` 无歧义（其操作数永远是已折叠布尔值，`not(false)=true`）。

**纠偏**：原「核心 not 歧义、标 SPEC 待澄清 v2.1」系我误判——收回；规范 E11 已充分定义，无需 spec 澄清。

## POC 调整（两阶段）

- Phase 1（2 天）：G3 密级比较验证基本流程；Phase 2（3–5 天）：加量词 all 或三值 AND 规则（「所有审批人已批准→ALLOW」测空数组折叠）。
- 工期 5–8 天；量化成功标准：≥2 条规则性质证明 + ≥1 反例回放一致 + 产出《schema 假设前提草案》《三值逻辑 SMT 编码规范草案》。
