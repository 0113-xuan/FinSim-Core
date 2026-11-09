const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const C = require('../static/compare-model.js');
const M = require('../static/shell-model.js');

const plans = [{id:'p1',name:'換國產車'},{id:'p2',name:'換進口車'},{id:'p3',name:'換工作'},{id:'p4',name:'空計畫'}];
const eventsByPlan = {
  p1:[{id:'e1',type:'vehicle_purchase',name:'購車',start_period:'2027-01',details:{purchase_price:800000,payment_method:'cash'}}],
  p2:[{id:'e2',type:'vehicle_purchase',name:'購車',start_period:'2027-01',details:{purchase_price:1500000,payment_method:'financed',loan_term_months:60}}],
  p3:[{id:'e3',type:'salary_change',name:'換工作',start_period:'2027-03',new_salary:90000}],
  p4:[],
};
const options = C.eventOptions(plans, eventsByPlan);
const byId = new Map(options.map(option => [option.id, option]));

test('event options list every saved event with its plan, and skip empty plans', () => {
  assert.deepEqual(options.map(option => option.id), ['e1','e2','e3']);
  assert.equal(options[2].planName, '換工作');
  assert.match(options[0].detail, /購車｜2027-01｜車價/);
  // Both cars are named 購車 in saved data; the plan name is what identifies each scenario.
  assert.deepEqual(options.map(option => option.title), ['換國產車','換進口車','換工作']);
  const twoEvents = C.eventOptions([plans[0]], {p1:[eventsByPlan.p1[0], eventsByPlan.p3[0]]});
  assert.deepEqual(twoEvents.map(option => option.title), ['換國產車：購車','換國產車：換工作']);
});

test('default scenarios are one per plan that has events, capped at four', () => {
  assert.deepEqual(C.defaultScenarios(options), [
    {name:'',eventIds:['e1']},{name:'',eventIds:['e2']},{name:'',eventIds:['e3']}]);
  const many = Array.from({length:7}, (_, i) => ({id:`x${i}`,planId:`plan${i}`,title:`t${i}`}));
  assert.equal(C.defaultScenarios(many).length, C.MAX_SCENARIOS);
});

test('a blank scenario name joins its event names, a typed one wins', () => {
  assert.equal(C.scenarioName({name:'',eventIds:['e1','e3']}, 0, byId), '換國產車＋換工作');
  assert.equal(C.scenarioName({name:'  只換車 ',eventIds:['e1']}, 0, byId), '只換車');
  assert.equal(C.scenarioName({name:'',eventIds:[]}, 1, byId), '情境 2');
});

test('combining events from different plans yields one scenario with both events', () => {
  const {entries, problems} = C.resolveScenarios([{name:'換車又換工作',eventIds:['e1','e3']},{name:'只換進口車',eventIds:['e2']}], options);
  assert.deepEqual(problems, []);
  assert.deepEqual(entries.map(entry => [entry.name, entry.kind, entry.events.map(event => event.id)]),
    [[C.BASELINE_NAME,'baseline',[]],['換車又換工作','scenario',['e1','e3']],['只換進口車','scenario',['e2']]]);
  assert.deepEqual(entries[1].eventLabels, ['購車 2027-01','換工作 2027-03']);
});

test('invalid scenario sets are rejected in plain language', () => {
  const run = (scenarios, opts) => C.resolveScenarios(scenarios, options, opts).problems.join('；');
  assert.match(run([{name:'',eventIds:[]}]), /還沒有勾選事件/);
  assert.match(run([{name:'A',eventIds:['e1']},{name:'A',eventIds:['e2']}]), /名稱重複/);
  assert.match(run([{name:'A',eventIds:['e1','e3']},{name:'B',eventIds:['e3','e1']}]), /完全相同/);
  assert.match(run([{name:C.BASELINE_NAME,eventIds:['e1']}]), /基準名稱/);
  assert.match(run([{name:'A',eventIds:['e1']}], {baseline:false}), /至少需要兩個情境/);
  assert.equal(run([{name:'A',eventIds:['e1']}], {baseline:false}).includes('基準名稱'), false);
  assert.match(run([]), /至少建立一個情境/);
  // Ids that no longer exist (event deleted elsewhere) count as unchecked.
  assert.match(run([{name:'A',eventIds:['gone']}]), /還沒有勾選事件/);
});

