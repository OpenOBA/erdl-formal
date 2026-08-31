# ERDL 形式化验证方案（POC 先行 · v2 修订）

> 维护者：OpenOBA
> 日期：2026-08-31 · 修订：v10（v2~v9 见前；v10=对照 erdl-spec 全量交叉深研，补 Simple 编译层/within-rate/fn/向量计数）
> 审校意见：`deliverables/erdl-formal-verification-plan-review-2026-08-31.md`
> 关联：`docs/research/erdl-feasibility-strengthening-2026-08-31.md` · `competitive-landscape-2026-08-31.md`

---

## 0. 定位与目标

**定位**：形式化验证 = OpenOBA 技术体系「验证层」新节点，与 `erdl-vectors` 平行、独立于 `erdl`。

**目标**：把 ERDL 从「可执行规约」（向量 = 抽样测试）升到「证明」（定理 = 全量保证）——「确定性求值」从**宣称**变**可验证事实**。

**一句话**：补上 Cedar 有的「可证明」，保住 Cedar 没有的「LLM 友好 + 富决策对象」。

---

## 1. 架构决策

| 项 | 决策 |
|---|---|
| 项目归属 | **独立项目** `erdl-formal`（验证者独立于被验证者，避免循环论证）|
| 层次 | 验证层（与 erdl-vectors 平行）|
| 开源策略 | 证明层开放（MIT）；引擎层保留 BSL 1.1 |
| 命名 | `erdl-formal`；成熟后可拆 `erdl-spec`(Lean) + `erdl-analysis`(SMT) |

---

## 2. 技术路径（5 步 · v2 修订顺序）

> v2 修正：schema 地面化是可判定性**前提**，前置到编译器之前；补多规则语义 + 编译器可靠性。

| 步 | 动作 | 产出 | 对标 Cedar |
|---|---|---|---|
| 1 | **指称语义**：34 节点 + E1–E12 denotational semantics | 形式规范 | cedar-lean |
| 2 | **schema 契约 + 地面化**：field contracts 声明集合基数上限 → 有限宇宙/索引展开（**可判定性前提，先于性质验证**）| 有界模型 | Cedar schema |
| 3 | **符号编译器**：ERDL → SMT-LIB（含三值逻辑抬升 + tier 折叠编码）| 工具 | cedar-policy-symcc |
| 4 | **验证性质**：表达式级 + 策略集级 | 性质清单 | Cedar Analysis |
| 5 | **双保险**：反例回放 + 差分测试 + 编译器 translation validation | 可信 | DRT |

**性质清单（v6：Cedar 6 性质作基座 + ERDL 特有性质扩展）**：

- **Cedar 基座（适应布尔决策子集）**：never-errors / always-allows / always-denies / subsumption / equivalence / disjointness + shadowed/conflict + reachability + redundancy。
- **ERDL 特有性质（v6 补，见下）**：override-soundness / ring-respect / emergency-shortcut。

#### 决策类型 → 布尔验证状态映射（13 种 → 3 类）

> Cedar 只有 permit/forbid 两态；ERDL 有 13 决策类型（§27.5 权威枚举）。验证前必须把决策映射到布尔/中间态。

| 类别 | 决策类型 | 布尔验证状态 |
|---|---|---|
| 拦截性（blocking）| DENY · EMERGENCY_HALT · ROLLBACK · QUARANTINE | `false`（阻断）|
| 放行（allow）| ALLOW · CORRECT · NOTIFY · GUIDE | `true`（放行）|
| 中间态（intermediate）| REQUEST_HUMAN · ESCALATE · DELEGATE · DEFER · WORKFLOW | 单独建模（非 true/false）|

**「触发」vs「拦截/放行」的三层区分（回应 REQUEST_HUMAN 之问）**：
1. **触发（fired）**：规则 `when` 为真且按解析顺序（priority→override→ring）成为 applied rule——REQUEST_HUMAN 规则命中 = **触发**。
2. **拦截（blocked）**：最终决策 ∈ 拦截性 → `false`。
3. **放行（allowed）**：最终决策 ∈ 放行 → `true`。
4. **人工介入（human）**：最终决策 ∈ 中间态 → 单独归类，不并入 true/false。

