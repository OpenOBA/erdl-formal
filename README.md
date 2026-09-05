# erdl-formal

ERDL 表达内核的形式化验证器 —— 用 Z3 证明规则在所有输入下的安全性

确定性有两种：测试覆盖的确定性，和数学证明的确定性。erdl-formal 提供后者。

>"erdl-formal 形式化验证了 ERDL v2.1 的表达内核与求值语义（§5、§7、附录 A），覆盖 34 节点和 E1–E12 约束。规范的其他层面（文档结构、gloss 渲染、集成模式）通过测试向量与工程验证保障。"

## 为什么是现在：LLM 有蛮力，没方向

LLM 是概率性的：同一个输入，两种回答。把企业决策交给概率分布，审计迟早会问——「这个决定，依据是什么？」

行业共识正在成形：**LLM 负责理解，规则负责裁决**——在 Agent 前面，必须有一层确定性规则引擎。但规则引擎的「确定性」通常靠单元测试背书，而测试只能证明**测过的输入**是对的。

金融、保险、政务这类强监管行业，审计只问一个问题：

> **这条规则，对所有输入都成立吗？**

抽样测试回答不了这个问题，回答只能是证明。Cedar Analysis 在 AWS 内部验证了这条路（Lean 形式化 + SMT 符号分析）；erdl-formal 对 ERDL 表达内核做同样的事——把「确定性」从**抽样测试**升到**全量证明**。

- **Cedar Analysis**：AWS 内部使用，Lean + SMT，不对外开放，只服务 AWS 自己的策略语言。
- **OPA / Rego**：无形式化语义，「实现即规范」。
- **erdl-formal**：开源、34 节点全覆盖、ERDL 特有语义（钱、时间、决策对象、双向 gloss）。

## 30 秒，看一个证明

G3 密级访问控制：文件密级 > 操作员密级 → DENY。要证明这条规则**可达**，且缺失字段**不绕过**（fail-closed）：

```python
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import always_denies

schema = Schema()
schema.add(FieldContract(field="file_cls", type="int"))
schema.add(FieldContract(field="op_cls", type="int"))

# when: file_cls > op_cls  →  DENY
rule = ["gt", ["field", "file_cls"], ["field", "op_cls"]]

# 一条断言，同时证明两条性质：
# 1) 可达 —— 字段都在时，密级更高确实触发拦截
# 2) fail-closed —— 字段缺失不绕过。这条性质取决于文档的未命中兜底决策
#    （default_decision）：兜底为 DENY 时，op_cls 缺失→守卫折叠为假→兜底仍拒绝，
#    不绕过；兜底为 ALLOW（resolution 默认）时，缺失即放行——规则 fail-open。
assert always_denies(
    rule, schema,
    premises=["file_cls", "op_cls"],
    missing_field="op_cls",
    default_decision="DENY",
)
assert not always_denies(
    rule, schema,
    premises=["file_cls", "op_cls"],
    missing_field="op_cls",
    default_decision="ALLOW",
)
```

背后没有测试用例，没有抽样。Z3 在**所有整数**的空间里搜索违反性质的输入：找到，返回**可回放的具体反例**（能丢回真实引擎复核）；找不到，UNSAT——性质对全量输入成立，证毕。

## 能证明什么

| 性质 | 含义 | 来源 |
|---|---|---|
| always-denies | 守卫可满足即拦截；配合 `default_decision` 判定字段缺失是否绕过 | Cedar + E11 |
| subsumption / equivalence / disjointness | 蕴含 / 等价 / 互斥 | Cedar |
| override-soundness | override 仅 DENY→ALLOW 方向（不覆盖到更不安全态）| **ERDL 特有** |
| ring-respect | 高环 DENY 覆盖低环 ALLOW（ring 顺序在 DENY 方向被尊重）| **ERDL 特有** |
| emergency-shortcut | EMERGENCY_HALT 命中即短路 | **ERDL 特有** |

表达式层性质（`always_denies` / `subsumes` / …）用「把反面写成约束、判 unsat」的方式证明；ERDL 特有的三条裁决层性质（`override_soundness` / `ring_respect` / `emergency_shortcut`）由 `resolution_smt.py` 把 `resolve()` 的 ring / override / priority 排序编码成 Z3 约束，**对全部规则集**判 UNSAT——不是抽样，是全量证明。任何 SAT 反例都是可回放真实引擎复核的具体规则集——证明 + 差分，双保险。

## 34/34 节点覆盖，E1–E12 语义

- **34 节点全部有 SMT 编码**：取值 / 逻辑 / 比较 / 集合 / 字符串 / 存在量纲 / 量词 / 算术 / 时间 / 聚合（比较与存在按字段类型分派：int / string / bool；`epoch_ms` 支持 date-only 与 ISO 8601 带时分秒/时区偏移）。
- 关键语义不是「大致对」，是**逐位精确**：
  - **E2** 定点小数：scale=14 + half-even——钱，不允许 `0.1 + 0.2` 式漂移；
  - **E8** 量词空数组折叠：反空洞真，`all([])` 是假不是真；
  - **E11** 三值逻辑：字段缺失在叶子处折叠为假（非 Kleene）；「缺失是否 fail-open」由文档兜底决策决定（见 `always_denies` 的 `default_decision`）；
  - **E10** NFC 归一化；**E12** 求值错误折叠为 `Missing`（tier≤2 fail-close 属运行时行为，不在内核建模）。

