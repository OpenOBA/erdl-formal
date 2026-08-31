// 交叉验证：我方 resolution.py 的裁决语义与 erdl 引擎 Evaluator 一致。
import { Evaluator } from '../../erdl/dist/index.js';

const evaluator = new Evaluator();

const rule = (name, decision, priority, ring, override) => ({
  id: name,
  name,
  description: name,
  category: 'security',
  conditions: [{ field: 'flag', operator: 'eq', value: true }],
  conditionLogic: 'AND',
  action: { decision, ring },
  priority,
  enabled: true,
  override,
});

const ctx = { flag: true };

const cases = [
  ['override ALLOW relaxes DENY', [rule('base-deny','DENY',10,0), rule('exc-allow','ALLOW',20,3,'critical')], 'ALLOW'],
  ['override DENY cannot tighten ALLOW', [rule('base-allow','ALLOW',10,0), rule('ovr-deny','DENY',20,0,'critical')], 'ALLOW'],
  ['higher-ring DENY overrides lower ALLOW', [rule('lower-allow','ALLOW',10,0), rule('higher-deny','DENY',20,1)], 'DENY'],
  ['EMERGENCY_HALT short-circuits', [rule('halt','EMERGENCY_HALT',10,0), rule('late-allow','ALLOW',20,3,'critical')], 'EMERGENCY_HALT'],
];

let ok = true;
for (const [name, rules, expected] of cases) {
  const got = evaluator.evaluate(rules, ctx).decision;
  const pass = got === expected;
  if (!pass) ok = false;
  console.log(`${pass ? '✅' : '❌'} ${name}: got ${got} (expect ${expected})`);
}
console.log('\nresolution 与我方 resolution.py 一致:', ok ? '✅ PASS' : '❌ FAIL');
process.exit(ok ? 0 : 1);
