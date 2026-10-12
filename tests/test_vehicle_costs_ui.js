const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const script=fs.readFileSync('static/vehicle-costs.js','utf8');
const html=fs.readFileSync('static/vehicle.html','utf8');
class Element {
  constructor(){this.children=[];this.handlers={};this.dataset={};this.style={};this.value='';this.hidden=false;}
  append(...children){for(const child of children) child.parentElement=this;this.children.push(...children);}
  replaceChildren(){this.children=[];}
  addEventListener(type,handler){this.handlers[type]=handler;}
  setAttribute(){}
  reportValidity(){return true;}
  focus(){}
  scrollIntoView(){}
  insertAdjacentElement(position,element){this.insertions ||= [];this.insertions.push({position,element});}
  querySelectorAll(){return [];}
  querySelector(selector){const key=selector.match(/data-finance="([^"]+)"/)?.[1];return this.children.flatMap(c=>c.children).find(c=>c.dataset.finance===key);}
}
const vehicles=[{id:'first',brand:'Toyota',model:'Cross',trim:'汽油',price_twd:809000,efficiency_km_l:14.3,source_url:'https://example.com/',source_period:'2026-10',checked_on:'2026-10-11'},{id:'second',brand:'Honda',model:'HR-V',trim:'油電',price_twd:899000,efficiency_km_l:23.5,source_url:'https://example.com/',source_period:'2025-06',checked_on:'2026-10-11'}];
const result=()=>({left:{vehicle:vehicles[0],monthly_cost:9000,period_cost:540000,structure:[{key:'annual_tax',monthly_amount:1000,percentage:100,source:'system_assumption'}]},right:{vehicle:vehicles[1],monthly_cost:8000,period_cost:480000,structure:[{key:'annual_tax',monthly_amount:1000,percentage:100,source:'user_provided'}]},ownership_years:5,difference_right_minus_left:{monthly_cost:-1000}});
async function harness(fetchImpl) {
  const nodes={},$=id=>nodes[id] ||= new Element(),modes=[new Element(),new Element()];modes[0].value='single';modes[1].value='compare';
  const form=new Element();form.elements={target_period:{value:'2026-11'},payment_method:{value:'financed'}};
  $('costDistance').value='15000';$('costFuelPrice').value='30';$('costYears').value='5';
  $('costCompareForm').querySelector=selector=>{
    const side=selector.match(/data-side="([^"]+)"/)[1],key=selector.match(/data-budget="([^"]+)"/)[1];
    return $(side+'Budgets').children.flatMap(label=>label.children).find(child=>child.dataset.budget===key);
  };
  const context={$ ,form,vehicleContext:null,singleCostContext:false,syncFinancialProfile:()=>{},name:k=>k,buildRequest:()=>({profile:{salary:60000},constraints:{minimum_monthly_surplus:5000},assumption_sources:{},start_period:'2026-10',scenario:{payload:{monthly_transportation_offset:{value:0,source:'system_assumption'}}}}),document:{createElement:()=>new Element(),querySelectorAll:()=>modes},window:{vehicleCatalogReady:Promise.resolve(vehicles),vehicleAssumptionsReady:Promise.resolve(['annual_insurance','annual_tax','annual_maintenance_budget','monthly_parking'].map(key=>({key,value:1000})))},money:v=>`NT$${v}`,num:String,sourceLabels:{system_assumption:'系統假設',user_provided:'使用者提供'},AbortController,setTimeout,clearTimeout,fetch:fetchImpl || (async()=>({ok:true,json:async()=>result()}))};
  vm.createContext(context);vm.runInContext(script,context);await new Promise(setImmediate);
  return {context,$,modes,form};
}
test('direct car picks share financial profile without old saved A/B controls',async()=>{
  let submitted;
  const {$,modes,form}=await harness(async(url,options)=>{submitted=JSON.parse(options.body);assert.equal(url,'/decisions/vehicle/cost-comparison');return {ok:true,json:async()=>result()};});
  modes[1].handlers.change();assert.equal(form.hidden,false);assert.equal($('singleVehicleFields').hidden,true);assert.equal($('directComparison').hidden,false);
  assert.equal(form.insertions[0].position,'beforebegin');
  assert.equal(form.insertions[0].element,$('directComparison'));
  assert.equal($('singleModeOptions').insertions[0].position,'beforebegin');
  assert.equal($('singleModeOptions').insertions[0].element,$('singleVehicleFields'));
  assert.equal($('costLeft').value,'first');assert.equal($('costRight').value,'second');
  $('compareReviewed').checked=true;await $('costCompareForm').handlers.submit({preventDefault(){}});
  assert.equal(submitted.left.vehicle_id,'first');assert.equal(submitted.right.vehicle_id,'second');
  assert.equal(submitted.left.annual_tax.source,'system_assumption');assert.equal(submitted.profile,undefined);
  assert.equal(submitted.financial_context.profile.salary,60000);
  assert.equal(submitted.left.payment_method,'financed');
  assert.equal($('costCompareScores').children.length,2);assert.equal($('costCompareResults').hidden,false);
  assert.match($('costCompareDifference').textContent,/Honda HR-V 油電.*每月少花 NT\$1000/);
  modes[0].handlers.change();assert.equal(form.hidden,false);
  assert.doesNotMatch(html,/saveVehicleA|compareVehicleAB|方案 A \/ B/);
});
test('cost structure includes explicit amount and share, with safe zero bars',async()=>{
  const {context,$}=await harness();
  context.renderCostStructure($('structure'),[{key:'monthly_fuel_or_energy',monthly_amount:2000,percentage:40,is_offset:false},{key:'annual_tax',monthly_amount:0,percentage:0,is_offset:false},{key:'monthly_transportation_offset',monthly_amount:1000,is_offset:true}]);
  assert.equal($('structure').children.length,2);
  assert.equal($('structure').children[0].children[0].children[1].textContent,'NT$2000 · 40%');
  assert.equal($('structure').children[1].children[1].children[0].style.width,'0%');
  context.renderRunningCostComparison({...result(),difference_right_minus_left:{monthly_cost:0}});
  assert.match($('costCompareDifference').textContent,/相同/);
});

