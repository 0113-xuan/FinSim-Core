const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('static/vehicle.html','utf8');
const js=fs.readFileSync('static/vehicle.js','utf8');
const css=fs.readFileSync('static/vehicle.css','utf8');
test('vehicle script parses',()=>assert.doesNotThrow(()=>new vm.Script(js)));

function submitHarness(fetchImpl) {
  const nodes=new Map(),timers=new Map();let submit,timerId=0;
  const $=id=>{if(!nodes.has(id)) nodes.set(id,{hidden:true,disabled:false,textContent:'',checked:id==='includeFinancialProfile'});return nodes.get(id);};
  const context={$ ,form:{addEventListener:(type,handler)=>submit=handler},document:{querySelector:()=>({value:'single'})},
    revision:0,AbortController,TypeError,Number,buildRequest:()=>({scenario:{payload:{}},profile:{salary:50000}}),
    invalidateVehicleAnalysis:()=>{},render:()=>{},setVehicleAnalysisContext:()=>{},renderStandaloneCosts:()=>{},
    fetch:fetchImpl,setTimeout:(callback,delay)=>{timers.set(++timerId,{callback,delay});return timerId;},clearTimeout:id=>timers.delete(id)};
  vm.createContext(context);
  vm.runInContext(js.slice(js.indexOf("form.addEventListener('submit'"),js.indexOf("$('includeFinancialProfile').addEventListener")),context);
  return {$,timers,submit:()=>submit({preventDefault(){}})};
}

test('calculation shows progress and uses a 30-second deadline',async()=>{
  let finish;
  const h=submitHarness(()=>new Promise(resolve=>finish=resolve));
  const pending=h.submit();
  assert.equal(h.$('submitDecision').disabled,true);
  assert.deepEqual([...h.timers.values()].map(t=>t.delay),[30000,10000]);
  [...h.timers.values()].find(t=>t.delay===10000).callback();
  assert.match(h.$('status').textContent,/仍在計算/);
  finish({ok:true,status:200,json:async()=>({})});await pending;
  assert.equal(h.$('status').textContent,'評估完成');
  assert.equal(h.$('submitDecision').disabled,false);
  assert.equal(h.timers.size,0);
});

test('timeout restores retry controls and preserves submitted profile',async()=>{
  let submitted;
  const h=submitHarness((url,options)=>{submitted=JSON.parse(options.body);return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error(),{name:'AbortError'}))));});
  const pending=h.submit();
  [...h.timers.values()].find(t=>t.delay===30000).callback();await pending;
  assert.match(h.$('error').textContent,/30 秒/);
  assert.match(h.$('error').textContent,/資料仍保留/);
  assert.equal(submitted.profile.salary,50000);
  assert.equal(h.$('submitDecision').disabled,false);
  assert.equal(h.timers.size,0);
});

test('gateway failure has a controlled message even for non-JSON responses',async()=>{
  const h=submitHarness(async()=>({status:503,json:async()=>{throw new SyntaxError('HTML');}}));
  await h.submit();
  assert.match(h.$('error').textContent,/伺服器暫時忙碌/);
  assert.equal(h.$('submitDecision').disabled,false);
  assert.equal(h.timers.size,0);
});

test('headline currency rounds to hundreds while exact values remain available',()=>{
  const context={Intl};vm.createContext(context);
  vm.runInContext(js.slice(js.indexOf('const exactMoney ='),js.indexOf('const form ='))+';this.money=money;this.exactMoney=exactMoney;',context);
  assert.equal(context.money(8789.05),'約 NT$8,800');
  assert.equal(context.money(-20552.52),'約 -NT$20,600');
  assert.equal(context.money(0),'NT$0');
  assert.equal(context.money(-.05),'-NT$0.05');
  assert.equal(context.exactMoney(8789.05),'NT$8,789.05');
});

test('standalone mode disables financial requirements and personal mode restores values',()=>{
  const nodes={},$=id=>nodes[id] ||= {checked:false,querySelectorAll(){return this.inputs || [];}};
  const salary={disabled:false,value:'60000'};
  $('sharedFinancialProfile').inputs=[salary];
  const label={hidden:false},rate={disabled:false,closest:()=>label};
  let compare=false;
  const context={$ ,form:{elements:{inflation_rate:rate}},document:{querySelector:()=>({value:compare?'compare':'single'})}};
  vm.createContext(context);
  vm.runInContext(js.slice(js.indexOf('function syncFinancialProfile()'),js.indexOf('function renderStandaloneCosts(')),context);
  context.syncFinancialProfile();
  assert.equal(salary.disabled,true);assert.equal($('sharedFinancialProfile').hidden,true);
  assert.equal($('submitDecision').textContent,'計算單車成本');
  $('includeFinancialProfile').checked=true;context.syncFinancialProfile();
  assert.equal(salary.disabled,false);assert.equal(salary.value,'60000');
  $('includeFinancialProfile').checked=false;compare=true;context.syncFinancialProfile();
  assert.equal(salary.disabled,false);assert.equal($('singleModeOptions').hidden,true);
});

