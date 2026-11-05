const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createStore,taipeiPeriod} = require('../static/shell.js');

function fakeClient(data = [{id:'row'}], error = null) {
  const calls = [];
  return {calls, from(table) {
    const call = {table, steps:[]}; calls.push(call);
    const builder = {then(resolve,reject) { return Promise.resolve({data,error}).then(resolve,reject); }};
    for (const name of ['select','eq','order','maybeSingle','single','upsert','insert','update','delete']) {
      builder[name] = (...args) => { call.steps.push([name,...args]); return builder; };
    }
    return builder;
  }};
}
test('planner reads are restricted to the signed-in user and selected plan',async()=>{
  const client=fakeClient(), store=createStore(client,'current-user');
  await store.profile();await store.debts();await store.plans();await store.events('selected-plan');
  assert.deepEqual(client.calls.map(c=>c.table),['profiles','debts','plans','plan_events']);
  for(const call of client.calls) {
    assert.ok(call.steps.some(s=>s[0]==='eq'&&s[1]==='user_id'&&s[2]==='current-user'));
    assert.notEqual(call.steps.find(s=>s[0]==='select')[1],'*');
  }
  assert.ok(client.calls[3].steps.some(s=>s[0]==='eq'&&s[1]==='plan_id'&&s[2]==='selected-plan'));
});
test('planner inserts and upserts always set the session owner',async()=>{
  const client=fakeClient(), store=createStore(client,'current-user');
  await store.saveProfile({monthly_income:100,user_id:'other-user'});
  await store.addDebt({name:'debt',user_id:'other-user'});
  await store.addPlan({name:'plan',user_id:'other-user'});
  await store.addEvent('selected-plan',{name:'event',user_id:'other-user',plan_id:'other-plan'});
  for(const call of client.calls) assert.equal(call.steps.find(s=>['insert','upsert'].includes(s[0]))[1].user_id,'current-user');
  assert.equal(client.calls[0].steps.find(s=>s[0]==='upsert')[2].onConflict,'user_id');
  assert.equal(client.calls[3].steps.find(s=>s[0]==='insert')[1].plan_id,'selected-plan');
});
test('deletes filter both ownership and row identity, events also filter their plan',async()=>{
  const client=fakeClient(), store=createStore(client,'current-user');
  await store.removeDebt('debt');await store.removePlan('plan');await store.removeEvent('selected-plan','event');
  for(const call of client.calls) {
    assert.ok(call.steps.some(s=>s[0]==='delete'));
    assert.ok(call.steps.some(s=>s[0]==='eq'&&s[1]==='user_id'&&s[2]==='current-user'));
    assert.ok(call.steps.some(s=>s[0]==='eq'&&s[1]==='id'));
  }
  assert.ok(client.calls[2].steps.some(s=>s[0]==='eq'&&s[1]==='plan_id'&&s[2]==='selected-plan'));
});
test('Supabase errors and zero-row deletion are surfaced to the page controller',async()=>{
  const store=createStore(fakeClient(null,{message:'儲存未完成'}),'current-user');
  for(const action of [()=>store.profile(),()=>store.debts(),()=>store.plans(),()=>store.events('plan'),
    ()=>store.saveProfile({}),()=>store.addDebt({}),()=>store.addPlan({}),()=>store.addEvent('plan',{}),
    ()=>store.removeDebt('row'),()=>store.removePlan('row'),()=>store.removeEvent('plan','row')]) {
    await assert.rejects(action,/儲存未完成/);
  }
  await assert.rejects(()=>createStore(fakeClient([]),'current-user').removePlan('missing'),/資料已不存在/);
});
test('the event picker panel is hidden once a plan has an event and results avoid statistics jargon',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  assert.match(html,/<section id="eventEditorPanel" class="panel"/);
  assert.match(page,/eventEditorPanel'\)\.hidden=events\.length>0&&!editing/);
  assert.match(page,/if\(ctx\.busy\|\|editing\|\|events\.length\|\|template\?\.status!=='available'\)return;/);
  const results=html.slice(html.indexOf('id="simulationResults"'));
  assert.doesNotMatch(results,/百分位|中位數|分位數|（p\d+）/);
});
test('insurance items live in a modal dialog outside the event form',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const start=html.indexOf('id="eventForm"'),eventForm=html.slice(start,html.indexOf('</form>',start));
  const dialog=html.slice(html.indexOf('<dialog id="insuranceDialog"'),html.indexOf('</dialog>',html.indexOf('<dialog id="insuranceDialog"')));
  assert.match(html,/<dialog id="insuranceDialog" class="plan-dialog" aria-labelledby="insuranceDialogTitle">/);
  assert.match(eventForm,/id="openInsuranceDialog" type="button" aria-haspopup="dialog" disabled/);
  assert.doesNotMatch(eventForm,/id="insuranceItems"/);
  assert.match(eventForm,/name="annual_insurance"/);
  for(const id of ['insuranceItems','insuranceDialogTotal','closeInsuranceDialog'])assert.match(dialog,new RegExp(`id="${id}"`));
});
test('start month is derived from Taipei time across UTC month and year boundaries',()=>{
  assert.equal(taipeiPeriod(new Date('2026-10-31T15:59:59Z')),'2026-10');
  assert.equal(taipeiPeriod(new Date('2026-10-31T16:00:00Z')),'2026-11');
  assert.equal(taipeiPeriod(new Date('2026-12-31T16:00:00Z')),'2027-01');
});
test('the independent page pins supabase-js and exposes only supported event entry types',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  assert.match(html,/@supabase\/supabase-js@2\.45\.4\/dist\/umd\/supabase\.js/);
  assert.match(html,/href="\/style.css"/);
  assert.doesNotMatch(html,/投資市值尚未納入計算/);
  assert.match(html,/現金不夠時，系統不會自動賣出投資來補/);
  for(const id of ['endingInvestment','netWorthP5','netWorthP50','netWorthP95','realNetWorthP50','samplingNote','dataSources'])
    assert.match(html,new RegExp(`id="${id}"`));
  const eventForm=html.slice(html.indexOf('id="eventForm"'),html.indexOf('</form>',html.indexOf('id="eventForm"')));
  assert.match(html,/id="eventTemplatePicker"/);
  assert.match(html,/id="changeTemplate" type="button" hidden/);
  assert.match(eventForm,/<label data-event-name hidden>事件名稱/);
  assert.match(html,/src="\/event-templates.js"/);
  assert.match(eventForm,/<input type="hidden" name="type"/);
  assert.doesNotMatch(eventForm,/<select name="type"/);
  assert.deepEqual(require('../static/event-templates.js').availableTemplates().map(t=>t.eventType).sort(),
    ['one_time','range','salary_change','vehicle_purchase'].sort());
});

