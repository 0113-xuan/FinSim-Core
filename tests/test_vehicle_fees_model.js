const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../static/vehicle-fees-model.js');
const Planner=require('../static/planner-model.js');
const Shell=require('../static/shell-model.js');
const refs=['compulsory','third_party','excess_liability','body_a','body_b','body_c','theft'].map((id,index)=>({id,default:(index+1)*100}));

test('new insurance defaults select compulsory, third party, excess and body B only',()=>{
  const rows=M.restoreInsurance(undefined,refs);
  assert.deepEqual(rows.filter(r=>r.selected).map(r=>r.id),['compulsory','third_party','excess_liability','body_b']);
  assert.deepEqual(M.insuranceSelection(rows),{insurance_items:[{id:'compulsory',amount:100},{id:'third_party',amount:200},{id:'excess_liability',amount:300},{id:'body_b',amount:500}],annual_insurance:1100});
  rows.find(r=>r.id==='body_b').selected=false;
  assert.equal(M.insuranceSelection(rows).annual_insurance,600);
});
test('saved insurance restores selected items and edited amounts without mutating input',()=>{
  const items=[{id:'compulsory',amount:1398},{id:'body_c',amount:10345.67}];
  const before=structuredClone(items),rows=M.restoreInsurance(items,refs);
  assert.deepEqual(M.insuranceSelection(rows),{insurance_items:items,annual_insurance:11743.67});
  assert.equal(rows.find(r=>r.id==='body_b').selected,false);assert.deepEqual(items,before);
});
test('insurance selection rejects missing compulsory, duplicate bodies and invalid amounts',()=>{
  for(const rows of [[],[{id:'compulsory',selected:true,amount:''}],
    [{id:'compulsory',selected:true,amount:100},{id:'body_a',selected:true,amount:1},{id:'body_b',selected:true,amount:1}],
    [{id:'compulsory',selected:true,amount:-1}],[{id:'compulsory',selected:true,amount:NaN}]])assert.throws(()=>M.insuranceSelection(rows));
});
test('saved fee metadata is excluded from vehicle analysis while the confirmed totals are sent',()=>{
  const event={type:'vehicle_purchase',start_period:'2027-03',details:{purchase_price:849000,payment_method:'cash',displacement_cc:1798,fuel_type:'hybrid',insurance_items:[{id:'compulsory',amount:1398}],annual_insurance:1398,annual_tax:11920}};
  const request=Planner.buildVehicleDecisionRequest({event,startPeriod:'2026-11',profile:{monthly_income:80000,fixed_expense:20000,variable_expense:15000,cash_balance:1500000}});
  assert.equal(request.scenario.payload.annual_insurance.value,1398);assert.equal(request.scenario.payload.annual_tax.value,11920);
  for(const key of ['displacement_cc','fuel_type','insurance_items'])assert.equal(Object.hasOwn(request.scenario.payload,key),false);
  assert.match(Shell.eventSummary(event),/保險 NT\$1,398／年、稅費 NT\$11,920／年/);
});
