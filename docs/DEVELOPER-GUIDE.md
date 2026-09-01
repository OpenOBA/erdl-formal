# erdl-formal 二开指南（Developer Guide）

> 面向想要扩展、二次开发 erdl-formal 的开发者。读完你能：加一个新节点、加一个新性质、加一道交叉验证。

---

## 1. 架构总览

```
ERDL 规则（S-expression）
   │  compile_expr（compiler.py，schema 驱动字段类型 + 量词索引展开）
   ▼
Z3 TVL 表达式（tvl.py：TVL(τ) = Def | Missing，叶子折叠）
   │  can_fire / always_denies / subsumes / ...（properties.py）
   ▼
sat / unsat + 反例 → 回放真实引擎交叉验证（replay/）
```

**模块职责**：

| 模块 | 职责 | 依赖 |
|---|---|---|
| `tvl.py` | 三值逻辑 + 34 节点的 Z3 编码（核心）| z3 |
| `quantifiers.py` | 量词 all/any/none（E8 空数组折叠）| tvl |
| `fixed_point.py` | 定点小数参考语义（scale=14+half-even）| fractions |
| `calendar.py` | 格里高利历 civil 算法 + 时间节点 | tvl |
| `field_contracts.py` | 验证 schema（字段类型/基数）| — |
| `compiler.py` | S-expression → Z3 TVL 编译器 | tvl, quantifiers, calendar, field_contracts |
| `properties.py` | 性质验证（可满足性 + 反例）| compiler |
| `resolution.py` | 规则裁决参考模型（§9）| — |

**依赖方向**：`compiler` → `tvl/quantifiers/calendar/field_contracts`；`properties` → `compiler`；`resolution` 独立。

---

## 2. 核心抽象

### 2.1 TVL（三值逻辑）

```python
TVL(τ) = Def(value: τ) | Missing   # τ ∈ {Int, Bool, String}
```

- `Def(v)`：有值；`Missing`：字段缺失 / undefined 哨兵。
- **叶子折叠**：比较节点把 Missing 折叠为 `false`，布尔算子两值（不是 Kleene）。
- 三种类型：`TVLInt` / `TVLBool` / `TVLStr`（分别有 `is_missing_*` / `val_*` / `str_def`）。

### 2.2 Schema（字段契约）

```python
schema = Schema()
schema.add(FieldContract(field="amount", type="int"))          # 标量
schema.add(FieldContract(field="approvers", type="array", element_type="bool", cardinality=3))  # 数组（基数驱动量词展开）
```

### 2.3 S-expression（IR）

`["gt", ["field", "file_cls"], ["field", "op_cls"]]` —— `[op, args...]` 嵌套列表，对齐 erdl 外部形式。

---

## 3. 如何添加一个新节点

以「添加 `between`（闭区间）」为例，三步：

**Step 1 — `tvl.py` 加编码**：

```python
def tvl_between(x, a, b):
    """闭区间 [a, b]（仅数值）；任一 Missing → Def(False)."""
    return TVLBool.Def(
        If(Or(is_missing_int(x), is_missing_int(a), is_missing_int(b)),
           False, And(val_int(a) <= val_int(x), val_int(x) <= val_int(b)))
    )
```

**Step 2 — `compiler.py` 加派发**：

```python
if op == "between":
    return tvl_between(compile_expr(expr[1], ctx), compile_expr(expr[2], ctx), compile_expr(expr[3], ctx))
```

**Step 3 — 写测试**（`tests/test_between_days.py`）：

```python
def test_between_in_range():
    assert is_true(simplify(val_bool(tvl_between(TVLInt.Def(5), TVLInt.Def(3), TVLInt.Def(10)))))
```

**要点**：新节点必须覆盖「正常 / 边界 / Missing 折叠」三类场景。

---

## 4. 如何添加一个新性质

性质在 `properties.py`，模式是「构造 Solver + 编译条件 + 加约束 + 判 sat/unsat」：

```python
def disjoint(a_expr, b_expr, schema):
    """a ∧ b 不可满足（互斥）。"""
    ctx = CompileContext(schema)
    a = compile_expr(a_expr, ctx)
    b = compile_expr(b_expr, ctx)
    s = Solver()
    s.add(val_bool(a), val_bool(b))
    return s.check() != sat
```

**要点**：性质 = 「把要证的反面写成约束，看是否 unsat」。`unsat` = 性质成立。

---

## 5. API 速查

| 模块 | 关键 API | 用途 |
|---|---|---|
| tvl | `tvl_gt/eq/...` `tvl_and/or/not` `tvl_add/mul/div/round` `tvl_contains/match` `tvl_date_*` | 34 节点 Z3 编码 |
| tvl | `TVLInt/Bool/Str` `str_def` `val_int/val_bool/val_str` | TVL 构造 + 解构 |
| quantifiers | `tvl_all/any/none` | 量词（E8 空数组折叠）|
| fixed_point | `parse/serialize/to_scale14_half_even` `add/sub/mul/div` | 定点参考语义（交叉验证基准）|
| calendar | `days_from_civil/civil_from_days/is_leap/days_in_month` | civil 算法 |
| field_contracts | `FieldContract/Schema` | 验证 schema |
| compiler | `CompileContext/compile_expr` | S-expression → Z3 |
| properties | `can_fire/always_denies/subsumes/equivalent/disjoint` | 性质验证 |
| resolution | `resolve` | 裁决（§9 ring/override/emergency）|

---

## 6. 如何添加一道交叉验证

交叉验证在 `replay/`，模式是「加载 erdl-vectors 冻结向量 → 用本仓参考语义重算 → 逐条比对」。

参考 `replay/crosscheck-vectors.py`（算术）或 `replay/crosscheck-calendar.py`（日历）：

```python
with open(VECTORS) as f:
    vectors = json.load(f, parse_float=str)["vectors"]
for v in vectors:
    if v["category"] != "V-ENGINE" or v["node"] not in (...):
        continue
    got = evaluate(v["expr_tree"])       # 本仓参考语义
    assert got == v["expected"]["value"]  # 逐条比对冻结答案
```

**运行**：`python replay/crosscheck-*.py`（需 `PYTHONPATH=src`）。

---

## 7. 测试约定

- 每个模块一个 `test_*.py`，覆盖「正常 / 边界 / Missing / 异常」。
- 交叉验证放 `replay/`（不是 `tests/`，因依赖 erdl-vectors 冻结向量）。
- 跑全量：`python -m pytest -q`（当前 130 全绿）。

---

## 8. 构建与发布

**三种安装方式**：

```bash
# 用户（从 PyPI，一条命令）
pip install erdl-formal

# 开发者（从源码，可编辑安装）
git clone https://github.com/OpenOBA/erdl-formal.git
cd erdl-formal
python -m pip install -e ".[dev]"

# 从源码构建分发包（wheel + sdist）
python -m pip install build
python -m build        # 产出 dist/erdl_formal-0.1.0-py3-none-any.whl + .tar.gz
```

**发布到 PyPI**：

```bash
python -m pip install twine
twine upload --repository testpypi dist/*   # 先 TestPyPI 试跑
twine upload dist/*                         # 再正式 PyPI
```

> 发布需 PyPI 账号 + API token（免费，`pypi.org/manage/account/token/` 生成，项目级作用域；token 只显示一次）。
>
> 纯 Python 项目 → 单个 `py3-none-any` 通用 wheel 全平台覆盖，无需多平台矩阵。`dist/`、`build/` 已被 `.gitignore` 忽略，产物不进 git，只上 PyPI / GitHub Releases。
