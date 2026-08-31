# 三值逻辑 SMT 编码规范（草案）

> 状态：草案（已实现于 `erdl_formal/tvl.py`，Phase 2 测试覆盖）
> 依据：erdl-spec-v2.0 §10.2 E11/E12 · 审查意见 `docs/findings.md` P0-3

## 1. 编码载体

```
TVL(τ) = Def(value: τ) | Missing
```

- `Def(v)` — 有值（is_defined = true）
- `Missing` — 无值（字段缺失 / undefined 哨兵）

Z3 ADT 实现：`TVLInt = Def(int) | Missing`、`TVLBool = Def(bool) | Missing`。

## 2. E11 叶子折叠（核心语义）

**比较节点**（eq/ne/gt/gte/lt/lte）：任一操作数 `Missing` → `Def(false)`。

**算术节点**（add/sub/mul/div/round）：任一操作数 `Missing` → `EvalError`（条件上下文折叠 `false`；值上下文 → E12 tier 折叠）。

**布尔算子**（and/or/not）：**两值逻辑**——操作数是已折叠的 `Def(true/false)`，undefined 不传播到布尔层。故 `not(字段缺失 == x)` = `not(false)` = `true`。

## 3. E12 tier 折叠

`EvalError` → tier≤2 / Guard 缺省 fail-close（DENY）；tier 3–5 折叠为 `false`。

## 4. not 的 exists 守卫（§11.4）

核心 Expression 树的 `not` 不自动加 exists 守卫。对 **ALLOW 规则**写 `not(field==x)` 且字段缺失时 `not(false)=true` 会 **fail-open**，MUST 手动写 `exists(field) AND not(field==x)` 保证 fail-closed。Simple 投影的 `not_*` 派生算子已由 §11.4 编译层 exists 守卫兜底。

## 5. 决策：叶子折叠（非 Kleene）

本编码采用**叶子折叠**（规范 E11「字段缺失统一返回 false」），**不是 Kleene 传播**。依据（调研定案，见 findings.md P0-3）：

| 模型 | `not(缺失)` | 定位 | 对 Guard 场景 |
|---|---|---|---|
| 叶子折叠（本规范）| `true` | Rego NAF，安全策略语言 | fail-closed ✅ |
| Kleene | `undefined` | SQL 查询语言 | fail-open ⚠️ |

## 6. 与代码的对应

| 规范项 | 代码 |
|---|---|
| TVL ADT | `tvl.TVLInt` / `tvl.TVLBool` |
| 比较折叠 | `tvl.tvl_gt` / `tvl_eq` 等（`_collapse_binary`）|
| 布尔两值 | `tvl.tvl_and` / `tvl_or` / `tvl_not` |
| 存在性 | `tvl.exists_int`（唯一感知字段存在性）|
| 量词 E8 | `quantifiers.tvl_all` / `tvl_any` / `tvl_none` |
