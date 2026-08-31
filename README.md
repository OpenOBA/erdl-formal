# erdl-formal

ERDL 表达内核的**形式化验证器**——用 SMT（Z3）对 ERDL 规则做**静态性质证明**：不只「测过」，而是「数学上证明不存在反例」。

> ERDL 是企业 AI Agent 的确定性规则语言（34 节点类型化表达式树 + E1–E12 求值约束）。本仓库回答一个问题：**这条规则，在**所有**输入下，会不会出错、会不会误放行、会不会该拦不拦？**

## 为什么需要它

LLM 是概率性的，规则引擎必须确定性。但「手写 if-else + 单元测试」只能证明**测过的输入**是对的。形式化验证把「确定性」从**抽样测试**升到**全量证明**——这正是 Cedar Analysis 在 AWS 内部的价值，也是强监管行业（金融/保险/政务）审计要的「恒真」证明。

## 关键特性

- **34 节点全覆盖**：取值/逻辑/比较/集合/字符串/存在量纲/量词/算术/时间/聚合，全部有 SMT 编码。
- **E1–E12 精确语义**：E2 定点小数 scale=14+half-even、E8 量词空数组折叠（反空洞真）、E11 三值逻辑（叶子折叠）、E12 tier 折叠、E10 NFC。
- **Cedar 6 性质 + ERDL 特有性质**：never-errors / always-allows / always-denies / subsumption / equivalence / disjointness + override-soundness / ring-respect / emergency-shortcut。
- **独立验证者**：只依据规范（`erdl-spec-v2.0`）编码，不依赖任何 ERDL 引擎实现——与 erdl（TS 引擎）、erdl-vectors（冻结向量）构成三重独立对拍。

## 快速上手

```python
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies

# G3 涉密访问控制：文件密级 > 操作员密级 → DENY
schema = Schema()
schema.add(FieldContract(field="file_cls", type="int"))
schema.add(FieldContract(field="op_cls", type="int"))

rule = ["gt", ["field", "file_cls"], ["field", "op_cls"]]

# 验证两条性质：
# 1) 可达 —— 字段都在时，密级更高确实能触发拦截
# 2) fail-closed —— 操作员密级缺失时，不产生误放行绕过
assert always_denies(rule, schema, premises=["file_cls", "op_cls"], missing_field="op_cls")
```

## 验证什么

| 性质 | 含义 | 来源 |
|---|---|---|
| never-errors | 求值永不产生 EvalError | Cedar |
| always-denies | 命中即拦截（含 fail-closed：字段缺失不绕过）| Cedar + E11 |
| always-allows / subsumption / equivalence / disjointness | 放行/蕴含/等价/互斥 | Cedar |
| override-soundness | override 仅 DENY→ALLOW 方向（不覆盖到更不安全态）| **ERDL 特有** |
| ring-respect | 无 override 时 ring 顺序在 DENY 方向被尊重 | **ERDL 特有** |
| emergency-shortcut | EMERGENCY_HALT 命中即短路 | **ERDL 特有** |

## 保证（Measurements, not endorsements）

不自我背书——**三重独立系统逐字节对拍一致**：

| 交叉验证 | 对象 | 结果 |
|---|---|---|
| 定点小数 | `fixed_point.py` ↔ erdl `fixed-point.js` | 逐字节一致 |
| 裁决语义 | `resolution.py` ↔ erdl `Evaluator` | 4 场景 |
| 算术向量 | ↔ erdl-vectors V-ENGINE | 7/7 |
| 日历向量 | ↔ erdl-vectors V-ENGINE | 6/6 |
| G3 反例回放 | `tvl.py` ↔ erdl 引擎 | 逐场景一致 |

## 架构

```
ERDL 规则 (S-expression)
   │
   ▼  compiler.py（符号编译器，schema 驱动字段类型 + 量词索引展开）
Z3 TVL 表达式（TVL(τ) = Def | Missing，叶子折叠）
   │
   ▼  properties.py（性质验证）
sat / unsat + 反例（回放真实引擎交叉验证）
```

## 与竞品的差异

| | Cedar Analysis | OPA/Rego | **erdl-formal** |
|---|---|---|---|
| 形式化 | ✅ Lean + SymCC | ❌ 语义即实现 | ✅ SMT |
| 决策对象 | 只有策略 ID | 无签名日志 | **富决策对象（DO）** |
| 双向 NL | 单向（NL→Cedar）| 单向 | 确定性 gloss 可锚定回译 |
| 定点小数 | ❌（无小数）| float64 丢精度 | **scale=14 精确** |

## 文档

- `docs/DELIVERY-REPORT.md` — 交付汇总（里程碑 / 34 节点矩阵 / 交叉验证 / 踩坑）
- `docs/semantics.md` — 34 节点指称语义
- `docs/tvl-encoding.md` — 三值逻辑 SMT 编码规范
- `docs/field-contracts.md` + `docs/schema-assumption.md` — 验证 schema 契约
- `docs/plan.md` / `docs/findings.md` / `docs/audit-upgrades.md` — 方案 / 审查 / 规范审计

## 开发

```bash
python -m pip install -e ".[dev]"   # 安装依赖
pytest                               # 跑测试（102 全绿）
python replay/crosscheck-vectors.py  # 与 erdl-vectors 冻结向量对拍
```

## 许可证

MIT · © 2026 深圳市秒镜科技有限公司