test('updates retain session ownership and filter event identity and plan identity',async()=>{
  const client=fakeClient(),store=createStore(client,'current-user');
  await store.updatePlan('plan',{name:'新名稱',user_id:'other'});
  await store.updateEvent('plan','event',{name:'事件',user_id:'other',plan_id:'other-plan'});
  for(const call of client.calls){
    assert.equal(call.steps.find(step=>step[0]==='update')[1].user_id,'current-user');
    assert.ok(call.steps.some(step=>step[0]==='eq'&&step[1]==='user_id'&&step[2]==='current-user'));
    assert.ok(call.steps.some(step=>step[0]==='eq'&&step[1]==='id'));
  }
  assert.equal(client.calls[1].steps.find(step=>step[0]==='update')[1].plan_id,'plan');
  assert.ok(client.calls[1].steps.some(step=>step[0]==='eq'&&step[1]==='plan_id'&&step[2]==='plan'));
});

test('update errors are visible to page actions rather than swallowed',async()=>{
  const store=createStore(fakeClient(null,{message:'修改失敗'}),'current-user');
  await assert.rejects(()=>store.updatePlan('plan',{name:'新名稱'}),/修改失敗/);
  await assert.rejects(()=>store.updateEvent('plan','event',{name:'新事件'}),/修改失敗/);
});

test('legacy planner only redirects and new pages pin shared libraries',()=>{
  const read=name=>fs.readFileSync(path.join(__dirname,`../static/${name}.html`),'utf8');
  assert.match(read('planner'),/url=\/login.html/);
  assert.doesNotMatch(read('planner'),/<form|planner\.js/);
  for(const page of ['login','onboarding','dashboard','plan','profile']){
    const html=read(page);assert.match(html,/lang="zh-Hant"/);assert.match(html,/supabase-js@2\.45\.4/);
    assert.match(html,/shell\.css/);assert.match(html,/shell\.js/);assert.match(html,/id="pageError"/);
  }
  for(const page of ['dashboard','plan'])assert.match(read(page),/https:\/\/cdn\.jsdelivr\.net\/npm\/chart\.js@4\.4\.8\/dist\/chart\.umd\.min\.js/);
});

