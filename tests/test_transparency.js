const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const T = require('../static/transparency.js');
const appSource = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const htmlSource = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const cssSource = fs.readFileSync(path.join(__dirname, '../static/style.css'), 'utf8');

function parsedScenario(overrides = {}) {
  return {
    summary: 'draft',
    confidence: 0.72,
    events: [{
      type: 'life_event',
      name: '旅行',
      start_month: 3,
      one_time_amount: -24000,
      source: 'ai'
    }],
    expense_adjustments: [{
      category: 'food',
      start_month: 3,
      monthly_amount: 1500,
      reason: '旅遊餐飲'
    }],
    display: {
      title: '日本旅行',
      scenario_type: '旅行',
      start_month: 3,
      duration_months: 1,
      one_time_cost: 24000,
      recurring_monthly_cost: 1500,
      low_estimate: 22000,
      expected_estimate: 25500,
      high_estimate: 30000,
      status: '等待確認',
      assumptions: [{ key: 'style', label: '旅遊方式', value: '標準型', source: 'AI 推估', editable: true }],
      sources: [{ label: '旅行成本', value: '估算', source: 'AI 推估', estimated: true }]
    },
    ...overrides
  };
}

test('scenario summary renders required fields and supports multiple scenarios', () => {
  const first = T.createScenarioModel(parsedScenario(), 'one');
  const second = T.createScenarioModel(parsedScenario({ display: { ...parsedScenario().display, title: '搬家' } }), 'two');
  const html = [first, second].map(T.ScenarioSummaryCard).join('');
  assert.match(html, /AI 模擬|日本旅行|搬家|一次性成本|每月週期成本|低 \/ 預期 \/ 高/);
  assert.equal((html.match(/scenario-summary-card/g) || []).length, 2);
});

test('assumptions and source labels distinguish editable estimates', () => {
  const assumptions = T.AssumptionList([
    { label: '車貸利率', value: '2.8%', source: 'AI 推估', editable: true },
    { label: '引擎結果', value: '12', source: '財務引擎計算', editable: false }
  ]);
  const sources = T.SourceList([
    { label: '每日餐飲', value: 'NT$1,200', source: '系統預設', estimated: true }
  ]);
  assert.match(assumptions, /可修改/);
  assert.match(assumptions, /disabled/);
  assert.match(sources, /系統預設 · 估算值/);
});

test('default variable-expense percentages total 100 percent', () => {
  const normalized = T.normalizePercentages({ food: 8, transportation: 3, shopping: 2 });
  const total = Object.values(normalized).reduce((sum, value) => sum + value, 0);
  assert.equal(total, 100);
  const allocation = T.allocationFromTotal(20000, normalized);
  assert.equal(Math.round(allocation.reduce((sum, item) => sum + item.monthly_amount, 0)), 20000);
  assert.ok(allocation.every(item => item.source === '系統預設'));
});

test('expense comparison displays original, adjusted and textual differences', () => {
  const html = T.ExpenseComparisonTable([{
    category: 'food',
    label: '餐飲',
    original_amount: 7000,
    adjusted_amount: 8500,
    difference: 1500,
    reason: '旅遊期間餐飲增加',
    source: 'AI 推估'
  }]);
  assert.match(html, /原始支出/);
  assert.match(html, /情境後支出/);
  assert.match(html, /\+NT\$1,500/);
  assert.match(html, /旅遊期間餐飲增加/);
});

test('scenario events use category adjustment instead of recurring cashflow', () => {
  const scenario = T.createScenarioModel(parsedScenario(), 'travel');
  const events = T.scenarioEvents(scenario, 12);
  const adjustment = events.find(item => item.name.startsWith('支出調整'));
  assert.equal(adjustment.monthly_amount, 0);
  assert.equal(adjustment.category_monthly_adjustment, 1500);
});

test('AI scenarios require confirmation and optional fields are tolerated', () => {
  const scenario = T.createScenarioModel({ events: [], expense_adjustments: [], confidence: 0.2 }, 'missing');
  assert.equal(scenario.status, '等待確認');
  assert.equal(scenario.one_time_cost, 0);
  assert.match(T.ScenarioSummaryCard(scenario), /等待確認/);
  assert.match(appSource, /scenario\.status = '使用者已確認'/);
});

test('financial impact renders backend before-and-after values', () => {
  const html = T.FinancialImpactSummary({
    final_assets: { before: 100000, after: 85000, difference: -15000 },
    fsi: { before: 0.3, after: 0.5, difference: 0.2 }
  });
  assert.match(html, /情境對財務|期末資產|原始|情境後|-NT\$15,000/);
  assert.match(html, /最高 FSI/);
});

test('empty chart, event markers and disabled legend behavior are implemented', () => {
  assert.match(htmlSource, /尚無模擬資料，請先確認 AI 建立的情境並執行模擬。/);
  assert.match(appSource, /event_markers/);
  assert.match(appSource, /pointStyle: 'triangle'/);
  assert.match(appSource, /onClick: \(\) => \{\}/);
  assert.match(appSource, /this\.chart\.destroy\(\)/);
  assert.doesNotMatch(appSource, /chartTypes|Switch to .* chart/);
});

test('mobile layout includes single-column transparency sections', () => {
  assert.match(cssSource, /@media \(max-width: 760px\)/);
  assert.match(cssSource, /\.impact-grid,[\s\S]*grid-template-columns: 1fr/);
  assert.match(cssSource, /\.assumption-row, \.source-list > div/);
});