test('financial comparison renders backend values and requires confirmation',async()=>{
  let called=false;
  const {context,$}=await harness(async()=>{called=true;return {ok:true,json:async()=>result()};});
  await $('costCompareForm').handlers.submit({preventDefault(){}});
  assert.equal(called,false);
  const data=result();
  for(const side of ['left','right']) data[side].financial={metrics:{monthly_surplus:12345,minimum_cash_balance:500000,ending_cash:1000000},constraints:[{key:'minimum_cash_balance',passed:false}]};
  data.financial_difference_right_minus_left={monthly_surplus:0};
  context.renderRunningCostComparison(data);
  assert.equal($('financialCompareScores').children.length,2);
  assert.equal($('financialCompareScores').children[0].className,'cost-score');
  assert.equal($('financialCompareScores').children[0].children[2].textContent,'NT$12345');
  assert.match($('financialCompareDifference').textContent,/每月結餘相同/);
});
test('editing a pending comparison cancels and discards late results',async()=>{
  let complete,signal;
  const {$}=await harness(async(url,options)=>{signal=options.signal;return new Promise(resolve=>{complete=resolve;});});
  $('compareReviewed').checked=true;
  const pending=$('costCompareForm').handlers.submit({preventDefault(){}});
  $('costCompareForm').handlers.input({target:$('costDistance')});
  assert.equal(signal.aborted,true);
  complete({ok:true,json:async()=>result()});await pending;
  assert.equal($('costCompareResults').hidden,true);assert.equal($('compareCosts').disabled,false);
});
test('errors never render an empty result and targets match HTML',async()=>{
  const {$}=await harness(async()=>({ok:false,json:async()=>({detail:'車款不支援'})}));
  $('compareReviewed').checked=true;
  await $('costCompareForm').handlers.submit({preventDefault(){}});
  assert.equal($('costCompareResults').hidden,true);assert.equal($('costCompareStatus').textContent,'車款不支援');
  for(const match of script.matchAll(/\$\('([^']+)'\)/g)) assert.ok(html.includes(`id="${match[1]}"`));
  assert.match(html,/資料來源與試算假設/);assert.match(html,/每月養車費/);
});
