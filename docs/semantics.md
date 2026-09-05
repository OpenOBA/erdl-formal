# 指称语义（Denotational Semantics）· 34 节点内核

> 依据：[erdl-language-spec](https://github.com/OpenOBA/erdl-landing/blob/main/erdl-spec.md) §5 / §7 · 本仓 `tvl.py` / `quantifiers.py` / `fixed_point.py`

本文定义 ERDL 表达式内核 34 节点的**指称语义**——每个节点的「输入 → 输出」数学函数。它是符号编译器（ERDL → SMT-LIB）的编码依据，也是反例回放的判定基准。

## 1. 值域（Value Domain）

```
τ ∈ { Int, Rational, String, Bool, Array<τ>, Set<τ> }
V  = TVL(τ) = Def(value: τ) | Missing          # E11 undefined 哨兵
```

- `Rational` = 高精度有界有理数（128 位分子/分母），中间计算精确、仅输出节点 scale=14 + half-even（E2）。
- `Missing` = 字段缺失 / undefined；`EvalError`（E12 求值错误，除零、类型不匹配算术）在**本 SMT 内核折叠为 `Missing`**（见 E3/E12 注）。

## 2. 节点指称（按 10 组）

设 `ctx : Context`（字段映射），`⟦e⟧(ctx) : V`。

### 取值（3）

| 节点 | 指称 |
|---|---|
| `field(f)` | `Def(ctx[f])` 若 `f ∈ ctx`；否则 `Missing` |
| `var(v)` | `Def(ctx.$[v])`（`$` / `$.path`）；缺失则 `Missing` |
| `literal(c)` | `Def(c)`（定点小数（`float`/`Fraction`/`Decimal`）→ Rational(scale-14) / NFC 字符串 / Bool）|

### 逻辑（3，两值）

| 节点 | 指称 |
|---|---|
| `and(a,b)` | `Def(val(a) ∧ val(b))`（操作数已折叠为 Def(Bool)，两值）|
| `or(a,b)` | `Def(val(a) ∨ val(b))` |
| `not(a)` | `Def(¬val(a))` |

> **E11 叶子折叠**：逻辑算子是**两值**的——其操作数是已折叠的布尔值（比较节点把 Missing 折叠为 false），undefined 不传播到布尔层。

### 比较（6，E11 折叠）

| 节点 | 指称 |
|---|---|
| `eq(a,b)` `ne(a,b)` | `Def(false)` 若任一操作数 Missing；否则 `Def(val(a) = / ≠ val(b))` |
| `gt(a,b)` `gte` `lt` `lte` | `Def(false)` 若任一 Missing；否则 `Def(val(a) > / ≥ / < / ≤ val(b))`（数值序 / 字符串 Unicode 码点序）|

### 集合（1）

`in(x, S)` = `Def(false)` 若 `x` Missing；否则 `Def(val(x) ∈ S)`。

### 字符串（4）

`contains(s,t)` / `starts_with(s,t)` / `ends_with(s,t)` = 前缀/后缀/包含判定（Missing → `Def(false)`）；`match(s,re)` = 安全正则（大小写敏感，ReDoS 防护，步数 ≤10000）。

### 存在/量纲（3）

| 节点 | 指称 |
|---|---|
| `exists(x)` | `Def(¬is_missing(x))`（唯一感知字段存在性）|
| `length(x)` | `Def(码点数)`（Unicode 码点，非 UTF-16 长度）|
| `between(x,a,b)` | `Def(a ≤ val(x) ≤ b)`（闭区间，仅数值；Missing → false）|

### 量词（3，E8 空数组折叠）

`all/any/none(array, pred)`：空数组 → `Def(false)`（E8 反空洞真）；非空 → `Def(∧/∨/¬∨_{i} pred(array[i]))`。

### 算术（5，E2 定点有理数）

`add/sub/mul/div`：精确有理数运算（128 位）；`div` 除零 → `Missing`（EvalError 的 SMT 近似）。`round`：half-even 舍入。**中间不舍入，仅输出节点 scale=14 + half-even**。

### 时间（5）

`epoch_ms` / `days_between` = 整数时间戳 / `floor(差/86400000)`（UTC）；`date_add` / `date_part` / `month_last_day` = 格里高利历（UTC，civil 算法）。

### 聚合（1）

`aggregate(fn, over)`：`count/sum` 空数组 → `Some(0)`；`avg/min/max` 空数组 → `None`（条件上下文折叠 false）。非数组 over → 编译期 `TypeError`（fail-fast）。

## 3. E 约束（语义层）

| 约束 | 语义 |
|---|---|
| E1 | 纯函数（无副作用/无时钟）；within/rate 状态在 GuardStateManager 树外 |
| E2 | 定点 scale=14 + half-even；中间 128 位有理数 |
| E3/E12 | EvalError → tier≤2 fail-close / tier 3-5 折叠 false（**运行时** tier 折叠；本 SMT 内核将 EvalError 近似为 `Missing` = 折叠 false，tier≤2 fail-close 不在内核建模）|
| E4 | 资源上限（Grade A 树深≤6/节点≤64/数组≤10000）|
| E5 | 加载时类型检查 |
| E8 | 量词空数组一律 false（all/none 为刻意安全偏离）|
| E10 | 字符串 NFC 规范化 |
| E11 | undefined 哨兵（叶子折叠）|

## 4. 决策：叶子折叠（非 Kleene）

本语义采用**叶子折叠**（E11「字段缺失统一返回 false」），非 Kleene 传播。依据见 `docs/tvl-encoding.md` §5。
