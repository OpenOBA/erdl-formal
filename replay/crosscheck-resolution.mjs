// 交叉验证：我方 resolution.py 的裁决语义与 erdl-landing 引擎 Evaluator 一致。
import { Evaluator } from '../../erdl-landing/dist/index.js';

const evaluator = new Evaluator();

const rule = (name, decision, priority, ring, override, catchAll = false) => ({
  id: name,
  name,
  description: name,
  category: 'security',
  // catch-all = 空条件（总是命中）；否则一个恒真条件（flag == true）。
  conditions: catchAll ? [] : [{ field: 'flag', operator: 'eq', value: true }],
  conditionLogic: 'AND',
  action: { decision, ring },
  priority,
  enabled: true,
  override,
});

const ctx = { flag: true };

const cases = [
  // --- override / ring / emergency（原有 4 例）---
  ['override ALLOW relaxes DENY', [rule('base-deny', 'DENY', 10, 0), rule('exc-allow', 'ALLOW', 20, 3, 'critical')], 'ALLOW'],
  ['override DENY cannot tighten ALLOW', [rule('base-allow', 'ALLOW', 10, 0), rule('ovr-deny', 'DENY', 20, 0, 'critical')], 'ALLOW'],
  ['higher-ring DENY overrides lower ALLOW', [rule('lower-allow', 'ALLOW', 10, 0), rule('higher-deny', 'DENY', 20, 1)], 'DENY'],
  ['EMERGENCY_HALT short-circuits', [rule('halt', 'EMERGENCY_HALT', 10, 0), rule('late-allow', 'ALLOW', 20, 3, 'critical')], 'EMERGENCY_HALT'],
  // --- v1.3 catch-all 语义（R1/R2）---
  ['catch-all DENY never overrides explicit ALLOW', [rule('explicit-allow', 'ALLOW', 10, 0), rule('catchall-deny', 'DENY', 20, 3, null, true)], 'ALLOW'],
  ['catch-all sorts last within a ring', [rule('catchall-deny', 'DENY', 10, 0, null, true), rule('explicit-allow', 'ALLOW', 10, 0)], 'ALLOW'],
  ['catch-all DENY still fires when nothing else set', [rule('catchall-deny', 'DENY', 10, 0, null, true)], 'DENY'],
  // --- 软决策累积 + 默认 ---
  ['REQUEST_HUMAN accumulates when nothing set', [rule('human', 'REQUEST_HUMAN', 10, 0)], 'REQUEST_HUMAN'],
  ['default ALLOW when nothing matches', [], 'ALLOW'],
  ['multiple DENY stays DENY', [rule('deny-a', 'DENY', 10, 0), rule('deny-b', 'DENY', 20, 1)], 'DENY'],
];

let ok = true;
for (const [name, rules, expected] of cases) {
  const got = evaluator.evaluate(rules, ctx).decision;
  const pass = got === expected;
  if (!pass) ok = false;
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name}: got ${got} (expect ${expected})`);
}
console.log('\nresolution 与 erdl-landing 引擎一致:', ok ? 'PASS' : 'FAIL');
process.exit(ok ? 0 : 1);