function run(name, {p5, p50, p95, shortfall = 0, minimumCash = 100000, minimumMonth = 5, negativeMonth = null, kind = 'scenario', vehicles = []}) {
  return {name, kind, converted:{vehicles},
    simulation:{summary:{final_balance:500000,final_net_worth:p50,minimum_cash_balance:minimumCash,minimum_cash_month:minimumMonth,first_negative_cash_month:negativeMonth}},
    mc:{net_worth_percentiles:{p5,p50,p95},real_net_worth_percentiles:{p50:p50 * .9},percentiles:{p50:400000},probability_cash_shortfall:shortfall,
      monthly_bands:{months:[1,2,3],net_worth:{p50:[10,20,30]},cash:{p5:[5,-5,-10]}}}};
}
const rowsOf = runs => runs.map(item => C.summarize(item, '2027-01', 60));

test('summaries turn month numbers into periods and carry the Monte Carlo percentiles', () => {
  const [row] = rowsOf([run('A', {p5:1e6,p50:2e6,p95:3e6,minimumMonth:3,negativeMonth:7})]);
  assert.equal(row.minimumCashPeriod, '2027-03');
  assert.equal(row.firstNegativePeriod, '2027-07');
  assert.deepEqual(row.netWorth, {p5:1e6,p50:2e6,p95:3e6});
  assert.equal(rowsOf([run('B', {p5:1,p50:2,p95:3})])[0].firstNegativePeriod, null);
});

test('leaders pick the highest net worth, highest minimum cash and lowest shortfall, with ties kept', () => {
  const rows = rowsOf([run('A',{p5:0,p50:2000000,p95:3e6,shortfall:.1,minimumCash:50000}),
    run('B',{p5:0,p50:2000020,p95:3e6,shortfall:.02,minimumCash:90000}),run('C',{p5:0,p50:1500000,p95:3e6,shortfall:.02,minimumCash:90000})]);
  const lead = C.leaders(rows);
  assert.deepEqual([...lead.netWorth].sort(), [0, 1], 'a 20 dollar gap is below the 100 rounding step, so A and B tie');
  assert.deepEqual([...lead.shortfall].sort(), [1, 2]);
  assert.deepEqual([...lead.minimumCash].sort(), [1, 2]);
});

test('the conclusion names the leader, the safest scenario and the trade-off', () => {
  const rows = rowsOf([run('不做任何事',{p5:1e6,p50:3000000,p95:5e6,kind:'baseline'}),
    run('換進口車',{p5:5e5,p50:2000000,p95:4e6,shortfall:.2}),run('換國產車',{p5:8e5,p50:2800000,p95:4.5e6,shortfall:.05})]);
  const view = C.conclusion(rows, '2027-01', 60);
  assert.match(view.headline, /2031-12/);
  assert.match(view.headline, /「不做任何事」/);
  assert.match(view.lines.join(''), /現金不足機率最低的是「不做任何事」（0%），最高的是「換進口車」（20%）/);
  assert.equal(view.tone, 'caution');
  assert.doesNotMatch(view.headline + view.lines.join(''), /保證|一定|建議你|應該/);
  assert.match(view.caveat, /不是預測/);
});

test('many tied safest scenarios are counted instead of listed',()=>{
  const rows=rowsOf([run('A',{p5:0,p50:1e6,p95:2e6}),run('B',{p5:0,p50:2e6,p95:2e6}),run('C',{p5:0,p50:3e6,p95:2e6}),run('D',{p5:0,p50:4e6,p95:2e6,shortfall:.4})]);
  assert.match(C.conclusion(rows,'2027-01',60).lines.join(''),/最低的有 3 個情境（0%），最高的是「D」（40%）/);
  const all=rowsOf([run('A',{p5:0,p50:1e6,p95:2e6,shortfall:.1}),run('B',{p5:0,p50:3e6,p95:2e6,shortfall:.1})]);
  assert.match(C.conclusion(all,'2027-01',60).lines.join(''),/所有情境的現金不足機率都約 10%/);
});

