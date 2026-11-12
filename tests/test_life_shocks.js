const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const model=require('../static/results-model.js');
const page=fs.readFileSync('static/plan-page.js','utf8');
const html=fs.readFileSync('static/plan.html','utf8');
const baseline={probability_cash_shortfall:0.1233,net_worth_percentiles:{p5:100000,p50:200000,p95:300000}};
const shocks={probability_cash_shortfall:0.4567,net_worth_percentiles:{p5:400000,p50:500000,p95:600000},assumptions:[
  {label:'重大醫療支出',kind:'expense',chance_in_horizon:0.2597,min_amount:50000,max_amount:300000},
  {label:'車禍與車損自付',kind:'expense',chance_in_horizon:0.17,min_amount:20000,max_amount:150000},
  {label:'收入中斷',kind:'income_gap',chance_in_horizon:0.2,duration_months:6}],disclaimer:'機率與金額是示範假設，不是統計或預測；只用來看這份計畫撐不撐得住意外。'};
test('switch starts off and gates the new endpoint and card',()=>{
  assert.match(html,/<input id="lifeShocksToggle" type="checkbox">/);
  assert.match(html,/id="lifeShocksCard"[^>]* hidden/);
  assert.match(page,/if\(includeLifeShocks\)loadLifeShocks\(lastRun\)/);
  assert.match(page,/revision\+\+;\$\('lifeShocksCard'\)\.hidden=true/);
});
test('both endpoints receive the same request with fixed simulation count and seed',()=>{
  assert.match(page,/const request=\{\.\.\.built\.request,simulations:500,seed:42\}/);
  assert.match(page,/post\('\/monte-carlo',request\)/);
  assert.match(page,/post\('\/monte-carlo\/life-shocks',run\.request\)/);
  assert.match(page,/lastRun=\{built,months,events,request,mc\}/);
});
test('comparison and assumptions use response values and preserve disclaimer',()=>{
  const view=model.lifeShocks(baseline,shocks);
  assert.deepEqual(view.columns.map(c=>c.label),['沒有意外','有意外']);
  assert.deepEqual(view.columns.map(c=>c.rows.map(r=>r[1])),[['12.33%','$100,000 到 $300,000','$200,000'],['45.67%','$400,000 到 $600,000','$500,000']]);
  assert.match(view.assumptions[0].value,/25\.97%.*50,000.*300,000/);
  assert.match(view.assumptions[2].value,/20%.*6 個月/);
  assert.equal(view.disclaimer,shocks.disclaimer);
});
test('endpoint failure keeps original results and offers retry',()=>{
  assert.ok(page.indexOf('renderResults(simulation,mc')<page.indexOf('if(includeLifeShocks)loadLifeShocks'));
  const code=page.slice(page.indexOf('async function loadLifeShocks'),page.indexOf('// Progress and failures'));
  assert.match(code,/catch\(error\)/);assert.match(code,/意外風險計算失敗/);assert.match(code,/retry\.addEventListener\('click'/);
  assert.doesNotMatch(code,/simulationResults.*hidden/);
});
test('response text is inserted as text, not HTML',()=>{
  const code=page.slice(page.indexOf('async function loadLifeShocks'),page.indexOf('// Progress and failures'));
  assert.doesNotMatch(code,/innerHTML/);assert.match(code,/S\.element\('p',view\.disclaimer\)/);
});
