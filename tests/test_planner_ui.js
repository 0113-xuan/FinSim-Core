const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createStore,taipeiPeriod} = require('../static/planner.js');

function fakeClient(data = [{id:'row'}], error = null) {
  const calls = [];
  return {calls, from(table) {
    const call = {table, steps:[]}; calls.push(call);
    const builder = {then(resolve,reject) { return Promise.resolve({data,error}).then(resolve,reject); }};
    for (const name of ['select','eq','order','maybeSingle','single','upsert','insert','delete']) {
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
  const html=fs.readFileSync(path.join(__dirname,'../static/planner.html'),'utf8');
  assert.match(html,/@supabase\/supabase-js@2\.45\.4\/dist\/umd\/supabase\.js/);
  assert.match(html,/href="\/style.css"/);
  assert.match(html,/投資市值尚未納入計算；每月投資金額視為現金支出/);
  const eventForm=html.slice(html.indexOf('id="eventForm"'),html.indexOf('</form>',html.indexOf('id="eventForm"')));
  assert.doesNotMatch(eventForm,/vehicle_purchase/);
  for(const type of ['one_time','range','salary_change']) assert.match(eventForm,new RegExp(`value="${type}"`));
});