故「恒触发」对 REQUEST_HUMAN 成立（它触发了），但「恒拦截/恒放行」不适用于它（它是中间态）。

#### ERDL 特有性质（v6）

| 性质 | 规范依据 | 验证目标 |
|---|---|---|
| **override-soundness** | §9 优先级规则 5：override 仅 DENY→ALLOW 方向（不得覆盖到更不安全状态）| 不存在违反方向的 override 规则对 |
| **ring-respect** | ring 0内核/1恢复/2审批/3建议（§11 规则字段）| 低 ring（内核）拦截不被高 ring（建议）放行覆盖 |
| **emergency-shortcut** | EMERGENCY_HALT = 无条件终止系统（§10.6）；硬约束「违反即被拦截」（§6.1 分层规则注入）| EMERGENCY_HALT 命中时其他规则决策无效（控制流短路）|

**v2 补两块**：① 多规则/策略集语义（subsumption/conflict 是策略集性质，非单表达式树）；② 符号编译器 translation validation（差分测试替代不了编译器自身的可靠性证明）。

---

## 3. 34 节点 SMT 映射

| 组 | SMT 映射（v5 核对 §10 + E11/E12 后）|
|---|---|
| 取值 3 | 未解释常量 / schema 类型常量；**E11 哨兵 → ADT `TVL(τ)=Def(value) | Missing`**（见下「三值逻辑编码」）|
| 逻辑 3 | **两值**（叶子已折叠为 Def(true/false)，undefined 不传播到布尔层，见下）|
| 比较 6 | 等式 + 序（数→QF_LIA 线性 / QF_NRA 非线性）；**任一操作数 Missing → Def(false)** |
| 集合 1 | cvc5 sets / 有限集合 |
| 字符串 4 | **值 NFC 解析层规范化**（信任假设，不可公理化）；**算子编码**：contains/starts_with/ends_with → 字符串谓词，**match/regex → POC 避开**（正则受限）|
| 存在/量纲 3 | 有界基数；length=Unicode 码点；between=闭区间 |
| 量词 3 | **field contracts 基数上限 → 索引展开**（all/any/none = 0..N-1 合取/析取；**E8 三量词空数组一律 false 显式编码**）|
| 算术 5 | **中间高精度有界有理数（128 位），仅输出节点 scale=14 + half-even 舍入**；线性→QF_LIA / 变量×变量→QF_NRA/QF_BV |
| 时间 5 | 绝对时间戳（整数）；**全 UTC 求值**（§10.5 确认，引擎转 UTC 注入 as_of，核外无时区）|
| 聚合 1 | **5 函数（count/sum/avg/min/max）**；空数组折叠：count/sum→0、avg/min/max→false（禁 Infinity/NaN）|

