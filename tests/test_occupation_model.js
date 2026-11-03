const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../static/occupation-model.js');
const {createStore}=require('../static/shell.js');
const planner=require('../static/planner-model.js');

const reference={available:true,occupation:'industry_20',average_regular_salary:51476,median:null,
  period:'2026-01/2026-06',source:{period_label:'2026 年 1–6 月'}};

test('new job defaults to profile occupation and editing preserves the saved job industry',()=>{
  assert.equal(M.initialOccupation({occupation:'industry_20'}),'industry_20');
  assert.equal(M.initialOccupation({occupation:'industry_20'},{occupation:'industry_90'}),'industry_90');
  assert.equal(M.initialOccupation({occupation:'industry_20'},{}),'');
  assert.equal(M.initialOccupation({}),'');
  assert.equal(M.occupationOptions([{id:'industry_20',name:'製造業'}])[0].value,'');
  assert.match(M.occupationOptions([],'old').at(-1).label,/先前儲存/);
});

test('selecting industry or receiving salary data never fills or replaces the user salary',()=>{
  const original={occupation:'',new_salary:'43210',reference:null};
  const selected=M.chooseOccupation(original,'industry_20');
  const loaded=M.receiveReference(selected,reference);
  assert.equal(selected.new_salary,'43210');assert.equal(loaded.new_salary,'43210');
  assert.equal(original.occupation,'');assert.equal(original.reference,null);
  assert.match(M.referenceText(reference),/同行業平均經常性薪資 NT\$51,476.*2026 年 1–6 月/);
  assert.match(M.taxNote,/稅前.*5–10%/);
  assert.equal(M.applyReference(loaded).new_salary,'51476');
  assert.equal(loaded.new_salary,'43210');
});

test('a late response for a different industry is ignored and cannot be applied',()=>{
  const state=M.chooseOccupation({new_salary:'50000',reference},'industry_90');
  assert.equal(M.receiveReference(state,reference).reference,null);
  assert.throws(()=>M.applyReference(state),/沒有可帶入/);
  assert.throws(()=>M.applyReference({...state,reference}),/沒有可帶入/);
  for(const value of [null,{available:false},{available:true,average_regular_salary:null},{available:true,average_regular_salary:Infinity}])assert.equal(M.canApply(value),false);
  assert.equal(M.referenceText({available:false,note:'請自行填寫'}),'請自行填寫');
});

test('public sector advice does not change loan terms or simulation inputs',()=>{
  assert.equal(M.publicLoanNote('public_sector'),'軍公教可向銀行詢問專案車貸利率。');
  assert.equal(M.publicLoanNote('industry_20'),'');
  const profile={monthly_income:60000,cash_balance:100000,fixed_expense:10000,variable_expense:10000,
    investment_value:0,monthly_investment:0,emergency_target_months:6};
  const input={profile,startPeriod:'2026-11',months:60,events:[{name:'換工作',type:'salary_change',start_period:'2026-12',new_salary:51476}]};
  const expected=planner.buildSimulationRequest(input);
  assert.deepEqual(planner.buildSimulationRequest({...input,profile:{...profile,occupation:'public_sector'},
    events:[{...input.events[0],details:{occupation:'industry_20'}}]}),expected);
});

function clientWith(results){
  const calls=[];
  return {calls,from(table){const call={table,steps:[]};calls.push(call);
    const query={then(resolve,reject){return Promise.resolve(results.shift()).then(resolve,reject);}};
    for(const step of ['select','eq','maybeSingle','upsert','single'])query[step]=(...args)=>{call.steps.push([step,...args]);return query;};return query;
  }};
}
test('profile occupation is selected and saved under the session owner',async()=>{
  const client=clientWith([{data:{occupation:'industry_20'},error:null},{data:{occupation:'industry_90'},error:null}]);
  const store=createStore(client,'owner');
  assert.equal((await store.profile()).occupation,'industry_20');
  await store.saveProfile({occupation:'industry_90',user_id:'wrong'});
  assert.match(client.calls[0].steps.find(s=>s[0]==='select')[1],/city,district,occupation/);
  const body=client.calls[1].steps.find(s=>s[0]==='upsert')[1];assert.equal(body.occupation,'industry_90');assert.equal(body.user_id,'owner');
});

test('missing occupation column retries finances without all optional profile columns',async()=>{
  const client=clientWith([{data:null,error:{code:'PGRST204',message:"Could not find the 'occupation' column in the schema cache"}},
    {data:{monthly_income:70000},error:null}]),warnings=[];
  const store=createStore(client,'owner',{onWarning:message=>warnings.push(message)});
  await store.saveProfile({monthly_income:70000,city:'臺北市',district:'士林區',occupation:'industry_20'});
  assert.equal(store.locationSupported,false);assert.equal(warnings.length,1);
  const body=client.calls[1].steps.find(s=>s[0]==='upsert')[1];
  assert.equal(body.monthly_income,70000);assert.equal(body.user_id,'owner');
  for(const key of ['city','district','occupation'])assert.equal(Object.hasOwn(body,key),false);
});
