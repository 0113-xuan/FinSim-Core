/* Typed decision inputs only; financial calculations remain on the backend. */
const labels = {
  salary:'每月收入',balance:'現金與存款',fixed_expense:'每月固定支出',variable_expense:'每月變動支出',required_monthly_debt:'既有每月還款',
  existing_debts:'既有債務明細',
  purchase_price:'車價',down_payment:'頭期款',annual_interest_rate:'貸款年利率',loan_term_months:'貸款期數',payment_method:'付款方式',scenario_type:'決策類型',
  annual_insurance:'年度保險（元）',annual_tax:'年度稅費（元）',annual_maintenance_budget:'年度維護預算（元）',monthly_fuel_or_energy:'每月油電（元）',monthly_parking:'每月停車（元）',monthly_transportation_offset:'每月交通抵減（元）',
  raise_rate:'年薪資成長率（小數，0.03 = 3%）',inflation_rate:'年通膨率（小數，0.02 = 2%）',fixed_expense_inflates:'固定支出通膨',
  minimum_emergency_fund_months:'最低預備金（月）',minimum_cash_balance:'最低現金（元）',minimum_monthly_surplus:'最低每月結餘（元）',
  monthly_loan_payment:'每月新車貸',total_interest:'全期利息',loan_principal:'貸款本金',start_period:'基準月份',target_period:'購車月份',horizon_months:'比較期間（月）',annual_insurance_monthly_average:'保險月平均（元）',annual_tax_monthly_average:'稅費月平均（元）',annual_maintenance_budget_monthly_average:'維護月平均（元）'
};
const sourceLabels = {user:'使用者提供',user_provided:'使用者提供',derived:'系統計算',backend_normalized:'系統換算',system_assumption:'系統假設'};
const exactMoney = v => v == null ? '不適用' : `${v<0?'-':''}NT$${new Intl.NumberFormat('zh-TW',{maximumFractionDigits:2}).format(Math.abs(v))}`;
const money = v => v == null ? '不適用' : Math.abs(v)<100 ? exactMoney(v) : `約 ${exactMoney(Math.sign(v)*Math.round(Math.abs(v)/100)*100)}`;
const num = v => v == null ? '不適用' : Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
const form = document.querySelector('#vehicleForm');
const $ = id => document.getElementById(id);
let revision=0;
let singleCostContext=false;
function syncFinancialProfile() {
  const compare=document.querySelector('[name="vehicleMode"]:checked')?.value==='compare';
  const personal=compare || $('includeFinancialProfile').checked;
  $('singleModeOptions').hidden=compare;
  $('ownershipPeriodControl').hidden=personal;
  $('personalCostNote').hidden=!personal;
  if(form.elements.target_period) form.elements.target_period.closest('label').hidden=!personal;
  for(const id of ['sharedFinancialProfile','financialConstraintSection']) {
    $(id).hidden=!personal;
    for(const input of $(id).querySelectorAll('input')) input.disabled=!personal;
  }
  for(const key of ['raise_rate','inflation_rate','monthly_transportation_offset','fixed_expense_inflates']) {
    const input=form.elements[key];
    if(input) {input.disabled=!personal;input.closest('label').hidden=!personal;}
  }
  $('submitDecision').textContent=personal?'執行 5 年購車評估':'計算單車成本';
}
function renderStandaloneCosts(result) {
  const costs=result.ownership_costs,vehicle=result.selected_vehicle;
  const years=result.ownership_years || 5;
  $('singleCostTitle').textContent=vehicle?`${vehicle.brand} ${vehicle.model} ${vehicle.trim}`:($('customVehicleName').value.trim() || '單車成本評估');
  $('singleCostMonthly').textContent=money(costs.monthly_vehicle_outflow ?? costs.monthly_net_increase);
  $('singleCostMonthlyNote').textContent=`養車 ${money(costs.monthly_ownership)} ＋ 車貸 ${money(costs.monthly_loan_payment)}`;
  $('singleCostUpfront').textContent=money(costs.one_time_payment);
  $('singleCostTotal').textContent=money(costs.net_cash_outlay);
  $('singleCostTotalLabel').textContent=`持有 ${years} 年的現金支出`;
  $('singleCostAnnual').textContent=`每年養車預算 ${money(result.annual_running_cost)}，不含車貸與購車付款。`;
  $('singleCostPeriodHeader').textContent=`${years} 年累計`;
  renderCostStructure($('singleCostStructure'),costs.items);
  $('singleCostRows').replaceChildren();
  row('singleCostRows',['車價',exactMoney(result.purchase_price)]);
  for(const fact of result.loan_details || []) if(['loan_principal','monthly_loan_payment','total_interest'].includes(fact.field)) row('singleCostRows',[name(fact.field),exactMoney(Number(fact.value))]);
  $('singleCostExpenseRows').replaceChildren();
  for(const item of costs.items.filter(i=>!i.is_offset)) row('singleCostExpenseRows',[name(item.key),exactMoney(item.monthly_amount),exactMoney(item.annual_amount),exactMoney(item.period_total),sourceLabels[item.source] || '未提供']);
  row('singleCostRows',[`${years} 年內貸款付款`,exactMoney(costs.loan_payments_total)]);
  if(costs.rounding_adjustment) row('singleCostRows',['逐月扣款取至分的累計差額',exactMoney(costs.rounding_adjustment)]);
  $('singleCostScope').textContent='年度費用按月提列，採固定預算；不含通膨、折舊、殘值或原交通費抵減。未使用個人財務資料，不判定是否負擔得起。' + (costs.remaining_loan_months?` ${years} 年後仍有 ${costs.remaining_loan_months} 期車貸，並非已付清。`:'');
  $('decisionResults').hidden=true;$('singleCostResults').hidden=false;singleCostContext=true;
  $('singleCostResults').focus();$('singleCostResults').scrollIntoView({block:'start'});
}
function row(target, values) {
  const tr = document.createElement('tr');
  values.forEach(v => { const td = document.createElement('td'); td.textContent = v; tr.append(td); });
  $(target).append(tr);
}
function name(key) { return labels[key.replace('profile.','')] || key; }
function stressVerdict(stress) {
  if(stress.applicable === false) return '不適用';
  const failed=stress.constraints.filter(c=>c.applicable !== false && c.passed === false);
  const unknown=stress.constraints.filter(c=>c.applicable !== false && c.passed !== true && c.passed !== false);
  const inapplicable=stress.constraints.filter(c=>c.applicable === false);
  const verdict=stress.passed === true ? '全部符合' : stress.passed === false ? '未符合' : '尚未判定';
  const details=[...failed.map(c=>`${name(c.key)}未符合`),
    ...unknown.map(c=>`${name(c.key)}尚未判定`),
    ...inapplicable.map(c=>`${name(c.key)}：不適用`)];
  return [verdict,...details].join('；');
}
function render(result) {
  renderOwnershipCosts(result.ownership_costs);
  const customName=$('customVehicleName').value.trim();
  $('ownershipVehicle').hidden=!result.selected_vehicle && !customName;
  $('ownershipVehicle').textContent=result.selected_vehicle ? `${result.selected_vehicle.brand} ${result.selected_vehicle.model} ${result.selected_vehicle.trim}；以你確認的金額計算` : customName;
  for(const id of ['stresses','boundaryChecks']) $(id).replaceChildren();
  $('loanMonthly').textContent=money(result.scenario.monthly_loan_payment);
  $('loanTotalInterest').textContent=money(result.scenario.total_loan_interest);
  const failed = result.constraints.filter(c=>!c.passed);
  $('constraintStatus').textContent = failed.length ? `這個方案超出你的財務門檻：${failed.map(c=>name(c.key)).join('、')}` : '這個方案符合你設定的財務門檻。';
  $('constraintStatus').dataset.state = failed.length ? 'failed' : 'passed';
  $('overviewSurplus').textContent = money(result.scenario.monthly_surplus);
  $('overviewSurplusNote').textContent = `不買車時 ${money(result.baseline.monthly_surplus)}／月；不含購車當下付款`;
  $('overviewCash').textContent = money(result.scenario.minimum_cash_balance);
  const coverage = result.scenario.minimum_emergency_fund_months;
  $('overviewCashNote').textContent = coverage == null ? '無必要支出，無法換算預備金月數' : `期間內預備金最低可支應 ${num(coverage)} 個月必要支出`;
  const applicableStresses = result.stress_tests.filter(s=>s.applicable === true);
  const failedStresses = applicableStresses.filter(s=>s.passed === false);
  const unknownStresses = applicableStresses.filter(s=>s.passed !== true && s.passed !== false);
  $('stressSummary').textContent = `${applicableStresses.length} 種適用情況，${failedStresses.length} 種未符合限制` + (unknownStresses.length?`，${unknownStresses.length} 種尚未判定`:'');
  $('riskHeadline').textContent = applicableStresses.length ? (failedStresses.length ? `遇到收入下降等壓力情況，有 ${failedStresses.length}／${applicableStresses.length} 種會超出財務門檻。` : unknownStresses.length ? '部分壓力測試尚未判定，請重新評估。' : `目前 ${applicableStresses.length} 種壓力測試都符合門檻，但不代表沒有風險。`) : '目前沒有適用的壓力測試，不能判定抗風險能力。';
  $('riskHeadline').dataset.state=failedStresses.length?'failed':unknownStresses.length || !applicableStresses.length?'unknown':'passed';
  const stressNames = {income_reduction:'購車起收入減少 10%',unemployment:'購車起失業 3 個月',emergency_expense:'購車月突發支出 10 萬',interest_rate:'貸款利率增加 2 個百分點'};
  result.stress_tests.forEach(s=>row('stresses',[stressNames[s.name],money(s.metrics.minimum_cash_balance),s.metrics.minimum_cash_month,num(s.metrics.minimum_emergency_fund_months),money(s.metrics.ending_cash),stressVerdict(s)]));
  const limit = result.affordability;
  $('overviewLimit').textContent = limit.status === 'bounded' ? money(limit.maximum_affordable_vehicle_price) : limit.status === 'no_feasible_price' ? '無可行車價' : '尚未找到上限';
  $('overviewLimitNote').textContent = limit.status === 'bounded' ? '僅為設定門檻下的計算邊界，不是建議預算，也不代表買得輕鬆或通過所有壓力測試。' : limit.status === 'no_feasible_price' ? '目前條件無法同時符合全部財務限制' : '已達搜尋範圍，無法判定最大可負擔車價';
  $('limit').textContent = limit.status === 'bounded' ? `${money(limit.maximum_affordable_vehicle_price)}；再增加 1% 車價將不符合：${limit.binding_constraint.map(name).join('、')}` : limit.status === 'no_feasible_price' ? '目前設定下，沒有符合全部限制的可行車價。' : '搜尋範圍內未找到上限，不宣稱此範圍為最大可負擔車價。';
  limit.constraint_results.forEach(c=>row('boundaryChecks',[name(c.key),num(c.required),num(c.actual),c.passed?'符合':'未符合']));
  $('decisionResults').hidden=document.querySelector('[name="vehicleMode"]:checked')?.value==='compare';
  if(!$('decisionResults').hidden) {$('decisionResults').focus();$('decisionResults').scrollIntoView({block:'start'});}
}
function renderOwnershipCosts(costs) {
  $('ownershipCosts').hidden=!costs;
  $('ownershipRows').replaceChildren();
  if(!costs) {
    $('ownershipNetLabel').textContent='每月支出變化';
    $('ownershipNet').textContent='未提供';
    $('ownershipNetNote').textContent='本次結果未提供持有成本明細';
    return;
  }
  renderCostStructure($('ownershipStructure'),costs.items);
  $('ownershipMonthly').textContent=money(costs.monthly_ownership);
  const hasOutflow=costs.monthly_vehicle_outflow!=null;
  $('ownershipNetLabel').textContent=hasOutflow?'每月養車＋車貸':costs.monthly_net_increase<0?'買車後，每月少花':'買車後，每月多花';
  $('ownershipNet').textContent=money(hasOutflow?costs.monthly_vehicle_outflow:Math.abs(costs.monthly_net_increase));
  $('ownershipNetNote').textContent=hasOutflow?`養車 ${money(costs.monthly_ownership)} ＋ 車貸 ${money(costs.monthly_loan_payment)}；抵減原交通費後，每月支出變化 ${money(costs.monthly_net_increase)}`:`養車 ${money(costs.monthly_ownership)} ＋ 車貸 ${money(costs.monthly_loan_payment)} − 原交通費 ${money(costs.monthly_offset)}`;
  $('ownershipUpfront').textContent=money(costs.one_time_payment);
  $('ownershipPeriod').textContent=`五年內現金支出 ${money(costs.net_cash_outlay)} · 持有 ${costs.ownership_months} 個月`;
  const costLabels={annual_insurance:'保險',annual_tax:'稅費',annual_maintenance_budget:'維修預算',monthly_fuel_or_energy:'油電',monthly_parking:'停車',monthly_transportation_offset:'原交通費抵減'};
  for(const item of costs.items) row('ownershipRows',[costLabels[item.key] || name(item.key),exactMoney(item.is_offset?-item.monthly_amount:item.monthly_amount),exactMoney(item.is_offset?-item.period_total:item.period_total),sourceLabels[item.source] || '未提供']);
  row('ownershipRows',['新車貸（本金＋利息）',exactMoney(costs.monthly_loan_payment),exactMoney(costs.loan_payments_total),'系統計算']);
  row('ownershipRows',['購車當下付款','一次性',exactMoney(costs.one_time_payment),'系統計算']);
  if(costs.rounding_adjustment) row('ownershipRows',['逐月金額取至分的差額','—',exactMoney(costs.rounding_adjustment),'系統計算']);
  row('ownershipRows',['淨支出合計','—',exactMoney(costs.net_cash_outlay),'系統計算']);
  $('ownershipScope').textContent='合計＝購車付款＋期間內車貸＋養車費－原交通費抵減。已包含車貸利息，不再加一次車價；不含殘值、折舊、未提供的購車附加費或期末未償貸款。' + (costs.remaining_loan_months ? ` 五年後仍有 ${costs.remaining_loan_months} 期車貸，不代表已付清。` : '');
}
function buildRequest() {
  const data=new FormData(form), value=key=>Number(data.get(key));
  const profile={};
  const assumption_sources={};
  ['salary','balance','fixed_expense','variable_expense','required_monthly_debt'].forEach(k=>profile[k]=value(k));
  const debts=Array.from(form.querySelectorAll('.debt-row')).map(r=>({name:r.querySelector('[data-debt="name"]').value.trim(),monthly_payment:Number(r.querySelector('[data-debt="payment"]').value),remaining_months:Number(r.querySelector('[data-debt="months"]').value)}));
  if(debts.length) { profile.existing_debts=debts; profile.required_monthly_debt=0; }
  ['raise_rate','inflation_rate'].forEach(k=>{ profile[k]=value(k); assumption_sources['profile.'+k]=form.elements[k].dataset.source; });
  profile.fixed_expense_inflates=form.elements.fixed_expense_inflates.checked;
  const sourced=key=>({value:value(key),source:({system_assumption:'system_assumption',backend_normalized:'backend_normalized',derived:'derived'})[form.elements[key].dataset.source] || 'user_provided',...(form.elements[key].dataset.evidence?{original_text:form.elements[key].dataset.evidence}:{})});
  const payload={scenario_type:'vehicle_purchase',payment_method:data.get('payment_method'),purchase_price:sourced('purchase_price')};
  if(payload.payment_method==='financed') Object.assign(payload,{down_payment:sourced('down_payment'),loan_term_months:value('loan_term_months'),annual_interest_rate:{value:value('annual_interest_rate')/100,source:'user_provided'}});
  ['annual_insurance','annual_tax','annual_maintenance_budget','monthly_fuel_or_energy','monthly_parking','monthly_transportation_offset'].forEach(k=>payload[k]=sourced(k));
  const constraints={};
  ['minimum_emergency_fund_months','minimum_cash_balance','minimum_monthly_surplus'].forEach(k=>{constraints[k]=value(k); assumption_sources[k]=form.elements[k].dataset.source;});
  const catalogId=form.querySelector?.('#vehicleModel')?.dataset.appliedId;
  return {profile,constraints,assumption_sources,...(catalogId?{vehicle_catalog_id:catalogId}:{}),start_period:data.get('start_period'),scenario:{scenario_id:'vehicle-decision',scenario_type:'vehicle_purchase',target_period:data.get('target_period'),horizon_months:60,payload}};
}
form.elements.payment_method.addEventListener('change',()=>document.querySelectorAll('.financing').forEach(label=>{label.hidden=form.elements.payment_method.value==='cash'; label.querySelector('input').disabled=label.hidden;}));
form.addEventListener('invalid',()=>{
  const missing=Array.from(form.querySelectorAll('input:invalid,select:invalid')).map(input=>input.id==='reviewed'?'確認金額與假設':(input.closest('label')?.firstChild?.textContent || input.name).trim());
  $('error').hidden=false;
  $('error').textContent=`還不能評估，請檢查：${missing.join('、')}`;
  $('status').textContent='請完成必填資料';
},true);
form.addEventListener('input',event=>{
  if(event.target.id!=='reviewed') {
    if($('reviewed').checked) $('status').textContent='資料已修改，請再次勾選確認後評估。';
    revision++;
    $('reviewed').checked=false;
    if(event.target.dataset.source) {event.target.dataset.source='user'; delete event.target.dataset.evidence; event.target.parentElement.querySelector('small').textContent='使用者修改';}
    $('decisionResults').hidden=true;
    $('singleCostResults').hidden=true;singleCostContext=false;
    invalidateVehicleAnalysis();
  }
});
form.addEventListener('submit',async event=>{
  if(document.querySelector('[name="vehicleMode"]:checked')?.value==='compare') {event.preventDefault();$('costCompareForm').requestSubmit();return;}
  event.preventDefault(); $('error').hidden=true; $('submitDecision').disabled=true; $('status').textContent='計算中…';
  const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),30000);
  const submittedRevision=revision;
  const personal=$('includeFinancialProfile').checked;
  const allInputs=buildRequest();
  const submittedRequest=personal?allInputs:{payload:allInputs.scenario.payload,ownership_years:Number($('singleOwnershipYears').value),...(allInputs.vehicle_catalog_id?{vehicle_catalog_id:allInputs.vehicle_catalog_id}:{})};
  invalidateVehicleAnalysis();
  try {
    const response=await fetch(personal?'/decisions/vehicle':'/decisions/vehicle/costs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(submittedRequest),signal:controller.signal});
    const result=await response.json();
    if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'請檢查日期、金額與貸款條件。');
    if(submittedRevision!==revision) { $('status').textContent='資料已修改，請重新確認並評估。'; return; }
    if(personal) {render(result);setVehicleAnalysisContext(submittedRequest);} else renderStandaloneCosts(result);
    $('status').textContent='評估完成';
  } catch(error) { $('error').hidden=false; $('error').textContent=error.name==='AbortError'?'計算逾時，資料仍保留，請再試一次。':error.message; $('status').textContent='未完成'; }
  finally { clearTimeout(timeout); $('submitDecision').disabled=false; }
});
$('includeFinancialProfile').addEventListener('change',syncFinancialProfile);
let previousParking;
$('parkingChoice').addEventListener('change',()=>{
  const input=form.elements.monthly_parking;
  if(!input) return;
  if($('parkingChoice').value==='own') {previousParking=input.value;input.value='0';}
  else if(previousParking!==undefined) {input.value=previousParking;previousParking=undefined;}
  input.dispatchEvent(new Event('input',{bubbles:true}));
  if($('parkingChoice').value!=='own') input.focus();
});
syncFinancialProfile();
window.vehicleAssumptionsReady=(async()=>{
  const date=new Date(), month=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
  form.elements.start_period.value=month(date);
  form.elements.target_period.value=month(new Date(date.getFullYear(),date.getMonth()+1,1));
  try {
    const response=await fetch('/decisions/vehicle/assumptions'); if(!response.ok) throw new Error('無法讀取假設，請重新整理。');
    const assumptions=await response.json();
    for(const a of assumptions) {
      const label=document.createElement('label'),input=document.createElement('input'),source=document.createElement('small');
      label.append(document.createTextNode(labels[a.key])); input.name=a.key; input.type='number'; input.value=a.value; input.min=a.key==='raise_rate'?'-.5':'0'; input.step='any'; input.required=true; input.dataset.source='system_assumption'; source.textContent='系統假設'; label.append(input,source);
      $(a.key.startsWith('minimum_')?'constraintFields':'assumptionFields').append(label);
    }
    syncFinancialProfile();$('submitDecision').disabled=false;
    return assumptions;
  } catch(error) { $('error').hidden=false; $('error').textContent=error.message; return null; }
})();