**v3 关键修正（对照 §10 权威源）**：
1. scale=14 定点有理数只有**线性片段**（加减/比较/乘常数）映射 QF_LIA；**变量×变量是非线性**（QF_NRA 或位向量 QF_BV）。**更关键**：§10.4(b) 规定中间计算用**高精度有界有理数（128 位分子/分母）**，仅**输出节点**按 scale=14 + half-even 舍入——SMT 建模的是「中间有理数算术 + 输出舍入」，不是全程 scale=14。
2. NFC 是 Unicode 组合/分解算法，**string theory 无法公理化**——字面量解析层规范化、context 求值前预规范化，SMT 层列为信任假设（§10.3 字面量规范 + E10）。
3. **E4 同时界树与数组**：Grade A 树深≤6/节点≤64/**数组≤10000**——不是「只界树大小」。但**具体数组长度是运行时值**，SMT 仍需 field contracts 声明具体基数后索引展开（语言层契约扩展）。
4. **E11 三值逻辑编码（v5 完整定义，见下「三值逻辑编码」）**；E12 tier 折叠编码全表见下。
5. **E8 是三量词全 false**：`all([])`/`any([])`/`none([])` 一律 false（`all`/`none` 为刻意安全偏离反空洞真，`any` 为标准 false）——计划原只写 `all([])`，不完整。
6. **资源上限分级 A/B/C**：Grade A（tier 0–2，安全底线）/ Grade B（业务合规，树深≤10/节点≤256/算术深度≤4/量词≤2 层）/ Grade C（fn 委派）。**POC 先 Grade A**（最受限、安全关键），再扩展 Grade B。

#### 三值逻辑编码（E11 + E12 + §11.4 完整定义）

> 回应发现 1.2：方案原「抬升编码」确不完备，但**规范的模型是「叶子折叠」，不是 Kleene 传播**——补全如下，不以 Kleene 真值表替代。

1. **哨兵编码**：`undefined` 用 ADT `TVL(τ) = Def(value: τ) | Missing`（`Missing` 即 is_defined=false）编码。
2. **叶子折叠（E11「字段缺失统一返回 false」）**：
   - 比较节点（eq/ne/gt/gte/lt/lte）任一操作数 Missing → 结果 `Def(false)`；
   - 算术节点（add/sub/mul/div/round）任一操作数 Missing → `EvalError`（E11 表「返回 false（条件）或 EvaluationError（算术表达式）」）；
   - 布尔运算因此是**两值**：and/or/not 只接收已折叠的 `Def(true/false)`，undefined 不传播到布尔层——**故无需 Kleene 真值表**（发现 1.2 的「false AND undefined=false」Kleene 表与规范「统一折叠」模型不同，规范模型下 AND 根本看不到 undefined）。
3. **E12 tier 折叠**：`EvalError` → tier≤2 / Guard 缺省 fail-close（DENY）；tier 3-5 折叠为 false。
4. **not 的对偶（§11.4 编译层保障）**：`not(field==x)` MUST 编译为 `exists(field) AND not(field==x)`，避免「缺失折叠 false → not(false)=true」的误放行。这是**编译层 exists 守卫**，非运行时三值传播。

#### 34 节点逐节点 SMT 编码模板（v7）

> 回应发现 1.4：§3 组级映射粒度不足，下沉到 34 语义节点。取值组 field/var/字面量编码不同，须分别给。

| 节点 | SMT 编码模板 | 备注 |
|---|---|---|
| **取值（3）** | | |
| field | `UF_field(ctx): Ctx → σ` 未解释函数 | schema 约束 σ；字段路径承重（冻结 FREEZE-1）|
| var | 自由变量 `v: σ` | `$` / `$.path`；上下文约束 |
| 字面量 | SMT 常量 `c: σ` | 定点小数字符串 / NFC 字符串 / bool |
| **逻辑（3）** | | |
| and / or / not | `∧` / `∨` / `¬` | 两值（叶子已折叠，见「三值逻辑编码」）|
| **比较（6）** | | |
| eq / ne | `=` / `≠` | 类型感知（数 QF_LIA / 串 str.=）|
| gt / gte / lt / lte | `>` `≥` `<` `≤` | 数 QF_LIA / 串 str.<（lexicographic）|
| **集合（1）** | | |
| in | `member(x, S)` | cvc5 sets 理论 |
| **字符串（4）** | | |
| contains | `str.contains(s, t)` | |
| starts_with | `str.prefixof(t, s)` | |
| ends_with | `str.suffixof(t, s)` | |
| match | — | 正则受限，POC 规避 |
| **存在/量纲（3）** | | |
| exists | `f ≠ Missing` | 哨兵判定（E11）|
| length | `str.len(s)` | Unicode 码点（⚠ 与 UTF-16 length 差异）|
| between | `a ≤ x ≤ b` | 闭区间 |
| **量词（3）** | | |
| all / any / none | `∧ᵢ / ∨ᵢ / ¬∃ᵢ`（0≤i<N）| field contracts 基数 N 索引展开；空数组→false（E8）|
| **算术（5）** | | |
| add / sub | QF_LIA 线性 | 中间高精度有理数 |
| mul | QF_LIA（乘常数）/ QF_NRA（变量×变量）| |
| div | 有理数除法（分子/分母）| 输出 scale=14 + half-even |
| round | 单独公理化（half-even 不连续）| |
| **时间（5）** | | |
| epoch_ms | 整数常量 | UTC |
| days_between | `floor((t1−t2)/86400000)` | UTC，floor 向下取整 |
| date_part / date_add / month_last_day | — | 日历语义（UTC+闰年+月末回退），SMT 难建模，POC 规避 |
| **聚合（1）** | | |
| aggregate | count/sum/avg/min/max 有界求和 | 空数组折叠（count/sum→0，avg/min/max→false）|

**诚实边界**：时间节点日历层（date_part/date_add/month_last_day）无法纯 SMT 编码——跨实现一致性靠 §10.5 UTC 语义 + 双实现生成向量（V-ENGINE 时间 20 条边界/异常），不靠 SMT。这印证 POC 选题避开时间节点。

#### 时间节点分层验证策略（v8）

> 回应 Henry 追问：时间不是「无解」，是「分层验证」——时区已由引擎转 UTC（§10.5），求值器只碰 epoch_ms 整数。

| 层 | 节点 | 编码 | 策略 |
|---|---|---|---|
| 时间戳层 | epoch_ms / days_between | 整数常量 / `floor((t1−t2)/86400000)` | **全量 SMT**（QF_LIA，trivial）|
| 日历层 | date_part / date_add / month_last_day | civil 算法（Hinnant days_from_civil / civil_from_days + Zeller day_of_week）| **公理化 + 差分测试** |

- **路线 A（规范已选）**：§10.5 已强制日历边界（月末回退+闰年）走**双实现生成向量**（§48.2）首批比对——跨实现一致性靠对拍，不靠 SMT。
- **路线 B（形式化补强）**：格里高利历 civil 算法是确定性整数函数，可用 div/mod 在 QF_LIA 编码，实现日历层全量证明——非平凡库，放 M2/M3。
- **POC 落地**：只用时间戳层（epoch_ms/days_between），即能验证 F6「24h 累计金额超阈值」等反拆分洗钱规则；日历层规则（按月结算/工作日路由/月末截止）留 M2/M3。
- **可选 M4**：合规 niche 要求时间日历全量证明时，再编码 civil 算法。

---

## 4. POC 设计（v9 两阶段）

**目标**：证明 ERDL 形式化验证可行 + 证明三值逻辑/量词编码可行（核心价值），产出可复现 demo。

**两阶段**：
- **Phase 1（2 天）**：G3「涉密访问控制」（密级序→整数，编码最简单）验证基本流程（规则→SMT 编码→性质证明→反例）。
- **Phase 2（3–5 天）**：加一个含**量词 all** 或**三值逻辑 AND** 的规则（如「所有审批人均已批准 → ALLOW」，测空数组 false 折叠 + 索引展开），验证量词/空值传播编码。

**工具**：Z3 Python API（POC 不变）；完整版换 cvc5（sets 理论，Cedar 同款）。

**步骤**（每阶段）：
1. 取规则 `when` 表达式（34 节点树），手写 Z3 编码（含三值折叠 + Option<Int> 聚合）。
2. 证明性质（带「字段存在且符合 schema」前提）。
3. 生成反例（Phase 1 首选「字段缺失→空值→不触发」；Phase 2 测「空数组 false 折叠」）。
4. 反例回放进真实 erdl 求值器验证一致（自动化 harness，P0-2 ②）。

**成功标准（量化）**：
- 至少 2 条不同语义规则在 Z3 完成性质证明；
- 至少 1 个反例在真实求值器复现且决策一致；
- 产出《schema 假设前提设计草案》；
- 产出《三值逻辑 SMT 编码规范（草案）》。

**工期**：**5–8 天**（含缓冲）。

---

## 5. 里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 方案定稿 | 本文 v2 |
| M1 | POC：1 策略 SMT 证明 + 反例 demo（3-5 天）| 待做 |
| M2 | 指称语义 + field contracts 契约定稿 | 待做 |
| M3 | 符号编译器（34 节点全映射 + 三值抬升）| 待做 |
| M4 | 性质证明集 + 反例回放 + 差分测试 + translation validation | 待做 |
| M5 | 与 erdl-vectors 汇合 | 待做 |

---

## 6. 风险与诚实边界（v2 补 4 条）

1. **工作量非线性**：Cedar 每加一个语言特性要 4–8 人天补证明；34 节点全量形式化是数月量级。
2. **字符串 NFC + 时间 + 量词**是硬骨头，POC 先避开或简化。
3. **定理 ≠ 实现正确**：证明的是语义规约，引擎是否按语义实现仍需差分测试兜底。
4. **本方案是验证者**：不保证 Action Guard 运行时行为（架构单路径，见 AST09 #56 三层边界）。
5. **（v2 补）编译器可靠性缺口**：有 bug 的编译器会产出「对错误语义的证明」→ 需 translation validation。
6. **（v2 补）schema 信任边界**：证明只在 schema 下成立，生产 context 违约即失效 → 需运行时校验兜底。
7. **（v2 补）求解器不终止**：字符串/量词片段可能不收敛 → 需可分析性分级。
8. **（v2 补）spec 变更须重生成全部证明**。

---

## 7. 示例库（高价值行业选题池 · v2 修订 17 条）

> POC 只选 1–2 条启动；示例覆盖金融/保险/政务强监管场景，证明形式化验证的商业价值。
> **v2 前提化**：每条「恒触发/恒拒绝」性质都必须加前提「字段存在且符合 schema」——否则字段缺失→空值→不触发，反例直接成立。

### 7.1 金融（7 条）

| # | 规则（when → then）| 要验证的性质 | 价值 |
|---|---|---|---|
| F1 | 交易金额 > 50,000 → REQUEST_HUMAN(大额交易报告) | 恒触发（字段符合 schema 前提下无绕过）| 反洗钱 AML 合规（示意阈值：现金 5 万 / 对公转账 200 万）|
| F2 | 转账金额 > 可用余额 → DENY | 恒拒绝（无透支通过）| 支付风控 / 防透支 |
| F3 | 交易对手 ∈ 关联方 ∧ 金额 > 1,000,000 → REQUEST_HUMAN | 恒审批 | 关联交易内控 |
| F4 | 风险等级 = 高 ∧ 尽调状态 ≠ 完成 → DENY | 恒拒绝 | KYC 合规 |
| F5 | 跨境 ∧ 金额 > 限额 → REQUEST_HUMAN(外管申报) | 恒申报 | 跨境支付合规 |
| F6 | 24h 内累计交易金额 > 阈值 → REQUEST_HUMAN(可疑报告) | 恒审查（聚合 + 时间窗，AML 最经典）| 反拆分洗钱 |
| F7 | 交易对手 ∈ 制裁名单 → DENY | 恒拒绝（合规价值最高的硬阻断）| 制裁合规 |

### 7.2 保险（5 条）

| # | 规则（when → then）| 要验证的性质 | 价值 |
|---|---|---|---|
| I1 | 保单期内累计理赔 > 保额 → DENY | 恒拒绝（超额理赔必拒；行业实为封顶，v2 改累计口径）| 核赔风控 |
| I2 | 职业 ∈ 高危 ∧ 保额 > 5,000,000 → REQUEST_HUMAN(人工核保) | 恒核保 | 核保合规 |
| I3 | 30 天内理赔次数 > 3 → REQUEST_HUMAN(欺诈审查) | 恒审查 | 反欺诈 |
| I4 | 保单生效天数 < 等待期 → DENY | 恒拒绝 | 等待期合规 |
| I5 | 保单贷款金额 > 现金价值 × 80% → DENY | 恒拒绝（含乘法，测非线性算术）| 保单贷款风控 |

### 7.3 政务（5 条）

| # | 规则（when → then）| 要验证的性质 | 价值 |
|---|---|---|---|
| G1 | 采购金额 > 1,000,000 → REQUEST_HUMAN(上级审批) | 恒审批 | 分级审批 |
| G2 | 数据等级 = 个人隐私 ∧ 授权 = 无 → DENY | 恒拒绝 | 隐私保护 |
| G3 | 文件密级 > 操作员密级 → DENY | 恒拒绝（越密级不可达；密级序→整数，编码最简单，**POC 首选**）| 涉密管理 |
| G4 | 采购方式 = 单一来源 ∧ 金额 > 限额 → DENY(须公开招标) | 恒拒绝 | 政府采购合规 |
| G5 | 同一主体同时为申请人与审批人 → DENY | 恒拒绝（**职责分离，形式验证最招牌性质**）| 内控 / 分权制衡 |

### 7.4 形式化验证对高价值行业的意义

- 金融 / 保险 / 政务是**强监管**行业，合规规则必须**可证明**——「数学上不存在绕过」，不是「测过了」。
- 监管审计（人行 / 银保监 / 审计署）要的是「恒真」**证明**，不是抽样测试通过。
- 这是 ERDL 形式化验证 vs 现有「手写 if-else + 测试」的本质差异，也是 Cedar Analysis 在 AWS 内部的价值。

---

## 8. 竞品借鉴（Cedar 验证栈 / OPA 审计）

### 8.1 Cedar 验证栈（主借鉴对象，OOPSLA'24 + SymCert FMCAD'26）

| Cedar 技法 | 对 ERDL 的启示 | 动作 |
|---|---|---|
| **SMT 理论栈 = UF + ADT + Strings + cvc5 sets + 线性整数算术**（非单纯 QF_LRA）| 映射要细化：field→未解释函数 UF、context/record→代数数据类型 ADT、in→sets、数→QF_LIA、字符串→string theory | 更新 §3 映射 |
| **求解器 cvc5**（私有 sets 理论）| ERDL 有 `in`（集合），完整版应选 **cvc5** 而非 Z3 | POC 用 Z3（避开集合）；完整版换 cvc5 |
| **6 性质**：never-errors / always-allows / always-denies / subsumption / equivalence / **disjointness** | 补 **disjointness**（两规则互斥）；cedar-lean-cli 另有 shadowed/conflict/redundancy 检测 | 更新性质清单 |
| **footprint 地面化**：一阶量词→有限 ground 断言 | 同一原理 = 我们「field contracts 基数→索引展开」；ERDL `in` 是**扁平集合**（§10 确认），无实体层级，比 Cedar 简单 | 守住「扁平集合」简化 |
| **SymCert**：验证 SMT 分析 sound/complete 的框架 | = Qwen3.8 提的 translation validation | 补进双保险 |
| **DRT + 反例合成**（Rust 实现 vs Lean 模型）| 反例必须回放真实求值器 | 已对齐 |
| **表达力税 4–8 人天/特性** | 印证「工作量非线性」；34 节点全量 = 数月 | 风险已列 |

### 8.2 OPA 审计（借鉴 + 反证）

| OPA 技法 | 借鉴 | 动作 |
|---|---|---|
| Decision Logs 结构（decision_id/input/result/metrics）| 事件结构可抄 | 但须补 OPA 缺的**哈希/签名**——正是我们 DO 已做的 |
| `nondeterministic` 回放字段 | 环境输入显式化（as_of/temporal_state 已显式进 DO，对齐 E1）| 已对齐 |
| 反证：无形式化语义（Brown 2024 逆向工程）| 印证「规范先行」正确，我们 spec-first | — |
| 反证：内置函数逃生舱（http.send/time.now_ns）| 印证 E1「纯函数、禁时钟」纪律 | — |

### 8.3 三个「竞品有洞、我们可占」的 moat 落点
1. **富决策对象**（Cedar 只有策略 ID）——已是我们的差异化。
2. **双向 NL 闭环**（Cedar/OPA 皆单向）——我们的空位。
3. **跨实现可验证证据链**（OPA 无签名、Cedar 决策薄）——我们的 DO + 向量。

---

## 9. 关键缺口：schema 层缺失（验证根基）

> **权威标注**：本缺口的 ground truth 已标注在规范 §7「字段契约」小节（`erdl-spec-v2.0.md` 已加「〔验证缺口 · 2026-08-31 · erdl-formal〕」注）。本节只陈述其对 POC 的**验证含义**，不再重复规范内容。

### 9.1 缺口本质（详见 spec 标注）

ERDL v2.0 采用「预置类型 + 自由字段」：context 字段完全自由（§10.2「字段缺失是常态」）。「字段契约 `EntityFieldContract`」定位是规则生产约束源，**缺「集合基数上限」**，无法支撑量词/聚合的 SMT 索引展开。

### 9.2 影响（分两类）

| 节点类别 | 验证所需前提 | 字段契约能否提供 | 影响 |
|---|---|---|---|
| 标量规则（密级/金额，POC）| 字段存在 + type 匹配 | ✅ 能（type 字段已有）| **POC 不受阻** |
| 数组/量词/聚合（all/any/count/sum）| 字段存在 + type + **基数上限** | ❌ 缺基数 | 「全量保证」不可兑现 |

### 9.3 结论与路线

- **短期（POC 落地方式）**：schema 作为「**验证假设**」而非规范一部分。验证结论表述为「**假设字段 tool.args.amount 存在且为数值型，则规则 F1 满足性质 P**」——标量规则据此可兑现「条件保证」。
- **中期 / 长期路线**：见 spec §7 字段契约的「〔验证缺口〕」标注（v2.1 可选 schema 子语言 → 长期 schema 入规范）。

---

## 10. 综合审查处置（问题清单 P0/P1/P2）

> 2026-09-01 全量审查。已处理项引用既有版本；新增项此处给出处置；分歧单独列出。

### 10.1 P0 阻塞性（4）

| # | 问题 | 处置 |
|---|---|---|
| P0-1 | schema 契约冲突 | ✅ 已处理 = 发现 1.1（v4 §9 + spec §7 标注）|
| P0-2 | translation validation 方法缺失 | ➕ 四层：①差分测试（M1–M4，双编译器 Python/Z3 + Rust/cvc5 生成同规则 SMT 验证语义等价）；②反例一致性 harness（M1，反例自动转 fact 对象回放真实求值器比对）；③符号执行验证（M4，对 AST→SMT 转换规则做符号执行）；④规约级证明（长期，Lean/Coq 证编译器正确性）|
| P0-3 | 三值逻辑编码未具体化 | ⚠️ 部分已处理（v5 §3）+ 分歧（见 10.4）|
| P0-4 | 聚合返回类型不统一 | ➕ 统一为 `Option<Int>`：count/sum(空)→`Some(0)`；avg/min/max(空)→`None`（条件上下文折叠 false）；SMT ADT `Option<Int> = None | Some(value: Int)` |

### 10.2 P1 重大（6）

| # | 问题 | 处置 |
|---|---|---|
| P1-1 | override/ring 性质 | ✅ 已处理 = 发现 1.3（v6 §2）|
| P1-2 | POC 选题简单 | ➕ 两阶段 POC（见 §4 修订）：Phase 1 密级 / Phase 2 量词+三值 |
| P1-3 | E4 资源上限可表达性 | ➕ 分级：Grade A 结构约束（树深≤6/节点≤64）加载时静态检查不进 SMT；数组基数靠 schema `max_cardinality` → SMT bounded quantifier；Grade B/C 部分约束运行时检查、不进静态验证 |
| P1-4 | scale=14+half-even 精确建模 | ➕ POC 完全避开 round/div（只整数比较）；完整版用位向量 QF_BV 编码定点小数 + half-even，或 round 作 UF + 近似约束 |
| P1-5 | temporal_state（within/rate）建模缺失 | ➕ 明确：POC 与 Grade A 完全不支持 within/rate；完整版 temporal_state 作额外输入（历史事件序列）+ Bounded Model Checking 有限窗口，或声明「含 temporal_state 规则需运行时验证、不入静态分析」|
| P1-6 | var 节点映射缺失 | ✅ 已处理 = 发现 1.4（v7 §3：field→UF / var→自由变量 / literal→常量）|

### 10.3 P2 优化（3）

| # | 问题 | 处置 |
|---|---|---|
| P2-1 | formal ↔ vectors 互补 | ➕ 分工：erdl-vectors=运行时一致性（跨实现逐字节对拍）；erdl-formal=静态性质（编译时证明）。汇合点：schema 假设由 vectors 验证运行时成立；formal 反例补 vectors 库 |
| P2-2 | NFC 信任假设审计影响 | ➕ 解析层 NFC 规范化 + SMT 前预规范化 + canonical_tree 显式标记「字符串已 NFC」|
| P2-3 | 13 决策类型验证语义 | ✅ 已处理 = 发现 1.3（v6 §2）；映射微调：DELEGATE/DEFER 归放行、NOTIFY 归人工介入（见 v6 表）|

### 10.4 P0-3 分歧：Kleene vs 叶子折叠（已调研定案）

- **规范事实（E11 + §10.4）**：字段缺失「统一返回 false」，比较节点「返回 false」——**叶子折叠**，不是 Kleene 传播。
- **P0-3 提议（Kleene）**：比较→undefined、`not(undefined)=undefined`——与规范「比较→false」不符。
- **调研定案（2026-09-01）**：Rego（安全策略语言）的 NAF `not(undefined)=true` 与折叠 `not(false)=true` 等价、fail-closed；SQL（查询语言）的 Kleene fail-open。**采纳规范折叠，否决 Kleene**。
- **纠偏**：规范 E11 已充分定义，核心 `not` 无歧义（操作数永远是已折叠布尔值），无需 spec 澄清。SMT 按折叠编码（比较→`Def(false)`）。

---

## 11. 交叉深研（对照 erdl-spec 全量 · 2026-09-01）

### 11.1 Simple → core 编译层（方案缺失，补）

方案只做 34 节点内核 SMT，但规范 §11.4 定义 **Simple 30 运算符 → 表达式树权威编译映射**（13 直接 + 6 not 组合 + 9 length/count 组合 + 2 时间修饰），§44.1 列为**验证对象三（30 编译向量）**。这是独立翻译验证目标，非 34 节点 SMT 一部分。→ 增加「Simple 编译正确性」验证：30 运算符→树映射，尤其 exists 守卫（not_*/length_*/count_*→`exists(field) AND 派生`）+ not_exists 例外。

