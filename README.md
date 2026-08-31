# erdl-formal

ERDL 表达内核的形式化验证器 —— 用 SMT（Z3 / cvc5）对 ERDL 规则做**静态性质证明**（never-errors / always-allows / always-denies / subsumption / equivalence / disjointness + ERDL 特有的 override-soundness / ring-respect / emergency-shortcut）。

## 定位

| 层 | 仓库 | 验证什么 | 手段 |
|---|---|---|---|
| 表达层 | **erdl-formal**（本仓）| 规则性质的**静态证明** | SMT 可满足性 / 反例合成 |
| 可信层 | erdl-vectors | 决策对象的**运行时一致性** | 跨实现逐字节对拍 |
| 表达层 | erdl | ERDL 解析与求值 | 参考实现 |

验证者独立于被验证者（同 erdl-vectors 独立于 erdl 的原则）——本仓不依赖任何 ERDL 引擎实现，只依据规范（`erdl-spec-v2.0`）编码 34 节点语义。

## 范围

- **内核**：34 节点类型化表达式树 + E1–E12 求值约束。
- **性质**：Cedar 6 性质（适应 ERDL）+ override-soundness / ring-respect / emergency-shortcut。
- **当前状态**：POC（M1）——先验证「密级比较（G3）」与「量词/三值（Phase 2）」两条规则的性质证明 + 反例回放。

## 关键设计

- **三值逻辑（E11）**：叶子折叠——比较节点将 undefined 折叠为 `false`，布尔算子（and/or/not）为两值逻辑。编码为 `TVL(τ) = Def(value) | Missing`（见 `erdl_formal/tvl.py`）。
- **schema 假设**：v2.0 无验证 schema，验证结论表述为「假设字段存在且符合类型，则规则满足性质 P」。
- **时间分层**：时间戳层（epoch_ms/days_between）可 SMT；日历层（date_add/date_part/month_last_day）规避。

## 文档

- `docs/plan.md` — 完整方案（v10）
- `docs/findings.md` — 审查意见汇总
- `docs/audit-upgrades.md` — 规范审计 + 升级建议

## 开发

```bash
python -m pip install -e ".[dev]"   # 安装依赖
pytest                               # 跑测试
```

## 许可证

MIT · © 2026 深圳市秒镜科技有限公司
