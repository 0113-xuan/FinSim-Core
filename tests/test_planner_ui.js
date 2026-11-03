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
  assert.match(html,/現金不足時也不會自動賣出/);
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