### 11.2 within/rate 有状态算子（P1-5 深化）

§11.4：within/rate 仅有的 2 个有状态算子；滑动窗口计数由 **GuardStateManager**（树外状态源）维护、`temporal_state` 进 DO；真值语义=计数达阈值→true/未达→record+false。滑动窗口由 **V-TEMPORAL（多决策序列重放）**验证，不进 V-ENGINE 单条向量、不进 SMT。

### 11.3 Grade C fn 委派不可重算（§16）

§16.2：Grade C=含函数委派，**不可重算**（gloss 显式标记，§27.6）。fn 黑盒不可 SMT 验证，只验调用边界（输入/输出哈希入签名原像）。→ Grade C 明确在 SMT 范围外。

### 11.4 向量计数纠正（§44/§50 权威）

**V-ENGINE = 201**（节点语义 136 + 求值约束 35 + Simple 编译 30），**非 223**；Core 基线 = 309（201+22+86），可验证 301（V-DO-v15 86 条中 8 条待签名层落地）。方案/记忆统一此口径。

### 11.5 双实现生成制（P0-2 的 spec 内建机制）

§48.2：语义敏感向量（E2 定点/E8 量词/时间 UTC 日历）预期值 MUST 由 OpenOBA + 独立实现（Concordia）各自生成逐字节比对。P0-2 的 translation validation 在 spec 已有内建机制，formal 应复用。

### 11.6 SMT ↔ 向量交叉验证

§44.1 验证对象一（34 节点×4 场景=136 向量）是运行时语义权威基准。SMT 模型 34 节点编码应与这 136 条向量交叉验证（SMT 推导结果=向量答案），作为 formal 模型正确性第一道闸门。

---

_本方案 v10 为 POC 立项依据，代码未动。待 Henry 拍板后启动 M1。_
