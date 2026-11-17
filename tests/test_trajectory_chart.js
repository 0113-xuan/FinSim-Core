const test = require('node:test');
const assert = require('node:assert/strict');

// Stubs: just enough page and Chart.js to capture what drawCompare hands to Chart.
let config = null;
globalThis.document = {body:{}, documentElement:{}};
globalThis.getComputedStyle = () => ({fontFamily:'sans', getPropertyValue:() => ''});
globalThis.addEventListener = () => {};
globalThis.Chart = class { constructor(canvas, cfg) { config = cfg; } destroy() {} };
globalThis.FutureWalletShell = {element: (tag, text) => ({tag, textContent:text})};
globalThis.ShellModel = require('../static/shell-model.js');
require('../static/charts.js');

const target = {id:'summary', replaceChildren() {}};
const canvas = {setAttribute() {}};

test("drawCompare keeps a line's own colour and dash, and hides the zero line from the legend", () => {
  const chart = {labels:['a', 'b'], series:[{name:'一般情況', kind:'baseline', color:'#0e7490', dash:[6, 4], values:[1, 2]}, {name:'買車', color:'#b45309', values:[1, 0]}]};
  globalThis.WalletCharts.drawCompare(canvas, target, chart, ['x'], {zeroLine:true});
  const [base, car, zero] = config.data.datasets;
  assert.deepEqual([base.borderColor, base.borderDash, car.borderColor, car.borderDash], ['#0e7490', [6, 4], '#b45309', []]);
  assert.equal(car.borderWidth, 2.5);
  assert.ok(zero.label.startsWith('_'));
});

test('a major event gets a dashed vertical line, a label card, and a thicker step segment', () => {
  const chart = {labels:['a', 'b', 'c', 'd', 'e'], series:[{name:'買車', color:'#b45309', values:[300000, 300000, -500000, -500000, -500000], marks:[{index:2, text:'買車 −$800,000'}]}]};
  globalThis.WalletCharts.drawCompare(canvas, target, chart, ['x'], {});
  const [car] = config.data.datasets;
  assert.equal(car.segment.borderWidth({p1DataIndex:2}), 4);              // the segment that ends on the event month
  assert.equal(car.segment.borderWidth({p1DataIndex:3}), undefined);
  const drawn = [];
  const draw = pixel => config.plugins[0].afterDatasetsDraw({
    ctx:{save() {}, restore() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, setLineDash() {}, roundRect() {}, fill() {}, arc() {}, measureText:() => ({width:40}), fillText:(text, x) => drawn.push([text, x])},
    chartArea:{left:0, right:500, top:0, bottom:300}, scales:{x:{getPixelForValue:() => pixel}}});
  draw(100);
  assert.deepEqual(drawn, [['買車 −$800,000', 134]]);                      // card just right of the line, text after the dot
  draw(480);
  assert.equal(drawn[1][1], 422);                                           // too close to the edge: the card goes left of the line
  draw(600);
  assert.equal(drawn.length, 2);                                            // a line outside the chart is not drawn
});

test('events in the same month share one guide line and one card', () => {
  const marks = name => [{index:1, text:name}];
  const chart = {labels:['a', 'b', 'c'], series:[{name:'甲', color:'#b45309', values:[1, 0, 0], marks:marks('甲')}, {name:'乙', color:'#6d28d9', values:[1, 0, 0], marks:marks('乙')}]};
  globalThis.WalletCharts.drawCompare(canvas, target, chart, ['x'], {});
  const guides = [], drawn = [];
  config.plugins[0].afterDatasetsDraw({
    ctx:{save() {}, restore() {}, beginPath() {}, moveTo:(x, y) => guides.push(x), lineTo() {}, stroke() {}, setLineDash() {}, roundRect() {}, fill() {}, arc() {}, measureText:() => ({width:40}), fillText:(text, x, y) => drawn.push([text, x, y])},
    chartArea:{left:0, right:500, top:0, bottom:300}, scales:{x:{getPixelForValue:() => 100}}});
  assert.equal(guides.length, 1);
  assert.deepEqual(drawn.map(([text, x]) => [text, x]), [['甲', 134], ['乙', 134]]);
  assert.ok(drawn[1][2] > drawn[0][2]);                                     // second row sits below the first
});
