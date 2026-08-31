# schema 假设前提设计（草案）

> 状态：草案
> 依据：erdl-spec-v2.0 §7 字段契约 · 方案 `docs/plan.md` §9 · 审查 `docs/findings.md` P0-1

## 1. 缺口

ERDL v2.0 无用于形式化验证的 schema 语言。字段契约 `EntityFieldContract`（field/display_name/type/description）定位是**规则生产的约束源**，缺「集合基数上限」，无法支撑量词/聚合的 SMT 索引展开。

## 2. 验证假设（短期）

验证结论表述为**条件保证**：

> 假设字段 `tool.args.amount` 存在且为数值型，则规则 F1 满足性质 P。

运行时由类型检查确保假设成立；验证器只证明「假设成立时的性质」。

## 3. 分两类影响

| 节点类别 | 所需前提 | 字段契约能否提供 | 影响 |
|---|---|---|---|
| 标量规则（密级/金额）| 字段存在 + type 匹配 | ✅（type 已有）| POC 不受阻 |
| 数组/量词/聚合 | 字段存在 + type + **基数上限** | ❌ 缺基数 | 需 schema 子语言 |

## 4. 量词索引展开的基数声明

`all/any/none` 的 SMT 编码需**具体数组基数 N**（索引展开为 N 路合取/析取）。POC 阶段将 N 作为**固定常量**（schema 前提）；未来 v2.1 schema 子语言声明 `max_cardinality`，验证时展开到该上限。

## 5. 路线

| 阶段 | 内容 |
|---|---|
| 短期（POC）| schema 作「验证假设」，结论为条件保证 |
| 中期（v2.1）| 可选 schema 子语言：扩展 `EntityFieldContract` 加「基数上限 / 数组元素类型 / 字段可选性」|
| 长期 | schema 成为规范正式组成部分（与「预置类型 + 自由字段」并存）|
