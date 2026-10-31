const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../static/planner-model.js');
const profile = {monthly_income:'60000',cash_balance:'900000',fixed_expense:'20000',variable_expense:'10000',
  investment_value:'500000',monthly_investment:'3000',raise_rate:null,emergency_target_months:'6'};
const build = overrides => M.buildSimulationRequest({profile, debts:[],events:[],startPeriod:'2026-11',months:60,...overrides});

test('maps saved profile values and sends the investment account instead of a cash event',()=>{
  const {request,warnings} = build();
  assert.deepEqual(request.profile,{salary:60000,balance:900000,fixed_expense:20000,variable_expense:10000,
    investment_value:500000,monthly_investment:3000,target_emergency_months:6});
  assert.deepEqual(request.events,[]);
  assert.deepEqual(warnings,[]);
  assert.ok(!Object.hasOwn(request.profile,'raise_rate'));
  assert.ok(!Object.hasOwn(request.profile,'inflation_rate'));
});
test('keeps an explicit zero salary raise and zero monthly investment',()=>{
  const {request} = build({profile:{...profile,raise_rate:0,monthly_investment:0}});
  assert.equal(request.profile.raise_rate,0);
  assert.equal(request.profile.monthly_investment,0);
  assert.deepEqual(request.events,[]);
});
test('rejects a missing investment value',()=>{
  assert.throws(()=>build({profile:{...profile,investment_value:''}}),/投資目前市值須填寫有效數字/);
});
test('period tools use inclusive month one and cross year boundaries',()=>{
  assert.equal(M.periodToMonth('2026-11','2026-11'),1);
  assert.equal(M.periodToMonth('2026-11','2027-02'),4);
  assert.equal(M.monthToPeriod('2026-11',4),'2027-02');
  assert.equal(M.periodToMonth('2026-11','2026-10'),0);
  assert.equal(M.monthToPeriod('2026-11',240),'2046-10');
});
test('maps each supported event, keeps signs, and never double counts range amount',()=>{
  const events=[{type:'one_time',name:'支出',start_period:'2027-02',amount:'-10000'},
    {type:'range',name:'租金',start_period:'2026-12',end_period:'2027-02',monthly_amount:'-5000',amount:-5000},
    {type:'range',name:'收入',start_period:'2027-01',end_period:null,monthly_amount:'2000'},
    {type:'salary_change',name:'換工作',start_period:'2027-02',new_salary:'70000'}];
  const {request}=build({profile:{...profile,monthly_investment:0},events});
  assert.deepEqual(request.events,[{type:'one_time',name:'支出',month:4,amount:-10000},
    {type:'range',name:'租金',start_month:2,end_month:4,monthly_amount:-5000},
    {type:'range',name:'收入',start_month:3,end_month:60,monthly_amount:2000},
    {type:'salary_change',name:'換工作',start_month:4,new_salary:70000}]);
  assert.ok(!Object.hasOwn(request.events[1],'amount'));
});
test('warns on early, late, clipped and unsupported events',()=>{
  const {request,warnings}=build({months:12,events:[
    {type:'one_time',name:'太早',start_period:'2026-10',amount:1},
    {type:'one_time',name:'太晚',start_period:'2027-11',amount:1},
    {type:'range',name:'截斷',start_period:'2027-01',end_period:'2028-01',monthly_amount:-1},
    {type:'vehicle_purchase',name:'購車',start_period:'2027-01'}]});
  assert.equal(warnings.length,4);
  for(const [index,reason] of ['早於模擬起始月','晚於模擬期間','截斷','尚不支援購車事件'].entries()) assert.match(warnings[index],new RegExp(reason));
  assert.equal(request.events.at(-1).end_month,12);
});
test('debt cash outflows expire, zero remaining terms are skipped and long terms are clipped',()=>{
  const {request,warnings}=build({months:60,profile:{...profile,monthly_investment:0},debts:[
    {name:'已還清',monthly_payment:1000,remaining_months:0},{name:'短貸',monthly_payment:'2000',remaining_months:5},
    {name:'長貸',monthly_payment:3000,remaining_months:100}]});
  assert.deepEqual(request.events,[{type:'range',name:'短貸',start_month:1,end_month:5,monthly_amount:-2000},
    {type:'range',name:'長貸',start_month:1,end_month:60,monthly_amount:-3000}]);
  assert.equal(warnings.length,2);
});
test('invalid periods and reversed event ranges are reported without mutating input',()=>{
  const input={profile,debts:[],events:[{type:'range',name:'反向',start_period:'2027-01',end_period:'2026-12',monthly_amount:-1},
    {type:'one_time',name:'無效日期',start_period:'2027-13',amount:1}],startPeriod:'2026-11',months:60};
  const original=structuredClone(input), result=M.buildSimulationRequest(input);
  assert.equal(result.warnings.length,2);
  assert.deepEqual(input,original);
  assert.throws(()=>M.monthToPeriod('2026-11',0));
  assert.throws(()=>M.periodToMonth('2026-13','2027-01'));
  assert.throws(()=>build({months:NaN}));
});