## 独立验证者：三重独立，逐字节对拍

验证者的可信度来自**不看被验证者的答案**。erdl-formal 只依据规范（[`erdl-language-spec`](https://github.com/OpenOBA/erdl-landing/blob/main/erdl-spec.md)）编码，零依赖任何 ERDL 引擎实现，与 [`erdl`](https://www.npmjs.com/package/@openoba/erdl)（TS 引擎）、[`erdl-vectors`](https://github.com/OpenOBA/erdl-vectors)（冻结向量）构成三重独立：

| 交叉验证 | 对象 | 结果 |
|---|---|---|
| 定点小数 | `fixed_point.py` ↔ erdl `fixed-point.js` | 逐字节一致 |
| 裁决语义 | `resolution.py` ↔ erdl `Evaluator` | 穷举 + 随机差分（`test_resolution_smt.py`）|
| 算术向量 | ↔ erdl-vectors V-ENGINE | 7/7 |
| 日历向量 | ↔ erdl-vectors V-ENGINE | 6/6 |
| G3 反例回放 | `tvl.py` ↔ erdl engine | 逐场景一致 |

**Measurements, not endorsements.** 三个独立构建的系统逐字节一致——说明规范足够精确，能支撑独立实现的精确复现。

## 与 Cedar / OPA 的差异

| 维度 | Cedar Analysis | OPA / Rego | **erdl-formal** |
|---|---|---|---|
| 形式化 | ✅ Lean + SMT（业界标杆，闭源） | ❌ 无形式化语义（实现即规范） | ✅ SMT（Z3），开源 |
| 定点小数（钱） | 小数扩展插件 | float64 丢精度 | ✅ scale=14 + half-even |
| 时间 / 日历 | — | — | ✅ UTC 日历（days_between / date_add / date_part / 月末） |
| 聚合 | — | — | ✅ aggregate（count / sum / avg / min / max） |
| 量词 | — | — | ✅ all / any / none（E8 空数组折叠） |
| 决策对象 | 策略 ID | 日志无签名 | ✅ 富 DO + 哈希链 |
| 自然语言 | 单向（NL→策略） | 单向 | ✅ 确定性 gloss 锚定回译（双向） |

差异不是「更形式化」——Cedar 的形式化栈是业界标杆。差异在**被形式化的东西**：ERDL 是为钱、时间、聚合、量词、决策对象与双向自然语言而生的企业规则内核，这些（表中 `—` 行）在 Cedar / OPA 的世界里不存在。

## 架构

```
ERDL 规则 (S-expression)
   │
   ▼  compiler.py（符号编译器：schema 驱动字段类型 + 量词索引展开）
Z3 TVL 表达式（TVL(τ) = Def | Missing，叶子折叠）
   │
   ▼  properties.py（表达式层性质验证）/ resolution.py（裁决参考模型）
     / resolution_smt.py（裁决层 SMT 全量证明）
sat / unsat + 反例（回放真实引擎交叉验证）
```

## 安装

**用户**（从 PyPI，一条命令）：

```bash
pip install erdl-formal
```

**开发者**（从源码，可编辑安装，改代码即时生效）：

```bash
git clone https://github.com/OpenOBA/erdl-formal.git
cd erdl-formal
python -m pip install -e ".[dev]"   # Python ≥3.11（3.14 开发），z3-solver ≥4.13（5.1.0 验证）
```

**从源码构建分发包**（wheel + sdist，供发布 / 离线分发）：

```bash
python -m pip install build
python -m build        # 产出 dist/erdl_formal-<version>-py3-none-any.whl + .tar.gz
```

## 快速上手

```bash
pytest                               # 全绿
python examples/verify_g3.py         # 验证 G3 密级规则（可达 + fail-closed）
python replay/crosscheck-vectors.py  # 与 erdl-vectors 冻结向量对拍
```

## 文档

- `docs/semantics.md` — 34 节点指称语义
- `docs/tvl-encoding.md` — 三值逻辑 SMT 编码规范
- `docs/field-contracts.md` — 验证 schema 契约
- `docs/DEVELOPER-GUIDE.md` — 二开指南（架构 / 加节点 / 加性质 / API / 构建发布）

> 英文版：`docs/*.en.md`

## 贡献与安全

- `CONTRIBUTING.md` — 贡献流程（先 issue 后 PR / review）
- `SECURITY.md` — 漏洞私下报，不开公开 issue
- `CHANGELOG.md` — 变更记录（Keep a Changelog）
- `CODE_OF_CONDUCT.md` / `style_guide.md`

## 许可证

Apache-2.0 · © 2026 深圳市秒镜科技有限公司 (Shenzhen Miaojing Technology Co., Ltd.)
