// 反例回放：验证 erdl 真实引擎的 E11 折叠语义与 SMT 模型一致。
//
// 反例 = 「字段缺失绕过」：字段缺失 → 比较折叠 false → 规则不命中 → 不拦截（fail-open）。
// 这与 erdl-formal 的 test_g3_field_missing_bypass 断言的是同一语义。

import { Evaluator } from '../../erdl/dist/index.js';

const evaluator = new Evaluator();

const rule = {
  id: 'g3-amount-guard',
  name: 'G3 amount guard',
  description: 'DENY when amount > 100',
  category: 'security',
  conditions: [{ field: 'amount', operator: 'gt', value: 100 }],
  action: { decision: 'DENY' },
  priority: 1,
  enabled: true,
};

// 场景 1：amount 存在且 > 100 → 应拦截 DENY
const r1 = evaluator.evaluate([rule], { amount: 200 });
console.log('amount=200        → decision =', r1.decision, ' (expect DENY)');

// 场景 2：amount 缺失 → 比较折叠 false → 不命中 → 不拦截（fail-open 反例）
const r2 = evaluator.evaluate([rule], {});
console.log('amount missing    → decision =', r2.decision, ' (expect NOT DENY = fail-open bypass)');

// 场景 3：amount 存在但 ≤ 100 → 不命中 → 不拦截
const r3 = evaluator.evaluate([rule], { amount: 50 });
console.log('amount=50         → decision =', r3.decision, ' (expect NOT DENY)');

// 断言：SMT 模型与引擎一致
const ok =
  r1.decision === 'DENY' &&
  r2.decision !== 'DENY' &&
  r3.decision !== 'DENY';
console.log('\n反例回放一致:', ok ? '✅ PASS' : '❌ FAIL');
process.exit(ok ? 0 : 1);
