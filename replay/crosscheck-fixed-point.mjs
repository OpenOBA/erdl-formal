// 交叉验证：erdl 引擎的定点小数（fixed-point.js）与我方 fixed_point.py 一致。
import { fromDecimalString, add, div, toDecimalString } from '../../erdl-landing/dist/expr-tree/fixed-point.js';

const cases = [
  ['1/3', div(fromDecimalString('1'), fromDecimalString('3'))],
  ['5e-15 (half-even down)', fromDecimalString('0.000000000000005')],
  ['15e-15 (half-even up)', fromDecimalString('0.000000000000015')],
  ['0.1+0.2', add(fromDecimalString('0.1'), fromDecimalString('0.2'))],
];

const expected = {
  '1/3': '0.33333333333333',
  '5e-15 (half-even down)': '0',
  '15e-15 (half-even up)': '0.00000000000002',
  '0.1+0.2': '0.3',
};

let ok = true;
for (const [name, r] of cases) {
  const got = toDecimalString(r);
  const pass = got === expected[name];
  if (!pass) ok = false;
  console.log(`${pass ? '✅' : '❌'} ${name}: got ${got} (expect ${expected[name]})`);
}
console.log('\nerdl fixed-point 与我方 fixed_point.py 一致:', ok ? '✅ PASS' : '❌ FAIL');
process.exit(ok ? 0 : 1);
