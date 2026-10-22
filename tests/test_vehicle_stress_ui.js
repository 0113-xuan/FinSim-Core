const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const js = fs.readFileSync('static/vehicle.js', 'utf8');

function renderHarness(stresses) {
  const nodes = new Map(), rows = [];
  const $ = id => {
    if (!nodes.has(id)) nodes.set(id, {value:'', textContent:'', dataset:{},
      replaceChildren(){}, focus(){}, scrollIntoView(){}});
    return nodes.get(id);
  };
  const context = {$, Intl, renderOwnershipCosts(){},
    row:(target, values) => rows.push({target, values}),
    document:{querySelector:() => ({value:'single'})}};
  vm.createContext(context);
  vm.runInContext(js.slice(0, js.indexOf('const form =')) +
    js.slice(js.indexOf('function name('), js.indexOf('function renderOwnershipCosts(')), context);
  context.render({scenario:{monthly_loan_payment:1, total_loan_interest:1, monthly_surplus:10000,
    minimum_cash_balance:1000000, minimum_emergency_fund_months:30},
    baseline:{monthly_surplus:20000}, constraints:[], stress_tests:stresses,
    affordability:{status:'no_feasible_price', constraint_results:[]}});
  return {$, text:rows.filter(r => r.target === 'stresses').map(r => r.values.join(' ')).join('\n')};
}

function stress(name='unemployment') {
  return {name, applicable:true, passed:true,
    metrics:{minimum_cash_balance:1000000, minimum_cash_month:'2026-10',
      minimum_emergency_fund_months:30, ending_cash:2000000},
    constraints:[{key:'minimum_cash_balance', actual:1000000, required:0, passed:true},
      {key:'minimum_monthly_surplus', actual:-30000, required:5000, applicable:false, passed:null}]};
}

test('unemployment backend pass excludes N/A surplus from failed summary and table', () => {
  const h = renderHarness([stress()]);
  assert.equal(h.$('stressSummary').textContent, '1 種適用情況，0 種未符合限制');
  assert.match(h.text, /符合/);
  assert.match(h.text, /最低每月結餘（元）.*不適用/);
  assert.doesNotMatch(h.text, /結餘（元）未符合/);
  assert.equal(h.$('riskHeadline').dataset.state, 'passed');
});

test('applicable false constraint fails while an inapplicable false constraint is excluded', () => {
  const s = stress(); s.passed = false; s.constraints[0].passed = false;
  s.constraints[1].passed = false;
  const h = renderHarness([s]);
  assert.match(h.$('stressSummary').textContent, /1 種未符合/);
  assert.match(h.text, /最低現金（元）未符合/);
  assert.doesNotMatch(h.text, /結餘（元）未符合/);
  assert.match(h.text, /結餘（元）.*不適用/);
  assert.equal(h.$('riskHeadline').dataset.state, 'failed');
});

test('overall stress status comes from backend passed and not recomputed constraints', () => {
  const s = stress(); s.passed = false;
  s.constraints.forEach(c => { c.passed = true; });
  const h = renderHarness([s]);
  assert.match(h.$('stressSummary').textContent, /1 種未符合/);
  assert.match(h.text, /未符合/);
});

for (const value of [null, undefined]) {
  test(`missing or null verdict is not converted to pass or failure (${value})`, () => {
    const s = stress(); s.passed = value; s.constraints[0].passed = value;
    const h = renderHarness([s]);
    assert.match(h.$('stressSummary').textContent, /0 種未符合.*1 種尚未判定/);
    assert.match(h.text, /尚未判定/);
    assert.doesNotMatch(h.text, /全部符合|最低現金（元）未符合/);
    assert.equal(h.$('riskHeadline').dataset.state, 'unknown');
  });
}

test('other stresses use the same explicit pass/fail/N/A rules', () => {
  const passed = stress('income_reduction'); passed.constraints[1].passed = true;
  delete passed.constraints[1].applicable;
  const failed = stress('emergency_expense'); failed.passed = false; failed.constraints[0].passed = false;
  const skipped = stress('interest_rate'); skipped.applicable = false; skipped.passed = false;
  const h = renderHarness([passed, failed, skipped]);
  assert.equal(h.$('stressSummary').textContent, '2 種適用情況，1 種未符合限制');
  assert.match(h.text, /收入減少.*全部符合/);
  assert.match(h.text, /突發支出.*最低現金（元）未符合/);
  assert.match(h.text, /貸款利率.*不適用/);
});
