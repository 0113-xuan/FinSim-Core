const test = require('node:test');
const assert = require('node:assert/strict');
const results = require('../static/results-model.js');

const profile = {cash_balance: 900000, investment_value: 500000};
const bands = {
  months: [1, 2, 3],
  net_worth: {p5: [1, 2, 3], p25: [2, 3, 4], p50: [3, 4, 5], p75: [4, 5, 6], p95: [5, 6, 7]},
};

test('bandData labels months as YYYY-MM and prepends today for every percentile', () => {
  const data = results.bandData(bands, '2027-01', [], profile);
  assert.deepEqual(data.labels, ['2026-12', '2027-01', '2027-02', '2027-03']);
  for (const values of Object.values(data.series)) assert.equal(values[0], 1400000);
  assert.deepEqual(data.summary, {period: '2027-03', p5: 3, p25: 4, p50: 5, p75: 6, p95: 7});
});

test('bandData without a profile starts at month 1 and does not mutate the response', () => {
  const data = results.bandData(bands, '2027-11', []);
  assert.deepEqual(data.labels, ['2027-11', '2027-12', '2028-01']);
  data.series.p50.push(99);
  assert.deepEqual(bands.net_worth.p50, [3, 4, 5]);
});

test('band markers point at event months but never at the starting month-end', () => {
  const events = [{name: '買車', start_period: '2027-02'}, {name: '早於起點', start_period: '2026-12'}, {name: '範圍外', start_period: '2030-01'}];
  const data = results.bandData(bands, '2027-01', events, profile);
  assert.deepEqual(data.markers, [{index: 2, period: '2027-02', name: '買車'}]);
});

test('band summary states the 90% and middle-half ranges and that lines are not paths', () => {
  const text = results.bandSummaryText({period: '2046-10', p5: 100, p25: 200, p50: 300, p75: 400, p95: 500}).join('');
  assert.match(text, /2046-10/);
  assert.match(text, /90% 的試驗/);
  assert.match(text, /一半的試驗/);
  assert.match(text, /不是某一次試驗的實際路徑/);
});

test('splitData separates cash, investment and net worth with a starting point', () => {
  const curve = [
    {month: 1, balance: 880000, investment_value: 510000, net_worth: 1390000},
    {month: 2, balance: 860000, investment_value: 520000, net_worth: 1380000},
  ];
  const data = results.splitData(curve, '2027-01', [], profile);
  assert.deepEqual(data.cash, [900000, 880000, 860000]);
  assert.deepEqual(data.investment, [500000, 510000, 520000]);
  assert.deepEqual(data.netWorth, [1400000, 1390000, 1380000]);
  assert.equal(data.hasInvestment, true);
  assert.equal(data.summary.cash.minimumPeriod, '2027-02');
});

test('splitData reports no investment when every value is zero', () => {
  const data = results.splitData([{month: 1, balance: 10, investment_value: 0, net_worth: 10}], '2027-01', [], {cash_balance: 10, investment_value: 0});
  assert.equal(data.hasInvestment, false);
});

const mc = {
  sampled_parameters: ['inflation_rate', 'raise_rate', 'investment_return'],
  sampling_method: {block_months: 12, history_start: '2003-01', history_end: '2026-09'},
};
const request = {profile: {monthly_investment: 3000, target_emergency_months: 6}};

test('assumption rows disclose historical defaults, sampling, seed and vehicle note', () => {
  const simulation = {assumptions: {annual_inflation_rate: 0.0134, inflation_source: 'historical_average', raise_rate: null,
    raise_source: 'follows_inflation', annual_return_rate: 0.1397, return_source: 'historical_average'}};
  const rows = results.assumptionRows({simulation, mc, request, startPeriod: '2026-11', months: 240,
    simulations: 300, seed: 42, converted: {note: '購車持有成本以固定通膨率每年調整。'}});
  const text = Object.fromEntries(rows.map(row => [row.label, row.value]));
  assert.equal(text['模擬期間'], '2026-11 起共 240 個月（至 2046-10）');
  assert.match(text['確定性模擬的通膨率'], /1\.34%.*2003-01 至 2026-09/);
  assert.match(text['Monte Carlo 的通膨'], /連續 12 個月一組/);
  assert.equal(text['調薪率'], '跟著通膨，每年調整一次');
  assert.match(text['確定性模擬的投資報酬率'], /13\.97%/);
  assert.match(text['Monte Carlo 試驗'], /300 次，亂數種子 42/);
  assert.equal(text['購車成本'], '購車持有成本以固定通膨率每年調整。');
});

test('assumption rows show user rates and no investment', () => {
  const simulation = {assumptions: {annual_inflation_rate: 0.02, inflation_source: 'user', raise_rate: 0.03,
    raise_source: 'user', annual_return_rate: null, return_source: 'historical_average'}};
  const fixed = {...mc, sampled_parameters: ['investment_return']};
  const rows = results.assumptionRows({simulation, mc: fixed, request: {profile: {inflation_rate: 0.02}},
    startPeriod: '2026-11', months: 60, simulations: 300, seed: 42});
  const text = Object.fromEntries(rows.map(row => [row.label, row.value]));
  assert.match(text['確定性模擬的通膨率'], /你設定的固定值/);
  assert.match(text['Monte Carlo 的通膨'], /固定為每年 2%/);
  assert.equal(text['調薪率'], '每年固定 3%');
  assert.match(text['投資'], /沒有設定投資/);
  assert.equal(text['購車成本'], undefined);
});
