# 验证 schema（Field Contracts）

> 依据：[erdl-spec v2.1](https://github.com/OpenOBA/erdl-landing/blob/main/erdl-spec.md)（EntityFieldContract）· 本仓 `erdl_formal/field_contracts.py`

## 1. 定位

ERDL v2.0 的 `EntityFieldContract`（field/display_name/type/description）服务于规则生产。本验证器在其基础上定义**验证 schema**：扩展字段类型 + 基数 + 可选性，作为 SMT 可判定性的前提。

## 2. 契约结构

```
FieldContract {
  field: str                 # 字段路径（如 tool.args.amount）
  type: 'int' | 'rational' | 'string' | 'bool' | 'array'
  element_type: str | None   # array 的元素类型
  cardinality: int | None    # array 的基数上限（SMT 索引展开的前提）
  optional: bool             # 字段可否缺失（E11；默认 true）
}
```

## 3. 分两类

| 类别 | 所需契约 | 缺失时 |
|---|---|---|
| 标量规则 | type（字段存在 + 类型）| 比较折叠 false（E11）|
| 数组/量词/聚合 | type + **cardinality** | 无法索引展开 |

## 4. 与 SMT 编码的衔接

- **标量**：`field` → UF（schema 类型约束）；缺失 → `Missing` → 比较折叠 false。
- **数组**：`cardinality` = 具体基数 N → `all/any/none` 展开为 N 路合取/析取（`quantifiers.py`）。
- **缺失语义**：`optional=true` 时字段可为 `Missing`（E11）；`optional=false` 时字段 MUST 存在（schema 前提，验证时不考虑 Missing）。

## 5. 验证假设

验证结论为**条件保证**：

> 假设字段 `tool.args.amount` 存在且为数值型，则规则满足性质 P。

运行时由类型检查确保假设成立；验证器只证明「假设成立时的性质」。数组/量词/聚合规则的基数上限通过 `cardinality` 显式声明（SMT 索引展开的前提）。
