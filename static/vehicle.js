/* Typed decision inputs only; financial calculations remain on the backend. */
const labels = {
  salary:'每月收入',balance:'現金與存款',fixed_expense:'每月固定支出',variable_expense:'每月變動支出',required_monthly_debt:'既有每月還款',
  purchase_price:'車價',down_payment:'頭期款',annual_interest_rate:'貸款年利率',loan_term_months:'貸款期數',payment_method:'付款方式',scenario_type:'決策類型',
  annual_insurance:'年度保險（元）',annual_tax:'年度稅費（元）',annual_maintenance_budget:'年度維護預算（元）',monthly_fuel_or_energy:'每月油電（元）',monthly_parking:'每月停車（元）',monthly_transportation_offset:'每月交通抵減（元）',
  raise_rate:'年薪資成長率（小數，0.03 = 3%）',inflation_rate:'年通膨率（小數，0.02 = 2%）',fixed_expense_inflates:'固定支出通膨',
  minimum_emergency_fund_months:'最低預備金（月）',minimum_cash_balance:'最低現金（元）',minimum_monthly_surplus:'最低每月結餘（元）',
  monthly_loan_payment:'每月新車貸',total_interest:'全期利息',loan_principal:'貸款本金',start_period:'基準月份',target_period:'購車月份',horizon_months:'比較期間（月）',annual_insurance_monthly_average:'保險月平均（元）',annual_tax_monthly_average:'稅費月平均（元）',annual_maintenance_budget_monthly_average:'維護月平均（元）'
};
const sourceLabels = {user:'使用者提供',user_provided:'使用者提供',derived:'系統計算',backend_normalized:'系統換算',system_assumption:'系統假設'};
const money = v => v == null ? '不適用' : `${v<0?'-':''}NT$${new Intl.NumberFormat('zh-TW',{maximumFractionDigits:2}).format(Math.abs(v))}`;
const num = v => v == null ? '不適用' : Number(v).toLocaleString('zh-TW',{maximumFractionDigits:2});
const form = document.querySelector('#vehicleForm');
const $ = id => document.getElementById(id);
let chart;
let revision=0;
function row(target, values) {
  const tr = document.createElement('tr');
  values.forEach(v => { const td = document.createElement('td'); td.textContent = v; tr.append(td); });
  $(target).append(tr);
}
function name(key) { return labels[key.replace('profile.','')] || key; }
function sourceValue(key, value) {
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (key === 'payment_method') return value === 'cash' ? '現金' : '貸款';
  if (key === 'scenario_type') return '購車';
  return typeof value === 'number' ? num(value) : String(value);
}
function render(result) {
  for(const id of ['metrics','stresses','sources','cashRows','definitions','boundaryChecks']) $(id).replaceChildren();
  const fields = [['每月結餘','monthly_surplus',money],['最低現金','minimum_cash_balance',money],['最低現金月份','minimum_cash_month',String],['最低預備金月數','minimum_emergency_fund_months',num],['一次性現金需求','one_time_cash_requirement',money],['每月新車貸','monthly_loan_payment',money],['全期貸款利息','total_loan_interest',money]];
  fields.forEach(([label,key,fmt]) => row('metrics',[label,fmt(result.baseline[key]),fmt(result.scenario[key])]));
  row('metrics',['5 年現金差額','—',money(result.five_year_cash_delta)]);
  const failed = result.constraints.filter(c=>!c.passed);
  $('constraintStatus').textContent = failed.length ? `未符合：${failed.map(c=>name(c.key)).join('、')}` : '符合目前設定的三項財務限制。';
  const stressNames = {income_reduction:'購車起收入減少 10%',unemployment:'購車起失業 3 個月',emergency_expense:'購車月突發支出 10 萬',interest_rate:'貸款利率增加 2 個百分點'};
  result.stress_tests.forEach(s=>row('stresses',[stressNames[s.name],money(s.metrics.minimum_cash_balance),s.metrics.minimum_cash_month,num(s.metrics.minimum_emergency_fund_months),money(s.metrics.ending_cash),!s.applicable?'不適用':s.constraints.every(c=>c.passed)?'全部符合':s.constraints.filter(c=>!c.passed).map(c=>name(c.key)).join('、')+'未符合']));
  const limit = result.affordability;
  $('limit').textContent = limit.status === 'bounded' ? `${money(limit.maximum_affordable_vehicle_price)}；再增加 1% 車價將不符合：${limit.binding_constraint.map(name).join('、')}` : limit.status === 'no_feasible_price' ? '目前設定下，沒有符合全部限制的可行車價。' : '搜尋範圍內未找到上限，不宣稱此範圍為最大可負擔車價。';
  limit.constraint_results.forEach(c=>row('boundaryChecks',[name(c.key),num(c.required),num(c.actual),c.passed?'符合':'未符合']));
  result.provenance.forEach(p=>row('sources',[name(p.key),sourceValue(p.key,p.value),sourceLabels[p.source]]));
  result.derived_values.forEach(p=>row('sources',[name(p.field),num(p.value),sourceLabels[p.source] || '系統計算']));
  for(const [key,value] of Object.entries(result.definitions)) { const dt=document.createElement('dt'),dd=document.createElement('dd'); dt.textContent=({monthly_surplus:'每月結餘',minimum_cash:'最低現金',zero_expense_coverage:'零支出',inflation:'通膨規則',annual_costs:'年度成本',cash:'模型範圍'})[key] || key; dd.textContent=value; $('definitions').append(dt,dd); }
  result.timeline.scenario.forEach((r,i)=>row('cashRows',[r.period,money(result.timeline.baseline[i].balance),money(r.balance)]));
  $('decisionResults').hidden=false;
  if(chart) { chart.destroy(); chart=null; }
  const valid=result.timeline.scenario.length && result.timeline.scenario.every(r=>Number.isFinite(r.balance));
  $('chartUnavailable').hidden=Boolean(window.Chart && valid);
  $('cashChart').hidden=!window.Chart || !valid;
  if(window.Chart && valid) {
    const minimum=result.scenario.minimum_cash_month;
    chart=new Chart($('cashChart'),{type:'line',data:{labels:result.timeline.scenario.map(r=>r.period),datasets:[
      {label:'原本生活',data:result.timeline.baseline.map(r=>r.balance),borderColor:'#475569',borderDash:[5,4],pointRadius:0},
      {label:'購車後',data:result.timeline.scenario.map(r=>r.balance),borderColor:'#047857',pointRadius:result.timeline.scenario.map(r=>r.period===minimum?6:0)}
    ]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{onClick:()=>{}}},scales:{y:{title:{display:true,text:'現金（新台幣）'}}}}});
  }
  $('decisionResults').focus();
}
function buildRequest() {
  const data=new FormData(form), value=key=>Number(data.get(key));
  const profile={};
  ['salary','balance','fixed_expense','variable_expense','required_monthly_debt'].forEach(k=>profile[k]=value(k));
  ['raise_rate','inflation_rate'].forEach(k=>{ if(form.elements[k].dataset.source==='user') profile[k]=value(k); });
  profile.fixed_expense_inflates=form.elements.fixed_expense_inflates.checked;
  const sourced=key=>({value:value(key),source:form.elements[key].dataset.source==='system_assumption'?'system_assumption':'user_provided'});
  const payload={scenario_type:'vehicle_purchase',payment_method:data.get('payment_method'),purchase_price:sourced('purchase_price')};
  if(payload.payment_method==='financed') Object.assign(payload,{down_payment:sourced('down_payment'),loan_term_months:value('loan_term_months'),annual_interest_rate:{value:value('annual_interest_rate')/100,source:'user_provided'}});
  ['annual_insurance','annual_tax','annual_maintenance_budget','monthly_fuel_or_energy','monthly_parking','monthly_transportation_offset'].forEach(k=>payload[k]=sourced(k));
  const constraints={};
  ['minimum_emergency_fund_months','minimum_cash_balance','minimum_monthly_surplus'].forEach(k=>{if(form.elements[k].dataset.source==='user')constraints[k]=value(k);});
  return {profile,constraints,start_period:data.get('start_period'),scenario:{scenario_id:'vehicle-decision',scenario_type:'vehicle_purchase',target_period:data.get('target_period'),horizon_months:60,payload}};
}
form.elements.payment_method.addEventListener('change',()=>document.querySelectorAll('.financing').forEach(label=>{label.hidden=form.elements.payment_method.value==='cash'; label.querySelector('input').disabled=label.hidden;}));
form.addEventListener('input',event=>{
  if(event.target.id!=='reviewed') {
    revision++;
    $('reviewed').checked=false;
    if(event.target.dataset.source) {event.target.dataset.source='user'; event.target.parentElement.querySelector('small').textContent='使用者修改';}
    $('decisionResults').hidden=true;
  }
});
form.addEventListener('submit',async event=>{
  event.preventDefault(); $('error').hidden=true; $('submitDecision').disabled=true; $('status').textContent='計算中…';
  const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),30000);
  const submittedRevision=revision;
  try {
    const response=await fetch('/decisions/vehicle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(buildRequest()),signal:controller.signal});
    const result=await response.json();
    if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'請檢查日期、金額與貸款條件。');
    if(submittedRevision!==revision) { $('status').textContent='資料已修改，請重新確認並評估。'; return; }
    render(result); $('status').textContent='評估完成';
  } catch(error) { $('error').hidden=false; $('error').textContent=error.name==='AbortError'?'計算逾時，資料仍保留，請再試一次。':error.message; $('status').textContent='未完成'; }
  finally { clearTimeout(timeout); $('submitDecision').disabled=false; }
});
(async()=>{
  const date=new Date(), month=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
  form.elements.start_period.value=month(date);
  form.elements.target_period.value=month(new Date(date.getFullYear(),date.getMonth()+1,1));
  try {
    const response=await fetch('/decisions/vehicle/assumptions'); if(!response.ok) throw new Error('無法讀取假設，請重新整理。');
    for(const a of await response.json()) {
      const label=document.createElement('label'),input=document.createElement('input'),source=document.createElement('small');
      label.append(document.createTextNode(labels[a.key])); input.name=a.key; input.type='number'; input.value=a.value; input.min=a.key==='raise_rate'?'-.5':'0'; input.step='any'; input.required=true; input.dataset.source='system_assumption'; source.textContent='系統假設'; label.append(input,source);
      $(a.key.startsWith('minimum_')?'constraintFields':'assumptionFields').append(label);
    }
    $('submitDecision').disabled=false;
  } catch(error) { $('error').hidden=false; $('error').textContent=error.message; }
})();
