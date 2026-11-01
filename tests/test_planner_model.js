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
    {type:'unknown',name:'不支援',start_period:'2027-01'}]});
  assert.equal(warnings.length,4);
  for(const [index,reason] of ['早於模擬起始月','晚於模擬期間','截斷','不支援的事件類型'].entries()) assert.match(warnings[index],new RegExp(reason));
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

test('vehicle events are returned separately with inclusive dates and unchanged details',()=>{
  const event={type:'vehicle_purchase',name:'買車',start_period:'2027-03',details:{purchase_price:849000,payment_method:'cash'}};
  const original=structuredClone(event);
  const {request,vehicles,warnings}=build({events:[event]});
  assert.deepEqual(vehicles,[{name:'買車',purchase_period:'2027-03',details:event.details}]);
  assert.deepEqual(request.events,[]);
  assert.deepEqual(warnings,[]);
  vehicles[0].details.purchase_price=1;
  assert.deepEqual(event,original);
});

test('vehicle dates at both horizon boundaries are accepted and outside dates are warned',()=>{
  const events=['2026-10','2026-11','2027-10','2027-11'].map(start_period=>({type:'vehicle_purchase',name:'買車',start_period,details:{}}));
  const result=build({months:12,events});
  assert.deepEqual(result.vehicles.map(car=>car.purchase_period),['2026-11','2027-10']);
  assert.equal(result.warnings.length,2);
  assert.match(result.warnings[0],/早於模擬起始月/);
  assert.match(result.warnings[1],/晚於模擬期間/);
  assert.doesNotMatch(result.warnings.join(''),/尚不支援購車事件/);
});

test('vehicle details omit blank optional costs, keep explicit zero and convert percentage to decimal',()=>{
  const details=M.vehicleDetails({purchase_price:'849000',payment_method:'financed',down_payment:'0',
    loan_term_months:'60',annual_interest_rate:'2.5',annual_insurance:'',monthly_parking:'0',vehicle_catalog_id:''});
  assert.deepEqual(details,{purchase_price:849000,payment_method:'financed',down_payment:0,
    loan_term_months:60,annual_interest_rate:.025,monthly_parking:0});
  assert.deepEqual(M.vehicleDetails({purchase_price:'100000',payment_method:'cash',down_payment:'30000',
    loan_term_months:'60',annual_interest_rate:'2.5'}),{purchase_price:100000,payment_method:'cash'});
  assert.throws(()=>M.vehicleDetails({purchase_price:100000,payment_method:'financed'}),/頭期款/);
});

test('vehicle analysis uses saved cash finances and existing debts, excluding investments and other events',()=>{
  const event={type:'vehicle_purchase',start_period:'2027-03',details:{purchase_price:849000,
    payment_method:'financed',down_payment:300000,loan_term_months:60,annual_interest_rate:.025,
    monthly_parking:0,vehicle_catalog_id:'toyota-cross-hybrid-luxury'}};
  const debts=[{name:'學貸',monthly_payment:3000,remaining_months:24,id:'not-for-api'}];
  const request=M.buildVehicleDecisionRequest({profile,debts,event,startPeriod:'2026-11'});
  assert.deepEqual(request.profile,{salary:60000,fixed_expense:20000,variable_expense:10000,
    balance:900000,required_monthly_debt:0,existing_debts:[{name:'學貸',monthly_payment:3000,remaining_months:24}]});
  assert.equal(request.scenario.horizon_months,60);
  assert.equal(request.scenario.target_period,event.start_period);
  assert.equal(request.vehicle_catalog_id,event.details.vehicle_catalog_id);
  assert.equal(request.scenario.payload.loan_term_months,60);
  assert.equal(request.scenario.payload.payment_method,'financed');
  assert.deepEqual(request.scenario.payload.monthly_parking,{value:0,source:'user_provided'});
  assert.deepEqual(request.scenario.payload.purchase_price,{value:849000,source:'user_provided'});
  assert.ok(!Object.hasOwn(request.scenario.payload,'annual_insurance'));
  assert.ok(!Object.hasOwn(request.scenario.payload,'vehicle_catalog_id'));
  const explicit=M.buildVehicleDecisionRequest({profile:{...profile,raise_rate:0},debts,event,startPeriod:'2026-11'});
  assert.equal(explicit.profile.raise_rate,0);
});

test('vehicle analysis respects the existing next-month and 58-month limits',()=>{
  for(const purchase of ['2026-10','2026-11','2031-10','invalid']) assert.ok(M.vehicleAnalysisReason('2026-11',purchase));
  for(const purchase of ['2026-12','2031-09']) assert.equal(M.vehicleAnalysisReason('2026-11',purchase),'');
});
