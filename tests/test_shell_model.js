const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../static/shell-model.js');

test('authentication and network failures have actionable Traditional Chinese text',()=>{
  assert.match(M.errorText({code:'invalid_credentials',message:'Invalid login credentials'}),/電子郵件或密碼不正確/);
  assert.match(M.errorText({code:'email_not_confirmed'}),/確認連結/);
  assert.match(M.errorText(new Error('Failed to fetch')),/確認網路或重新登入/);
  assert.equal(M.errorText(new Error('測試修改失敗')),'測試修改失敗');
});

test('current net worth subtracts all remaining nominal debt payments',()=>{
  assert.deepEqual(M.financialSummary({cash_balance:'900000',investment_value:'100000'},[
    {monthly_payment:'5000',remaining_months:12},{monthly_payment:10000,remaining_months:24},
    {monthly_payment:9999,remaining_months:0}]),
    {cash:900000,investment:100000,assets:1000000,debtTotal:300000,netWorth:700000});
  assert.equal(M.financialSummary({cash_balance:-500,investment_value:0}).netWorth,-500);
});

test('route guards distinguish guest, onboarding, and established user',()=>{
  const session={user:{id:'user'}};
  for(const page of ['dashboard','profile','plan','onboarding'])assert.equal(M.routeFor(page,null,null),'/login.html');
  assert.equal(M.routeFor('login',null,null),null);
  for(const page of ['dashboard','profile','plan','login'])assert.equal(M.routeFor(page,session,null),'/onboarding.html');
  assert.equal(M.routeFor('onboarding',session,null),null);
  assert.equal(M.routeFor('login',session,{}),'/dashboard.html');
  for(const page of ['dashboard','profile','plan'])assert.equal(M.routeFor(page,session,{}),null);
});

test('events sort by YYYY-MM without mutating input and tie-break consistently',()=>{
  const events=[{id:'c',start_period:'2027-02'},{id:'b',start_period:'2026-12'},{id:'a',start_period:'2026-12'}];
  const original=structuredClone(events);
  assert.deepEqual(M.sortEvents(events).map(e=>e.id),['a','b','c']);assert.deepEqual(events,original);
});

test('all four event types have Chinese summaries with explicit zero retained',()=>{
  assert.match(M.eventSummary({type:'one_time',amount:-10000}),/10,000/);
  assert.match(M.eventSummary({type:'range',monthly_amount:0,end_period:'2027-03'}),/每月.*0.*2027-03/);
  assert.match(M.eventSummary({type:'range',monthly_amount:-100}),/模擬結束/);
  assert.match(M.eventSummary({type:'salary_change',new_salary:70000}),/新月薪.*70,000/);
  assert.match(M.eventSummary({type:'vehicle_purchase',details:{purchase_price:849000,payment_method:'financed',loan_term_months:60}}),/849,000.*貸款 60 期/);
  assert.match(M.eventSummary({type:'vehicle_purchase',details:{purchase_price:100000,payment_method:'cash'}}),/現金購買/);
});

test('chart months, multiple event markers and textual extrema use the actual row month',()=>{
  const curve=[{month:1,balance:100,net_worth:200},{month:2,balance:-20,net_worth:160},{month:3,balance:70,net_worth:250}];
  const data=M.chartData(curve,'2026-12',[
    {name:'換工作',start_period:'2027-01'},{name:'買車',start_period:'2027-01'},
    {name:'期間外',start_period:'2027-03'},{name:'早於期間',start_period:'2026-11'}]);
  assert.deepEqual(data.labels,['2026-12','2027-01','2027-02']);
  assert.deepEqual(data.markers.map(m=>m.index),[1,1]);
  assert.equal(data.summary.cash.minimum,-20);assert.equal(data.summary.cash.minimumPeriod,'2027-01');
  assert.equal(data.summary.netWorth.initial,200);assert.equal(data.summary.netWorth.final,250);
});

test('initial chart position is the previous month-end, not the first projected cash balance',()=>{
  const data=M.chartData([{month:1,balance:200,net_worth:400}],'2027-01',[
    {name:'本月購車',start_period:'2027-01'},{name:'舊事件',start_period:'2026-12'}],{cash_balance:100,investment_value:50});
  assert.deepEqual(data.labels,['2026-12','2027-01']);assert.deepEqual(data.cash,[100,200]);assert.deepEqual(data.netWorth,[150,400]);
  assert.deepEqual(data.markers,[{index:1,period:'2027-01',name:'本月購車'}]);
  assert.equal(data.summary.netWorth.minimumPeriod,'2026-12');
  assert.equal(M.chartData([],'2027-01').summary.cash,null);
});