test('plan results lead with a conclusion, then the explanation, and fold the full number list',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const results=html.slice(html.indexOf('id="simulationResults"'));
  const at=id=>results.indexOf(`id="${id}"`);
  assert.ok(at('conclusion')>=0&&at('conclusion')<at('explanationSection'));
  assert.ok(at('explanationSection')<at('bandHeading'));
  const details=results.slice(results.indexOf('<details id="allMetrics"'),results.indexOf('id="assumptionsPanel"'));
  for(const id of ['minimumCash','cashShortfall','netWorthP50','realNetWorthP50'])assert.match(details,new RegExp(`id="${id}"`));
  assert.match(results,/不是預測|conclusionCaveat/);
});

test('long actions report progress and failures next to their own button and hand focus on',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const shell=fs.readFileSync(path.join(__dirname,'../static/shell.js'),'utf8');
  const sim=html.slice(html.indexOf('id="simulationForm"'),html.indexOf('id="simulationResults"'));
  assert.ok(sim.indexOf('type="submit">執行模擬')<sim.indexOf('id="simulationStatus"')&&sim.indexOf('id="simulationStatus"')<sim.indexOf('id="simulationError"'));
  assert.match(html,/id="simulationError" class="error" role="alert" hidden/);
  assert.match(html,/id="explanationStatus" class="run-status" role="status"/);
  assert.match(html,/id="explanationError" class="error" role="alert" hidden/);
  assert.doesNotMatch(page,/S\.status\('(正在計算|模擬完成|正在產生說明|說明已產生)/);
  assert.match(page,/return \$\('conclusionHeading'\);/);
  assert.match(page,/scope:'simulationPanel',errorId:'simulationError'/);
  assert.match(shell,/next instanceof root\.Element\?next:focused/);
  assert.match(shell,/area\.setAttribute\('aria-busy','true'\)/);
});

test('plan page copy avoids internal jargon and explains sign and default wording',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const visible=html.replace(/<script[\s\S]*?<\/script>/g,'');
  assert.doesNotMatch(visible,/後端|Monte Carlo|確定性模擬|亂數種子|（支出為負）/);
  assert.doesNotMatch(page,/後端/);
  assert.equal(visible.match(/留空使用系統預設值/g).length,3);
  assert.match(visible,/一次性金額（元）/);
  assert.match(visible,/每月金額（元）/);
  assert.equal(visible.match(/淨資產＝/g).length,1);
  const method=visible.slice(visible.indexOf('class="method-details"'));
  assert.ok(method.indexOf('id="shortfallDefinition"')>0&&method.indexOf('id="samplingNote"')>0);
});