test('cash chart is removed and loan summary precedes ownership and sensitivity',()=>{
  assert.doesNotMatch(html,/id="cashChart"|id="chartUnavailable"|現金餘額走勢/);
  assert.doesNotMatch(js,/cashChart|chartUnavailable|new Chart/);
  assert.ok(html.indexOf('id="loanSummary"')<html.indexOf('id="ownershipCosts"'));
  assert.ok(html.indexOf('id="loanSummary"')<html.indexOf('id="sensitivityPanel"'));
});

test('sensitivity is expanded and has a prominent primary action',()=>{
  assert.match(html,/<details id="sensitivityPanel" open>/);
  assert.match(html,/id="runSensitivity" class="primary"/);
  assert.match(css,/#sensitivityPanel > summary \{ font-size:22px/);
});

test('key result metrics have framed emphasis without hiding failure labels',()=>{
  assert.match(css,/\.result-overview > div \{[^}]*border-radius:8px/);
  assert.match(css,/#financialCompareScores \.cost-score \{[^}]*background:#203b35/);
  assert.match(css,/result-status\[data-state="failed"\] \{ color:#ffd3cc/);
  assert.match(css,/\.risk-headline\[data-state="failed"\] \{ background:#fff1ef/);
});

test('manual custom entry and validation feedback stay available',()=>{
  assert.match(html,/id="chooseCustomVehicle"/);
  assert.match(html,/id="customVehicleName"/);
  assert.match(js,/form.addEventListener\('invalid'/);
  assert.match(js,/還不能評估，請檢查/);
  assert.match(js,/資料已修改，請再次勾選確認後評估/);
});

test('monthly net burden leads the result with visible risk and unique targets',()=>{
  const overview=html.slice(html.indexOf('aria-label="購車重點"'),html.indexOf('id="ownershipCosts"'));
  assert.ok(overview.indexOf('id="ownershipNet"')<overview.indexOf('id="overviewSurplus"'));
  assert.match(overview,/id="riskHeadline"/);
  for(const id of ['ownershipNet','ownershipNetNote','overviewLimit','riskHeadline']) assert.equal((html.match(new RegExp(`id="${id}"`,'g'))||[]).length,1);
  assert.match(js,/不代表沒有風險/);
});

test('duplicate assumption calibration section and render targets are removed',()=>{
  assert.doesNotMatch(html,/假設版本與校準狀態|assumptionRecords/);
  assert.doesNotMatch(js,/assumptionRecords/);
  assert.doesNotMatch(html,/假設、來源與計算定義/);
});

test('removed source section has no stale rendering references',()=>{
  assert.doesNotMatch(html,/id="sources"|id="definitions"/);
  assert.doesNotMatch(js,/renderSystemSources|row\('sources'|\$\('definitions'\)/);
});

test('loan summary replaces the comparison table with two visible engine values',()=>{
  const block=html.slice(html.indexOf('<section id="loanSummary"'),html.indexOf('</section>',html.indexOf('<section id="loanSummary"')));
  assert.equal((block.match(/<dd /g)||[]).length,2);
  assert.doesNotMatch(block,/<details|每月結餘|最低現金|預備金/);
  assert.doesNotMatch(html,/購車前後完整比較|id="metrics"/);
  assert.match(js,/\$\('loanMonthly'\)\.textContent=money\(result.scenario.monthly_loan_payment\)/);
  assert.match(js,/\$\('loanTotalInterest'\)\.textContent=money\(result.scenario.total_loan_interest\)/);
});

test('all result reset targets exist after monthly details removal',()=>{
  const list=js.match(/for\(const id of (\[[^\]]+\])\) \$\(id\)\.replaceChildren/)[1];
  for(const id of vm.runInNewContext(list)) assert.ok(html.includes(`id="${id}"`),`Missing result target: ${id}`);
  assert.doesNotMatch(js,/cashRows/);
  assert.doesNotMatch(html,/每月現金明細/);
});
test('untouched displayed assumptions are sent with their sources',()=>{
  const values={salary:'60000',balance:'600000',fixed_expense:'15000',variable_expense:'10000',required_monthly_debt:'2000',
    raise_rate:'0',inflation_rate:'0.02',payment_method:'financed',purchase_price:'650000',down_payment:'150000',loan_term_months:'60',annual_interest_rate:'3',
    annual_insurance:'20000',annual_tax:'12000',annual_maintenance_budget:'18000',monthly_fuel_or_energy:'3000',monthly_parking:'2000',monthly_transportation_offset:'0',
    minimum_emergency_fund_months:'3',minimum_cash_balance:'0',minimum_monthly_surplus:'5000',start_period:'2026-09',target_period:'2026-10'};
  const elements=Object.fromEntries(Object.keys(values).map(k=>[k,{dataset:{source:'system_assumption'}}]));
  elements.fixed_expense_inflates={checked:false};
  const context={form:{elements,querySelectorAll:()=>[]},FormData:class {get(k){return values[k];}}};
  vm.createContext(context);
  vm.runInContext(js.slice(js.indexOf('function buildRequest()'),js.indexOf("form.elements.payment_method.addEventListener")),context);
  const result=JSON.parse(JSON.stringify(context.buildRequest()));
  assert.deepEqual(result.constraints,{minimum_emergency_fund_months:3,minimum_cash_balance:0,minimum_monthly_surplus:5000});
  assert.equal(result.profile.raise_rate,0);
  assert.equal(result.profile.inflation_rate,.02);
  assert.equal(result.assumption_sources.minimum_monthly_surplus,'system_assumption');
  assert.equal(result.scenario.payload.annual_insurance.value,20000);
  values.minimum_monthly_surplus='7000'; elements.minimum_monthly_surplus.dataset.source='user';
  const edited=context.buildRequest();
  assert.equal(edited.constraints.minimum_monthly_surplus,7000);
  assert.equal(edited.assumption_sources.minimum_monthly_surplus,'user');
});
test('sensitivity chart and explicit confirmation are retained',()=>{
  assert.equal((html.match(/id="sensitivityChart"/g)||[]).length,1);
  assert.match(html,/id="reviewed" required/);
});
test('isolated deterministic API with timeout and stale response guard',()=>{
  assert.match(js,/fetch\(personal\?'\/decisions\/vehicle':'\/decisions\/vehicle\/costs'/);
  assert.match(js,/submittedRevision!==revision/);
  assert.match(js,/controller.abort\(\)/);
  assert.doesNotMatch(js,/\/ai\/|\/optimize|\/monte-carlo|\/compare/);
});
test('stress, constraints and mobile table overflow remain visible',()=>{
  for(const id of ['stresses','boundaryChecks']) assert.match(html,new RegExp(`id="${id}"`));
  assert.match(css,/overflow:auto/);
  assert.match(css,/@media\(max-width:760px\)/);
  assert.doesNotMatch(html,/FSI|bankruptcy|advisor score/);
});

test('ownership summary separates monthly, upfront, offset and legacy missing data',()=>{
  const elements=new Map();
  const $=id=>{if(!elements.has(id)) elements.set(id,{hidden:false,textContent:'',replaceChildren(){}});return elements.get(id);};
  const rows=[];
  const context={$,money:v=>String(v),exactMoney:v=>String(v),name:k=>k,renderCostStructure:()=>{},sourceLabels:{user_provided:'使用者提供'},row:(id,values)=>rows.push(values)};
  vm.createContext(context);
  vm.runInContext(js.slice(js.indexOf('function renderOwnershipCosts('),js.indexOf('function buildRequest()')),context);
  context.renderOwnershipCosts(undefined);
  assert.equal($('ownershipCosts').hidden,true);
  context.renderOwnershipCosts({monthly_ownership:7000,monthly_net_increase:15000,monthly_loan_payment:9000,monthly_offset:1000,one_time_payment:150000,net_cash_outlay:1050000,purchase_period:'2026-10',ownership_months:60,remaining_loan_months:24,loan_payments_total:540000,items:[{key:'monthly_transportation_offset',is_offset:true,monthly_amount:1000,period_total:60000,source:'user_provided'}]});
  assert.equal($('ownershipCosts').hidden,false);
  assert.equal($('ownershipUpfront').textContent,'150000');
  assert.equal($('ownershipNetLabel').textContent,'買車後，每月多花');
  assert.equal($('ownershipNet').textContent,'15000');
  assert.match($('ownershipNetNote').textContent,/養車 7000.*車貸 9000.*原交通費 1000/);
  assert.equal(rows[0][1],'-1000');
  assert.match($('ownershipScope').textContent,/24 期車貸/);
  assert.match($('ownershipScope').textContent,/不再加一次車價/);
  for(const id of elements.keys()) assert.ok(html.includes(`id="${id}"`));
});
