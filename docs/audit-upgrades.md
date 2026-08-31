# ERDL 规范审计 + 升级建议（交叉深研成果）

> 日期：2026-09-01
> 触发：Henry「继续深挖，但不要被规范约束，对规范有增益的该审计规范就升级规范」
> 关联：`erdl-formal-verification-plan-2026-08-31.md`（v10）· `erdl-formal-verification-findings-2026-08-31.md`
> 维护：OpenOBA

---

## 审计发现（6 项）

| # | 类型 | 规范位置 | 问题 | 升级建议 | 优先级 |
|---|---|---|---|---|---|
| U1 | 澄清 | §10.2 E11 | E11 表未显式列 not/and/or 对 undefined 行为 | 补「布尔算子两值」+ 核心 Expression not 无 exists 守卫的 fail-open 警示 | ✅ 已回写 2026-09-01 |
| U2 | 澄清 | §10.4(d) | aggregate 空数组返回 Int/Bool 类型不一致 | 明确 `Option<Int>` | ✅ 已回写 2026-09-01 |
| U3 | 微调 | §10.2 E11 | 「统一返回 false」与「算术→EvaluationError」措辞张力 | 改「条件折叠 false / 算术 EvaluationError」| ✅ 已回写 2026-09-01 |
| U4 | 增强 | §7 字段契约 | 缺基数上限，无法支撑量词/聚合 SMT 索引展开 | v2.1 可选 schema 子语言（已标注「〔验证缺口〕」）| v2.1 |
| U5 | 计划补 | §13 决策表 | 计划只提 Simple→core，漏决策表→core 编译 | 计划 §11.1 补「三投影面编译 = Simple + 决策表」（规范已对，计划漏）| 计划 |
| U6 | 已知缺口 | §44.1 | Grade B 分级上限向量「待版本升级增补」| formal 验证可提前覆盖 Grade B 资源上限语义 | M2 |
| U7 | 战略增益 | §15 | 「逆向回译（双向 NL）」标注 Pending | erdl-formal 的确定性 gloss（`gloss==render(树)`）可铺定回译，使「双向 NL」从 LLM 概率变可验证 | 路线 |
| U8 | 增益 | §20.3/§34 | schema 子语言（U4）应 leverage 现有法域字段映射，非从零发明 | 扩展 §20.3 字段映射机制加基数上限 | v2.1 |
| U9 | 澄清 | §14 | gloss `exists` 布尔字段特例靠 `is_*/has_*` 命名约定启发式 | 明确 is_*/has_* 为注册约定（进单一事实源）| 低 |

---

## 处置建议

- **U1/U2/U3**：澄清不改语义，**立即升级规范**（让 E11 + 聚合语义对实现者与形式化验证者无歧义）。
- **U4**：v2.1 增强，已标注，暂不动。
- **U5**：计划补（`erdl-formal` 方案 §11.1）。
- **U6**：spec 自认缺口，formal M2 提前覆盖。

## 待 Henry 拍板

1. U1/U2/U3 已回写（2026-09-01）。
2. U7/U8/U9 是否纳入路线（U7 战略级、U8 归 v2.1、U9 低优）？

## 审计进度

- ✅ 表达层 §9-§18（含 §10 内核/§11 Simple/§12 Expression/§13 决策表/§16 Grade/§17 eval_trace）→ U1-U6
- ✅ 合规层 §19-§25 → 无 spec bug，U8（schema leverage）
- ✅ 可信层 §26-§32 → 无 spec bug
- ✅ 生命周期 §33-§41 → 无 spec bug
- ✅ gloss/NL §14/§15 → U7/U9

**整体结论**：规范基础扎实，表达层/合规层/可信层/生命周期全链路清晰；主要增益点是 U1-U3（已回写）+ U7（双向 NL moat）+ U8（schema leverage）。

---

_审计持续进行中，后续发现追加此处。_