test('plan page type, contrast and shape roles are defined once and the answer is the largest thing',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../static/shell.css'),'utf8');
  const luminance=hex=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.03928?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2];};
  const ratio=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
  const muted=css.match(/body\.fw \{[^}]*--muted:(#[0-9a-f]{6})/i)[1];
  assert.ok(ratio(muted,'#f6f8fb')>=4.5,`muted ${muted} must reach 4.5:1 on the page background`);
  const field=css.match(/body\.fw \{[^}]*--field-border:(#[0-9a-f]{6})/i)[1];
  assert.ok(ratio(field,'#ffffff')>=3,`field border ${field} must reach 3:1 on the white card`);
  assert.match(css,/\.fw input:not\(:focus\),\.fw select:not\(:focus\),\.fw textarea:not\(:focus\) \{ border-color:var\(--field-border\)/);
  assert.doesNotMatch(css,/border-left\s*:\s*[2-9]px|border-right\s*:\s*[2-9]px/);
  assert.doesNotMatch(css,/border-radius:\s*(7|9|14)px/);
  assert.match(css,/\.fw button \{ min-height:44px/);
  const clampMin=selector=>Number(css.slice(css.indexOf(selector)).match(/font-size:clamp\((\d+)px/)[1]);
  assert.ok(clampMin('.fw .conclusion-headline')>=24);
  assert.ok(clampMin('.fw .conclusion-facts strong')>=26);
  assert.doesNotMatch(css,/font-size:1[0-3]px/);
});

test('stale errors are cleared when the inputs change or a new run starts, and both simulation kinds are explained where first charted',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const clear=page.slice(page.indexOf('function clearExplanation'),page.indexOf('function invalidate'));
  assert.match(clear,/\$\('explanationError'\)\.hidden=true/);
  const inv=page.slice(page.indexOf('function invalidate'),page.indexOf('function renderExplanation'));
  assert.match(inv,/\$\('simulationError'\)\.hidden=true/);
  assert.match(inv,/clearExplanation\(\)/);
  assert.match(html,/從台灣歷史資料隨機抽 300 次；相同輸入每次得到相同結果/);
  assert.match(html,/通膨和報酬各用一個固定數字/);
});

test('one plan holds one event: the copy says so and the optional vehicle costs sit behind one disclosure',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const shell=fs.readFileSync(path.join(__dirname,'../static/shell.js'),'utf8');
  for(const text of [html,page,shell])assert.doesNotMatch(text,/更多事件|事件時間軸|新增第一筆|想先加入什麼事件/);
  assert.match(shell,/一個計畫放一個事件/);
  const details=html.slice(html.indexOf('id="vehicleOptionalCosts"'),html.indexOf('</details>',html.indexOf('id="vehicleOptionalCosts"')));
  assert.match(html,/<details id="vehicleOptionalCosts" class="advanced-fields" data-vehicle-field data-vehicle-step="3" hidden>/);
  for(const name of ['annual_maintenance_budget','monthly_fuel_or_energy','annual_depreciation_rate'])assert.match(details,new RegExp(`name="${name}"`));
  assert.match(page,/vehicleOptionalCosts'\)\.open=\[/);
  assert.match(page,/vehicleOptionalCosts'\)\.addEventListener\('invalid'/);
});

test('shell.css braces are balanced and wide numbers wrap by width instead of splitting mid-number',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../static/shell.css'),'utf8');
  assert.equal(css.split('{').length,css.split('}').length);
  assert.match(css,/\.fw \.conclusion-facts \{[^}]*repeat\(auto-fit,minmax\(min\(100%,270px\)/);
  assert.match(css,/\.fw \.metric-table strong \{[^}]*white-space:nowrap/);
  // style.css gives every table min-width:720px and 13px text; the result tables must undo both.
  assert.match(css,/\.fw \.metric-table \{[^}]*min-width:0;[^}]*font-size:16px/);
  assert.match(css,/\.fw \.metric-table th \{ font-size:16px; \}/);
});

test('plan page controls reach 44px and small text reaches 16px',()=>{
  const css=fs.readFileSync(path.join(__dirname,'../static/shell.css'),'utf8');
  assert.match(css,/\.fw input,\.fw select \{[^}]*min-height:44px/);
  assert.match(css,/\.fw select \{ min-height:44px/);
  assert.match(css,/\.fw small \{ font-size:16px; \}/);
  assert.match(css,/body\.fw \{[^}]*font-size:18px/);
  assert.match(css,/\.fw \.assumptions summary,\.fw \.method-details summary,\.fw \.advanced-fields summary,\.fw \.plan-settings summary \{ min-height:44px/);
  assert.match(css,/\.fw \.shell-sidebar nav a \{ min-height:44px/);
  assert.match(css,/@media \(max-width:1180px\) \{\s*\.fw \.metric-table thead \{ position:absolute/);
  assert.match(css,/\.fw \.metric-table td::before \{ content:attr\(data-label\)/);
});

test('the answer shows what the event changed and offers a way back to the event',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const card=html.slice(html.indexOf('id="conclusion"'),html.indexOf('id="explanationSection"'));
  assert.ok(card.indexOf('id="conclusionFacts"')<card.indexOf('id="conclusionCompare"')&&card.indexOf('id="conclusionCompare"')<card.indexOf('id="conclusionCaveat"'));
  assert.match(card,/id="conclusionAction"[^>]*hidden><a href="#eventsHeading">/);
  assert.match(html,/id="eventsHeading" tabindex="-1"/);
  assert.match(page,/prepareSimulation\(ctx,\[\],months,startPeriod\)/);
  assert.match(page,/\.catch\(\(\)=>null\)/);
  assert.match(page,/\$\('conclusionAction'\)\.hidden = view\.tone === 'calm'/);
});

test('the cash chart comes before the net worth range and each chart names its model',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const at=id=>html.indexOf(`id="${id}"`);
  assert.ok(at('conclusion')<at('splitHeading')&&at('splitHeading')<at('bandHeading')&&at('bandHeading')<at('allMetrics'));
  assert.match(html,/id="splitHeading">現金、投資與淨資產（固定值模擬）/);
  assert.match(html,/id="bandHeading">淨資產可能範圍（隨機模擬）/);
  assert.doesNotMatch(html.replace(/<script[\s\S]*?<\/script>/g,''),/平均情況|歷史平均報酬/);
  assert.equal(html.match(/淨資產＝/g).length,1);
});

test('months are picked and income or expense is chosen instead of typing a minus sign',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  for(const name of ['start_period','end_period'])assert.match(html,new RegExp(`name="${name}" type="month"`));
  assert.match(html,/id="startPeriod" type="month"/);
  assert.doesNotMatch(html,/min="-\d/);
  for(const key of ['amount','monthly_amount']){
    assert.match(html,new RegExp(`name="${key}_direction"`));
    assert.match(html,new RegExp(`name="${key}" type="number" min="0"`));
    assert.ok(page.includes(`signed('${key}')`));
  }
  assert.match(page,/label\.querySelectorAll\('input,select'\)/);
  assert.match(page,/model\.splitAmount\(stored\)/);
});


test('buying a car is entered in three validated steps; other events show their fields at once',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const css=fs.readFileSync(path.join(__dirname,'../static/shell.css'),'utf8');
  const form=html.slice(html.indexOf('id="eventForm"'),html.indexOf('</form>',html.indexOf('id="eventForm"')));
  const owner=name=>{const at=form.indexOf(`name="${name}"`);return Number(form.slice(form.lastIndexOf('<label',at),at).match(/data-vehicle-step="(\d)"/)?.[1]);};
  for(const name of ['start_period','vehicle_catalog_id','purchase_price','displacement_cc','fuel_type'])assert.equal(owner(name),1,name);
  for(const name of ['payment_method','down_payment','loan_term_months','annual_interest_rate'])assert.equal(owner(name),2,name);
  for(const id of ['vehicleOptionalCosts','vehicleParkingSection','vehicleFeesSection'])assert.match(form,new RegExp(`id="${id}"[^>]*data-vehicle-step="3"`));
  assert.match(form,/id="vehicleSteps" class="vehicle-steps"[^>]*hidden/);
  assert.equal((form.match(/data-step-button="\d"/g)||[]).length,3);
  assert.match(form,/id="vehiclePrev" type="button" hidden/);
  assert.match(form,/id="vehicleNext" class="primary" type="button" hidden/);
  // The current step lives on the form under its own name so it cannot match every field as a "step 1" ancestor.
  assert.match(page,/form\.dataset\.activeStep=String\(vehicleStep\)/);
  assert.doesNotMatch(page,/form\.dataset\.vehicleStep/);
  for(const step of [1,2,3])assert.ok(css.includes(`#eventForm[data-active-step="${step}"] [data-vehicle-step]:not([data-vehicle-step="${step}"])`));
  assert.match(page,/form\.noValidate=active/);
  assert.match(page,/submit',event=>\{[\s\S]*?vehicleStep<3[\s\S]*?firstInvalidStep\(1,3\)/);
  assert.match(page,/vehicleStep=1;\$\('vehicleOptionalCosts'\)\.open=false/);
  assert.match(page,/type\.value=template\.eventType/);
});


test('the plan page leads with the event and the result; renaming and deleting sit last and the page explains itself',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const at=id=>html.indexOf(`id="${id}"`);
  assert.ok(at('eventsHeading')<at('eventEditorPanel')&&at('eventEditorPanel')<at('simulationPanel')&&at('simulationPanel')<at('planSettings'));
  assert.match(html,/<details id="planSettings" class="panel plan-settings"><summary>計畫設定（改名、刪除）<\/summary><form id="planNameForm">/);
  assert.ok(at('planSettings')<html.indexOf('</main>')&&at('planSettings')>at('simulationResults'));
  assert.ok(at('deletePlan')>at('planSettings'));
  assert.match(html,/id="eventLimitNote" class="lede" hidden>一個計畫放一個事件[^<]*<a href="\/dashboard\.html">/);
  assert.match(page,/\$\('eventLimitNote'\)\.hidden=events\.length===0\|\|!!editing/);
  const nav=html.slice(html.indexOf('class="result-nav"'),html.indexOf('</nav>',html.indexOf('class="result-nav"')));
  for(const target of ['splitHeading','bandHeading','assumptionsPanel','qaSection'])assert.ok(nav.includes(`href="#${target}"`),target);
  assert.ok(at('conclusion')<html.indexOf('class="result-nav"')&&html.indexOf('class="result-nav"')<at('explanationSection'));
  assert.match(page,/const hadResults=!\$\('simulationResults'\)\.hidden/);
  assert.match(page,/hadResults\?'計畫或輸入已變更，上一次的結果已清除，請重新執行模擬。':''/);
});

test('every number under "see all numbers" names its simulation, the dashboard uses the same words, and charts use the page font at 14px',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const dashboard=fs.readFileSync(path.join(__dirname,'../static/dashboard.html'),'utf8');
  const charts=fs.readFileSync(path.join(__dirname,'../static/charts.js'),'utf8');
  const all=html.slice(html.indexOf('id="allMetrics"'),html.indexOf('id="assumptionsPanel"'));
  assert.match(all,/「固定值模擬」是單一路線，其餘來自 300 次隨機模擬。較差：20 次有 1 次更低/);
  // Same kind of figure sits in one row; the columns say which simulation each number comes from.
  const [endTable,riskTable]=all.split('<table').slice(1);
  assert.match(endTable,/<thead><tr><th scope="col">項目<\/th><th scope="col">固定值模擬<\/th><th scope="col">較差情況<\/th><th scope="col">一般情況<\/th><th scope="col">順利情況<\/th>/);
  const rows=[...endTable.matchAll(/<tr><th scope="row">([^<]+)<\/th>((?:<td[^>]*>.*?<\/td>){4})<\/tr>/g)];
  assert.deepEqual(rows.map(row=>row[1]),['期末現金','期末投資市值','期末淨資產','期末淨資產（以今日購買力計算）']);
  for(const row of rows)assert.equal((row[2].match(/data-label="(固定值模擬|較差情況|一般情況|順利情況)"/g)||[]).length,4);
  assert.match(riskTable,/<th scope="col">來自<\/th>/);
  const risks=[...riskTable.matchAll(/<th scope="row">([^<]+)<\/th><td data-label="數字"><strong id="(\w+)">—<\/strong><\/td><td data-label="來自">(固定值模擬|隨機模擬)<\/td>/g)];
  assert.deepEqual(risks.map(row=>[row[2],row[3]]),[['minimumCash','固定值模擬'],['minimumCashPeriod','固定值模擬'],['firstNegativePeriod','固定值模擬'],['minimumEmergency','固定值模擬'],['cashShortfall','隨機模擬']]);
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  for(const id of [...all.matchAll(/<strong id="(\w+)"/g)].map(match=>match[1]))assert.ok(page.includes(`'${id}'`)||page.includes(`$('${id}')`),`${id} must be filled by plan-page.js`);
  assert.doesNotMatch(dashboard,/確定性/);
  assert.match(dashboard,/固定報酬率算出的單一路線/);
  assert.match(charts,/size:14/);
  assert.equal((charts.match(/\{font,|ticks:\{font|Font:font/g)||[]).length,5);
});

test('the result area keeps chart text folded, periods unbroken, a caution colour, and a rename shortcut',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../static/plan.html'),'utf8');
  const page=fs.readFileSync(path.join(__dirname,'../static/plan-page.js'),'utf8');
  const css=fs.readFileSync(path.join(__dirname,'../static/shell.css'),'utf8');
  for(const id of ['planChartSummary','bandChartSummary'])assert.match(html,new RegExp(`<details class="chart-text"><summary>用文字看這張圖</summary><div id="${id}" class="chart-summary"></div></details>`));
  assert.match(html,/<p class="assumption-note">淨資產＝現金＋投資市值＋車輛估值－貸款餘額；車輛估值是估算，不是成交價。<\/p>/);
  assert.equal(html.match(/淨資產＝/g).length,1);
  assert.match(page,/function setText\(node,text\)[^\n]*\(\\d\{4\}-\\d\{2\}\)[^\n]*'nowrap'/);
  for(const call of ["setText($('conclusionHeadline'), view.headline)","setText(note, fact.note)","setText(label, fact.label)","setText(compare.querySelector('span'), view.comparison.text)"])assert.ok(page.includes(call),call);
  assert.match(css,/\.fw \.nowrap \{ white-space:nowrap; \}/);
  assert.match(css,/\.fw \.conclusion\[data-tone="caution"\] \.conclusion-headline \{ color:var\(--caution\); \}/);
  const luminance=hex=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.03928?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2];};
  const caution=css.match(/--caution:(#[0-9a-f]{6})/i)[1];
  assert.ok((luminance('#ffffff')+.05)/(luminance(caution)+.05)>=4.5,`caution ${caution} must reach 4.5:1 on white`);
  assert.match(css,/\.fw table \{ min-width:0; \}/);
  assert.match(html,/id="renamePlan"/);
  assert.ok(page.includes("$('renamePlan').addEventListener('click'")&&page.includes("settings.open=true"));
});
