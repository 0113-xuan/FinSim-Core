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

test('band summary states the typical, 9-in-10 and most-common ranges in plain words', () => {
  const text = results.bandSummaryText({period: '2046-10', p5: 100, p25: 200, p50: 300, p75: 400, p95: 500}).join('');
  assert.match(text, /2046-10/);
  assert.match(text, /一般情況下淨資產約/);
  assert.match(text, /9 成的模擬/);
  assert.doesNotMatch(text, /百分位|中位數|分位數/);
  assert.match(text, /最常見的 5 成/);
  assert.match(text, /不是某一次模擬的實際路徑/);
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

test('assumption rows disclose historical defaults, sampling, run count and vehicle note in plain words', () => {
  const simulation = {assumptions: {annual_inflation_rate: 0.0134, inflation_source: 'historical_average', raise_rate: null,
    raise_source: 'follows_inflation', annual_return_rate: 0.1397, return_source: 'historical_average'}};
  const rows = results.assumptionRows({simulation, mc, request, startPeriod: '2026-11', months: 240,
    simulations: 2000, seed: 42, converted: {note: '購車持有成本以固定通膨率每年調整。'}});
  const text = Object.fromEntries(rows.map(row => [row.label, row.value]));
  assert.equal(text['模擬期間'], '2026-11 起共 240 個月（至 2046-10）');
  assert.match(text['固定值模擬的通膨率'], /1\.34%.*2003-01 至 2026-09/);
  assert.match(text['隨機模擬的通膨'], /連續 12 個月/);
  assert.equal(text['調薪率'], '跟著通膨，每年調整一次');
  assert.match(text['固定值模擬的投資報酬率'], /13\.97%/);
  assert.match(text['隨機模擬次數'], /2000 次/);
  assert.equal(text['購車成本'], '購車持有成本以固定通膨率每年調整。');
  const shown = rows.map(row => `${row.label}${row.value}`).join('');
  assert.doesNotMatch(shown, /Monte Carlo|亂數種子|確定性|抽樣|42/);
});

test('assumption rows show user rates and no investment', () => {
  const simulation = {assumptions: {annual_inflation_rate: 0.02, inflation_source: 'user', raise_rate: 0.03,
    raise_source: 'user', annual_return_rate: null, return_source: 'historical_average'}};
  const fixed = {...mc, sampled_parameters: ['investment_return']};
  const rows = results.assumptionRows({simulation, mc: fixed, request: {profile: {inflation_rate: 0.02}},
    startPeriod: '2026-11', months: 60, simulations: 2000, seed: 42});
  const text = Object.fromEntries(rows.map(row => [row.label, row.value]));
  assert.match(text['固定值模擬的通膨率'], /你設定的固定值/);
  assert.match(text['隨機模擬的通膨'], /固定為每年 2%，不隨機抽取/);
  assert.equal(text['調薪率'], '每年固定 3%');
  assert.match(text['投資'], /沒有設定投資/);
  assert.equal(text['購車成本'], undefined);
});

test('conclusion states the cash answer first and keeps the limits of the model in view', () => {
  const mc = {probability_cash_shortfall: 0.0333, net_worth_percentiles: {p5: 100, p50: 500, p95: 900}};
  const base = {summary: {minimum_cash_balance: 12000, minimum_cash_month: 3, first_negative_cash_month: null},
    mc, startPeriod: '2027-01', months: 60, simulations: 2000};
  const caution = results.conclusion(base);
  assert.equal(caution.tone, 'caution');
  assert.match(caution.headline, /固定值模擬顯示現金不會低於 0，但在較差的隨機情況下可能會/);
  assert.deepEqual(caution.facts.map(fact => fact.label.replace(/ ?\d{4}-\d{2} ?/, '')), ['現金最低會到（固定值模擬）', '現金不足機率（隨機模擬）', '的淨資產（隨機模擬，一般情況）']);
  assert.doesNotMatch(caution.headline + caution.facts.map(fact => fact.label).join(''), /平均/);
  assert.equal(caution.facts.length, 3);
  assert.equal(caution.facts[0].note, '發生在 2027-03');
  assert.equal(caution.facts[1].value, '3%');
  assert.equal(caution.facts[0].value, '$12,000');
  assert.equal(results.conclusion({...base, summary: {...base.summary, minimum_cash_balance: 1234.56}}).facts[0].value, '$1,200');
  assert.doesNotMatch(caution.facts[2].note, /\.00/);
  assert.match(caution.facts[2].label, /2031-12/);
  assert.match(caution.caveat, /不是預測，也不保證/);

  const alert = results.conclusion({...base, summary: {...base.summary, first_negative_cash_month: 7}});
  assert.equal(alert.tone, 'alert');
  assert.match(alert.headline, /固定值模擬顯示，現金會在 2027-07 第一次低於 0/);
  assert.match(alert.caveat, /固定值模擬.*隨機模擬.*2000 次.*不是預測，也不保證/);

  const calm = results.conclusion({...base, mc: {...mc, probability_cash_shortfall: 0}});
  assert.equal(calm.tone, 'calm');
  assert.match(calm.headline, /2000 次隨機模擬中，現金都沒有低於 0/);
});

test('conclusion compares the plan with the same plan without its events', () => {
  const mc = {probability_cash_shortfall: 0, net_worth_percentiles: {p5: 100, p50: 500, p95: 900}};
  const summary = {minimum_cash_balance: 10000, minimum_cash_month: 3, first_negative_cash_month: null, final_balance: 400000};
  const base = {summary, mc, startPeriod: '2027-01', months: 60, simulations: 2000};
  assert.equal(results.conclusion(base).comparison, null);
  const worse = results.conclusion({...base, baseline: {final_balance: 1000000, minimum_cash_balance: 250000.4}}).comparison;
  assert.equal(worse.lead, '和沒有這個事件相比');
  assert.equal(worse.text, '2031-12 的現金少了 $600,000，最低現金少了 $240,000。');
  const better = results.conclusion({...base, baseline: {final_balance: 100000, minimum_cash_balance: 10000}}).comparison;
  assert.equal(better.text, '2031-12 的現金多了 $300,000，最低現金沒有差別。');
});

test('amounts round to the nearest 100 and percents to whole numbers, without turning a real chance into 0%', () => {
  const shell = require('../static/shell-model.js');
  assert.equal(shell.money(1234567.89), '$1,234,600');
  assert.equal(shell.money(-249.9), '-$200');
  assert.equal(shell.money(-30), '$0');
  assert.equal(shell.money(null), '不適用');
  assert.doesNotMatch(shell.money(98765.43), /[.]/);
  assert.equal(shell.wholePercent(0.0333), '3%');
  assert.equal(shell.wholePercent(0.002), '不到 1%');
  assert.equal(shell.wholePercent(0), '0%');
});
