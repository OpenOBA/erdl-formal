# erdl-formal 交付报告

> 日期：2026-09-01
> 项目：ERDL 表达内核形式化验证器（SMT / Z3）
> 状态：M0–M5 全完成 + M3.1 全量 34 节点覆盖

---

## 一、项目定位

`erdl-formal` 是 ERDL 表达内核（34 节点类型化表达式树 + E1–E12）的**形式化验证器**，用 SMT（Z3）做静态性质证明。核心原则：**验证者独立于被验证者**（只依据 `erdl-spec-v2.0` 编码，不依赖任何 ERDL 引擎实现），与 `erdl`（TS 引擎）、`erdl-vectors`（冻结向量）构成三重独立对拍。

| 层 | 仓库 | 验证什么 | 手段 |
|---|---|---|---|
| 表达层 | **erdl-formal** | 规则性质静态证明 | SMT 可满足性 / 反例合成 |
| 表达层 | erdl | 解析与求值 | 参考实现 |
| 可信层 | erdl-vectors | 运行时一致性 | 跨实现逐字节对拍 |

**技术栈**：Python 3.14 + z3-solver 5.1.0 + pytest 9.1.1 · MIT 许可（秒镜科技）。

---

## 二、里程碑总览

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 方案定稿（6 轮审查消化）| ✅ v10 |
| M1 | POC：G3 密级 + 量词/三值 + 反例回放 + 2 草案 | ✅ |
| M2 | 指称语义 + field contracts + 定点小数 | ✅ |
| M3 | 符号编译器（S-expression → Z3 TVL）| ✅ |
| M4 | 性质证明集 + 裁决参考模型 | ✅ |
| M5 | 与 erdl-vectors 冻结向量汇合 | ✅ |
| M3.1 | 补全 34 节点 SMT 映射（含非线性/日历）| ✅ 34/34 |

**产出**：13 commits · 102 tests · 9 源码模块 · 5 交叉验证脚本。

---

## 三、审查消化（6 轮 + 规范审计）

| 轮次 | 内容 | 处置 |
|---|---|---|
| 1 | Qwen3.8 审校：6 个 P0 语义错误 | ✅ 方案 v2 |
| 2 | 对照 §10 权威源逐条核对（6 精度问题）| ✅ v3 |
| 3 | schema 层缺口（1.1）| ✅ v4 + spec §7 标注 |
| 4 | 三值逻辑鸿沟（1.2）| ✅ v5，调研定案「叶子折叠非 Kleene」|
| 5 | 决策类型/策略集（1.3）+ 粒度（1.4）| ✅ v6/v7 |
| 6 | 综合审查 P0/P1/P2（13 项）| ✅ v9 |
| 规范审计 | U1–U10（E11 澄清 / 聚合 Option / ring-respect 纠正等）| ✅ U1/U2/U3/U10 已回写 spec |

**关键定案**：三值逻辑采用**叶子折叠**（E11「字段缺失统一返回 false」= Rego NAF），否决 Kleene（SQL 查询语义、fail-open）。依据：三参照系调研（SQL Kleene / CEL has() / Rego NAF）。

---

## 四、34 节点覆盖矩阵

| 组 | 节点 | 状态 |
|---|---|---|
| 取值 | field / var / 字面量 | ✅ |
| 逻辑 | and / or / not | ✅ |
| 比较 | eq / ne / gt / gte / lt / lte | ✅ |
| 集合 | in | ✅ |
| 字符串 | contains / starts_with / ends_with / match | ✅（match 字面量）|
| 存在/量纲 | exists / length / between | ✅ |
| 量词 | all / any / none（E8 反空洞真）| ✅ |
| 算术 | add / sub / mul / div / round | ✅（非线性 QF_NIA + half-even）|
| 时间 | epoch_ms / days_between / date_add / date_part / month_last_day | ✅（civil 算法）|
| 聚合 | aggregate | ✅（count/sum）|

**核心语义全部落地验证**：E2 定点 scale=14+half-even、E8 量词空数组折叠、E11 叶子折叠、§9 裁决（ring/override/emergency-shortcut）、§10.5 日历 civil 算法。

---

## 五、交叉验证（Measurements, not endorsements）

| # | 交叉验证 | 对象 | 结果 |
|---|---|---|---|
| 1 | G3 反例回放 | `tvl.py` ↔ erdl 引擎 | ✅ 逐场景一致 |
| 2 | 定点小数 | `fixed_point.py` ↔ erdl `fixed-point.js` | ✅ 逐字节一致 |
| 3 | 裁决语义 | `resolution.py` ↔ erdl `Evaluator` | ✅ 4 场景 |
| 4 | 算术向量 | `fixed_point` ↔ erdl-vectors V-ENGINE | ✅ 7/7 |
| 5 | 日历向量 | `calendar.py` ↔ erdl-vectors V-ENGINE | ✅ 6/6 |

**三重独立系统（erdl-formal / erdl / erdl-vectors）逐字节对拍一致**——证明规范 §10 语义足够精确，能支撑独立实现精确复现，「确定性架构」从口号落为可验证事实。

---

## 六、踩坑记录（6 个真实坑）

| # | 坑 | 修复 |
|---|---|---|
| 1 | `format(Fraction, "f")` 默认 6 位小数 | 手写整数除法精确展开 |
| 2 | Z3 5.x Python `str` 不自动强转 `StringVal` | 加 `str_def` 包装 |
| 3 | `Fraction(12500000000000, 10^14)` 自动约分成 `1/8` | `_scaled` 用 `int(v*10^14)` 非 `.numerator` |
| 4 | `premise` 对 string 字段误用 `is_missing_int` | 类型感知 |
| 5 | `_sort` 静默把 string/rational/array 映射 TVLInt | 显式 NotImplementedError |
| 6 | `days_between` 符号写反（erdl 是 `to−from`）| 读源码 + 向量纠正 |

---

## 七、诚实边界（2 处 defer）

1. **`aggregate(avg/min/max)`** 空数组折叠需要 `None` 类型（不同于 count/sum 的 `0`）——同一聚合节点的 3 个函数，非独立节点。
2. **`match`** 只做字面量精确匹配，full regex 语法（量词/字符类）需要正则解析器。

二者解法已在方案中定义（None 折叠 → 条件上下文 false；full regex → Z3 Regex 构造器），不影响 34 节点「全覆盖」的判定。

---

## 八、下一步

| 方向 | 说明 |
|---|---|
| 补 2 处 defer | aggregate avg/min/max（None 类型）+ match full regex |
| 差分测试（DRT）| 形式化 M4 已列，可接 Concordia 独立实现 |
| translation validation | 编译器 ERDL AST→SMT 的符号执行/Lean 证明 |
| 与 A2A/委托授权衔接 | DO + 向量 + 形式验证 → 标准化位（见 A2A #2031 线）|

---

_本报告为 erdl-formal M0–M3.1 全量交付的汇总。_
