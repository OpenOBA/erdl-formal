# §7.1 义务 → 属性 映射表

> 维护者：OpenOBA · 生成于 2026-09-07 · 范围：`src/erdl_formal/resolution.py`（参考实现）+ `resolution_smt.py`（Z3 证明）

本文件把 ERDL SPEC §7.1（优先级与冲突裁决）和 §7.0.2（求值算法）的每一条规范性义务，映射到证明或锚定它的属性。这正是 ANP2 Network 要求的「机械义务清单」：一条没有映射属性的义务，会在评审者点名之前就以**缺口**的形式显现在这里。

## 映射

| SPEC 义务 | 属性（erdl-formal） | 类别 | 状态 |
|---|---|---|---|
| §7.1.1 — 按 `priority` 升序排序 | `sorted_premise()` + 差分穷举 | 输入契约（排序）| ✅ 已锚定 |
| §7.1.2 — 同 priority 时带 `override` 者优先 | `sorted_premise()` + 差分穷举 | 输入契约（排序）| ✅ 已锚定 |
| §7.1.3 — `override` 枚举 `critical` > `high` > `normal` > `low` | `override_rank()` + 差分穷举 | 输入契约（排序）| ✅ 已锚定 |
| §7.1.4 — 同 priority + 同 override → 定义顺序 | `sorted_premise()`（数组序）| 输入契约（排序）| ✅ 已锚定 |
| §7.1.5a — `override` 仅 DENY→ALLOW（不得越权到更不安全状态）| `override_soundness` | 安全（禁止型）| ✅ 已证明 |
| §7.1.5b — `critical`/`high` 跨 ring 生效：高 ring 的 override ALLOW 覆盖低 ring DENY | *无* | 能力（可达性）| ⚠️ 缺口 — 见下 |
| §7.1.6 — catch-all 不得改写显式条件规则建立的决策 | `catch_all_inert_when_explicit` | 安全（禁止型）| ✅ 已证明 + 变异测试 |
| §7.1.6a（量词 1）— catch-all 的 `then` 对最终决策无关 | `catch_all_then_irrelevant_when_explicit` | 安全，基于决策观察量 | ✅ 已证明 + 变异测试 |
| §7.1.6b（量词 2）— catch-all 的 `override` 对最终决策无关 | `catch_all_override_irrelevant_when_explicit` | 安全，基于决策观察量 | ✅ 已证明 + 变异测试 |
| §7.0.2 — ring 顺序 0→3 | `ring_respect` | 安全（DENY 方向）| ✅ 已证明 |
| §7.0.2 — EMERGENCY_HALT 命中即短路 | `emergency_shortcut` | 安全（终结）| ✅ 已证明 |
| §7.0.2 — WORKFLOW 命中即短路进入状态机 | `workflow_shortcut` | 安全（终结）| ✅ 已证明 |

## 类别说明

- **输入契约（排序）** — 排序规则决定的是*处理顺序*，而非需要证明的后置条件。`sorted_premise()` 把它们编码为 fold 的输入契约，穷举差分（`test_reformulation_matches_reference_exhaustive`）把这个编码锚定到手写 `resolution.resolve`。这些是机械规则，误读会在「一眼错」层面被抓出，不携带 §7.1.6 那种跨规则的精妙语义。
- **安全（禁止型）** — 否定义务（「MUST NOT …」）；以坏项 UNSAT 证明。
- **能力（可达性）** — 肯定义务（「may …」）；以证明该状态可达（非空真）来证明，而非 UNSAT。

## 缺口

### ⚠️ §7.1.5b — 高 ring 的 override ALLOW 覆盖低 ring DENY

`override_soundness` 只证明了 §7.1.5 的*否定*半边（同 ring 的 override DENY 不会把 ALLOW 收紧为 DENY）。它**没有**证明*肯定*半边：`critical`/`high` 的 override ALLOW 确实能**不比较 ring 地**覆盖低 ring 的 DENY/ROLLBACK/QUARANTINE。在 fold 里这是 `allow_relax` 分支（`dec == ALLOW & enables & has & is_restrictive(fin)`）。

这是一条**能力**，应以「跨 ring 放松可达」的非空真证明来关闭，而非新增 UNSAT 属性。记为跟进项；不是正确性缺陷（该能力已被差分穷举所覆盖）。

### 排序规则（§7.1.1–4）无独立 UNSAT 属性

排序规则被建模为 fold 的输入契约，而非被证明的后置条件。它们由针对手写参考实现的穷举差分所锚定。若参考实现与 fold 共享了同一排序规则的误读，则穷举与任何属性都无法抓到。实践中这些规则是机械的（数值升序 / 固定枚举序 / 稳定定义序），其误读不属于 §7.1.6 那种精妙的跨规则缺陷；*独立性*缺口真实但有限，而 §7.1 真正的独立锚定仍依赖第三方 runner（见 `erdl-vectors`）。

## 本映射表的产出方式（机械提取）

本表不是精选摘要，而是把 SPEC §7.1 / §7.0.2 **逐句投影**到属性清单（ANP2 Network：「逐句提取是可信输入，不是目标」）。具体：

1. §7.1 的每条*规范性*条款（§7.1.1–6）与 §7.0.2 的每条短路条款各占一行。
2. 携带多个合取项或量词的条款**拆开**——每个量词/合取项一行（§7.1.5 → 5a 否定 / 5b 肯定；§7.1.6 → 6a `then` / 6b `override`）。正是拆解把 6b 暴露为之前未映射的义务。
3. 一行**关闭**当且仅当存在一个具名属性：其 docstring 引用该义务、且其测试断言了它（已证明 + 变异测试）。无对应属性的行即为**缺口**，列于上方「缺口」一节。

提取本身是可信输入（由人读 SPEC）；*目标*是得到的覆盖边界——每条义务要么关闭、要么显式为缺口，评审者永远不必手工发现一条未映射的义务。