test('trade-off sentence appears only when the richest scenario is not the safest', () => {
  const rows = rowsOf([run('高報酬',{p5:0,p50:3e6,p95:5e6,shortfall:.3}),run('保守',{p5:0,p50:2e6,p95:3e6,shortfall:.05})]);
  assert.match(C.conclusion(rows, '2027-01', 60).lines.join(''), /自己取捨/);
  const aligned = rowsOf([run('好',{p5:0,p50:3e6,p95:5e6,shortfall:.05}),run('差',{p5:0,p50:2e6,p95:3e6,shortfall:.3})]);
  assert.doesNotMatch(C.conclusion(aligned, '2027-01', 60).lines.join(''), /取捨/);
});

test('an alert tone and sentence appear when a fixed-value run goes below zero cash', () => {
  const view = C.conclusion(rowsOf([run('A',{p5:0,p50:2e6,p95:3e6,negativeMonth:4}),run('B',{p5:0,p50:1e6,p95:2e6})]), '2027-01', 60);
  assert.equal(view.tone, 'alert');
  assert.match(view.lines.join(''), /「A」會在 2027-04 第一次現金低於 0/);
});

test('scenarios with the same result are described as the same instead of ranked', () => {
  const rows = rowsOf([run('A',{p5:0,p50:2e6,p95:3e6}),run('B',{p5:0,p50:2000010,p95:3e6})]);
  const view = C.conclusion(rows, '2027-01', 60);
  assert.match(view.headline, /差不多/);
  assert.equal(view.tone, 'calm');
  assert.match(view.lines.join(''), /所有情境的現金都沒有低於 0/);
});

test('net worth gaps use the same wording as the plan page', () => {
  const [base, more, less, same] = rowsOf([run('b',{p5:0,p50:2e6,p95:0}),run('m',{p5:0,p50:2300000,p95:0}),run('l',{p5:0,p50:1800000,p95:0}),run('s',{p5:0,p50:2000010,p95:0})]);
  assert.equal(C.netWorthGap(more, base), `多了 ${M.money(300000)}`);
  assert.equal(C.netWorthGap(less, base), `少了 ${M.money(200000)}`);
  assert.equal(C.netWorthGap(same, base), '沒有差別');
});

test('chart series start from today and use the same months for every scenario', () => {
  const profile = {cash_balance:100,investment_value:50,monthly_income:1};
  const runs = [run('A',{p5:0,p50:1,p95:2}), run('B',{p5:0,p50:1,p95:2,kind:'baseline'})];
  const net = C.chartSeries(runs, 'netWorth', '2027-01', profile, []);
  assert.deepEqual(net.labels, ['2026-12','2027-01','2027-02','2027-03']);
  assert.deepEqual(net.series[0].values, [150,10,20,30]);
  const cash = C.chartSeries(runs, 'cash', '2027-01', profile, []);
  assert.deepEqual(cash.series[1].values, [100,5,-5,-10]);
  assert.equal(cash.series[1].kind, 'baseline');
  assert.match(C.chartSummary(cash, '現金')[0], /最低點 NT\$-?0?.*在 2027-03|最低點.*2027-03/);
});

test('vehicle rows keep the scenario name so different cars can be compared', () => {
  const rows = C.vehicleRows([run('A',{p5:0,p50:1,p95:2,vehicles:[{name:'國產車',economic_cost_in_horizon:1}]}),run('B',{p5:0,p50:1,p95:2})]);
  assert.deepEqual(rows.map(row => [row.scenario, row.name]), [['A','國產車']]);
});

test('the compare page is wired into the app and every element it uses exists', () => {
  const read = file => fs.readFileSync(path.join(__dirname, '../static', file), 'utf8');
  const html = read('compare.html'), page = read('compare-page.js');
  const ids = new Set([...page.matchAll(/\$\('([A-Za-z]+)'\)/g)].map(match => match[1]));
  assert.ok(ids.size > 20);
  for (const id of ids) assert.match(html, new RegExp(`id="${id}"`), `compare.html lacks #${id}`);
  assert.match(html, /data-page="compare"/);
  for (const script of ['planner-model','shell-model','results-model','compare-model','shell','charts','compare-page','pages'])
    assert.match(html, new RegExp(`src="/${script}.js"`));
  assert.match(read('pages.js'), /page==='compare'\)await root\.ComparePage\.start\(ctx\)/);
  assert.match(read('shell.js'), /add\('比較情境','\/compare\.html'/);
  assert.match(read('dashboard.html'), /href="\/compare\.html"/);
  assert.match(read('charts.js'), /drawCompare/);
});
