const test = require('node:test');
const assert = require('node:assert/strict');

// Stubs: just enough page and Chart.js to capture what drawTrajectories hands to Chart.
let config = null;
globalThis.document = {body:{}, documentElement:{}};
globalThis.getComputedStyle = () => ({fontFamily:'sans', getPropertyValue:() => '#047857'});
globalThis.addEventListener = () => {};
globalThis.Chart = class { constructor(canvas, cfg) { config = cfg; } destroy() {} };
globalThis.FutureWalletShell = {element: (tag, text) => ({tag, textContent:text})};
globalThis.ShellModel = require('../static/shell-model.js');
globalThis.ResultsModel = require('../static/results-model.js');
require('../static/charts.js');

const months = 24, startPeriod = '2026-11';
const curve = fn => Array.from({length:months}, (_, i) => ({month:i + 1, balance:fn(i), investment_value:0, net_worth:fn(i)}));
const band = fn => ({p5:Array.from({length:months}, (_, i) => fn(i) - 100000), p50:Array.from({length:months}, (_, i) => fn(i)), p95:Array.from({length:months}, (_, i) => fn(i) + 100000)});
const bands = {months:Array.from({length:months}, (_, i) => i + 1), net_worth:band(i => 1000000 + i), cash:band(i => 200000 + i * 1000)};
const profile = {cash_balance:300000, investment_value:0, monthly_investment:0};
const target = {id:'summary', replaceChildren(...items) { this.items = items; }};
const canvas = {setAttribute() {}};
const labelsOf = () => config.data.datasets.map(d => d.label);

test('every cash path is drawn together with a zero line, and cash below zero is shaded', () => {
  const plan = curve(i => 300000 - i * 40000), baseline = curve(i => 300000 + i * 5000);
  globalThis.WalletCharts.drawTrajectories(canvas, target, {plan, baseline, bands}, startPeriod, [{name:'買車', start_period:'2027-03'}], profile, {});
  assert.deepEqual(labelsOf(), ['順利情況（隨機模擬）', '較差情況（隨機模擬）', '一般情況（隨機模擬）', '沒有這個事件', '有這個事件', '現金 0']);
  const [high, low, , , mine, zero] = config.data.datasets;
  assert.equal(high.fill, '+1');                       // the band is filled from the high line down to the low one
  assert.equal(low.data.length, months + 1);           // the starting month comes first
  assert.equal(low.data[0], 300000);                   // every path starts from today's cash
  assert.deepEqual(mine.fill.target, {value:0});
  assert.match(mine.fill.below, /180,35,24/);
  assert.ok(zero.data.every(value => value === 0));
  assert.ok(mine.order < high.order && mine.order < zero.order);   // the plan is drawn on top of the range
  assert.ok(mine.pointRadius.some(radius => radius > 0));   // the event month is marked
  assert.match(target.items.map(item => item.textContent).join(''), /沒有這個事件：現金最低.*有這個事件：現金最低.*隨機模擬到/);
});

test('without events or random bands only the plan and the zero line are drawn', () => {
  globalThis.WalletCharts.drawTrajectories(canvas, target, {plan:curve(i => 300000 + i)}, startPeriod, [], profile, {});
  assert.deepEqual(labelsOf(), ['有這個事件', '現金 0']);
});

test('a window shows only that many months after the start', () => {
  globalThis.WalletCharts.drawTrajectories(canvas, target, {plan:curve(i => 300000 + i), bands}, startPeriod, [], profile, {window:12});
  assert.equal(config.data.labels.length, 13);
  assert.ok(config.data.datasets.every(dataset => dataset.data.length === 13));
});

test('bandData can read the cash series and starts it from the cash balance', () => {
  const data = globalThis.ResultsModel.bandData(bands, startPeriod, [], profile, [], 'cash');
  assert.equal(data.series.p50[0], 300000);
  assert.equal(data.series.p50[1], 200000);
});

test('drawCompare keeps a line\'s own colour and dash, and hides the zero line from the legend', () => {
  const chart = {labels:['a', 'b'], series:[{name:'一般情況', kind:'baseline', color:'#0e7490', dash:[6, 4], values:[1, 2]}, {name:'買車', color:'#b45309', values:[1, 0]}]};
  globalThis.WalletCharts.drawCompare(canvas, target, chart, ['x'], {zeroLine:true});
  const [base, car, zero] = config.data.datasets;
  assert.deepEqual([base.borderColor, base.borderDash, car.borderColor, car.borderDash], ['#0e7490', [6, 4], '#b45309', []]);
  assert.equal(car.borderWidth, 2.5);
  assert.ok(zero.label.startsWith('_'));
});

test('a major event gets a dashed vertical line, a label with the size of the step, and a thick step segment', () => {
  const plan = curve(i => i < 5 ? 300000 : -500000), events = [{name:'買車', start_period:'2027-04'}];   // the step lands on month 6
  globalThis.WalletCharts.drawTrajectories(canvas, target, {plan}, startPeriod, events, profile, {window:12, from:2});
  assert.equal(config.data.labels.length, 13);
  assert.equal(config.data.labels[0], '2026-12');                       // starts two months in
  const mine = config.data.datasets.find(dataset => dataset.label === '有這個事件');
  const step = {p1DataIndex:4};                                          // month 6 is point 4 once two months are cut
  assert.equal(mine.segment.borderWidth(step), 7);
  assert.equal(mine.segment.borderWidth({p1DataIndex:3}), undefined);
  const drawn = [];
  const chart = {ctx:{save() {}, restore() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, setLineDash() {}, measureText:() => ({width:40}), fillText:(text, x) => drawn.push([text, x])},
    chartArea:{left:0, right:500, top:0, bottom:300}, scales:{x:{getPixelForValue:index => index * 10}}};
  config.plugins[0].afterDatasetsDraw(chart);
  assert.deepEqual(drawn.map(item => item[0]), ['買車 −$800,000']);
  assert.equal(drawn[0][1], 4 * 10 + 6);                                 // just right of the line
});
