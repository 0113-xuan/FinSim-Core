/* Shared cost structure rendering; all amounts and percentages come from the backend. */
const runningCostLabels={annual_insurance:'保險',annual_tax:'稅費',annual_maintenance_budget:'維修',monthly_fuel_or_energy:'油費',monthly_parking:'停車'};
function renderCostStructure(target,items) {
  target.replaceChildren();
  const order=['monthly_fuel_or_energy','annual_tax','annual_insurance','annual_maintenance_budget','monthly_parking'];
  for(const item of items.filter(item=>!item.is_offset).sort((a,b)=>order.indexOf(a.key)-order.indexOf(b.key))) {
    const block=document.createElement('div');block.className='cost-category';block.dataset.category=item.key;
    const heading=document.createElement('div');heading.className='cost-category-heading';
    const label=document.createElement('span'),amount=document.createElement('span');
    label.textContent=runningCostLabels[item.key] || item.key;
    amount.textContent=`${money(item.monthly_amount)} · ${num(item.percentage ?? 0)}%`;
    heading.append(label,amount);
    const track=document.createElement('div'),fill=document.createElement('span');track.className='cost-track';track.setAttribute('aria-hidden','true');
    fill.style.width=`${Math.max(0,Math.min(100,item.percentage || 0))}%`;track.append(fill);
    block.append(heading,track);target.append(block);
  }
}
function renderRunningCostComparison(result) {
  const scores=$('costCompareScores'),structures=$('costCompareStructure'),sources=$('costCompareSources');
  scores.replaceChildren();structures.replaceChildren();sources.replaceChildren();
  const modelName=vehicle=>`${vehicle.brand} ${vehicle.model} ${vehicle.trim}`.trim();
  $('financialCompareScores').replaceChildren();
  $('financialCompareDifference').textContent='';
  for(const side of ['left','right']) {
    const data=result[side];
    if(!data.financial) continue;
    const column=document.createElement('article'),title=document.createElement('h3');column.className='cost-score';
    title.textContent=modelName(data.vehicle);column.append(title);
    const metrics=data.financial.metrics;
    for(const [label,value] of [['買車後每月剩下',metrics.monthly_surplus],['五年內最低存款',metrics.minimum_cash_balance],['五年後存款',metrics.ending_cash]]) {
      const caption=document.createElement('p'),amount=document.createElement('p');caption.textContent=label;amount.textContent=money(value);
      amount.className=label==='買車後每月剩下'?'cost-score-total':'financial-metric';column.append(caption,amount);
    }
    const status=document.createElement('p'),failed=data.financial.constraints.filter(c=>!c.passed);
    status.textContent=failed.length?`未符合門檻：${failed.map(c=>name(c.key)).join('、')}`:'符合你設定的財務門檻';
    status.className='result-status';status.dataset.state=failed.length?'failed':'passed';column.append(status);
    $('financialCompareScores').append(column);
  }
  if(result.financial_difference_right_minus_left) {
    const delta=result.financial_difference_right_minus_left.monthly_surplus;
    $('financialCompareDifference').textContent=delta===0?'兩款車購買後，每月結餘相同。':`${modelName(result[delta>0?'right':'left'].vehicle)}，買車後每月多剩 ${money(Math.abs(delta))}。不代表最低存款或風險也較好。`;
  }
  for(const side of ['left','right']) {
    const data=result[side],score=document.createElement('article');score.className='cost-score';
    const title=document.createElement('h3');title.textContent=modelName(data.vehicle);
    const label=document.createElement('p');label.textContent='每月持有成本';
    const total=document.createElement('p');total.className='cost-score-total';total.textContent=money(data.monthly_cost);
    const secondary=document.createElement('p');secondary.textContent=`${result.ownership_years} 年養車支出 ${money(data.period_cost)}`;
    score.append(title,label,total,secondary);scores.append(score);
    const column=document.createElement('div'),heading=document.createElement('h4');heading.textContent=modelName(data.vehicle);
    const bars=document.createElement('div');renderCostStructure(bars,data.structure);column.append(heading,bars);structures.append(column);
    const source=document.createElement('div'),sourceTitle=document.createElement('h4'),link=document.createElement('a'),note=document.createElement('p');
    sourceTitle.textContent=modelName(data.vehicle);link.textContent='官方車款資料';link.href=data.vehicle.source_url;link.target='_blank';link.rel='noopener noreferrer';
    note.textContent=data.vehicle.source==='user_provided'?'自訂車款；每月油電由使用者提供，未使用官方車價或油耗。':`參考車價 ${money(data.vehicle.price_twd)}；資料版本 ${data.vehicle.source_period}，核對 ${data.vehicle.checked_on}。油耗 ${data.vehicle.efficiency_km_l} km/L 為實驗室測試值。`;
    source.append(sourceTitle);
    if(data.vehicle.source!=='user_provided') source.append(link);
    source.append(note);
    const list=document.createElement('ul');
    for(const item of data.structure) {
      const li=document.createElement('li');li.textContent=`${runningCostLabels[item.key]}：${money(item.monthly_amount)}／月 · ${sourceLabels[item.source] || '系統計算'}`;list.append(li);
    }
    source.append(list);sources.append(source);
  }
  const delta=result.difference_right_minus_left.monthly_cost;
  $('costCompareDifference').textContent=delta===0?'兩款車的每月持有成本相同。':`${modelName(result[delta>0?'left':'right'].vehicle)}，每月少花 ${money(Math.abs(delta))}`;
  $('costCompareResults').hidden=false;
}
(() => {
  const comparisonForm=$('costCompareForm'),button=$('compareCosts'),status=$('costCompareStatus');
  form.insertAdjacentElement('beforebegin',$('directComparison'));
  $('singleModeOptions').insertAdjacentElement('beforebegin',$('singleVehicleFields'));
  const budgetKeys=['annual_insurance','annual_tax','annual_maintenance_budget','monthly_parking'];
  let catalog=[],controller,revision=0;
  const title=id=>{const vehicle=catalog.find(v=>v.id===$(id).value);return $(id).value==='custom'?($(id==='costLeft'?'leftCustomName':'rightCustomName').value.trim() || '自訂車款'):vehicle?`${vehicle.brand} ${vehicle.model} ${vehicle.trim}`:'選擇車款';};
  function invalidate() {
    revision++;controller?.abort();controller=null;$('costCompareResults').hidden=true;status.textContent='';
    $('compareReviewed').checked=false;
    button.disabled=!catalog.length || !$('leftBudgets').children.length;
  }
  function updateBudgetTitles() {
    $('leftBudgetTitle').textContent=title('costLeft');$('rightBudgetTitle').textContent=title('costRight');
    for(const side of ['left','right']) {
      const custom=$(side==='left'?'costLeft':'costRight').value==='custom';
      $(side+'Custom').hidden=!custom;
      for(const suffix of ['Name','Fuel']) $(side+'Custom'+suffix).disabled=!custom;
      const fields=$(side+'Finance');
      const price=fields.querySelector('[data-finance="purchase_price"]');
      if(price) {
        price.disabled=!custom;price.parentElement.hidden=!custom;
        const cash=fields.querySelector('[data-finance="payment_method"]').value==='cash';
        for(const key of ['down_payment','annual_interest_rate','loan_term_months']) {
          const input=fields.querySelector(`[data-finance="${key}"]`);input.disabled=cash;input.parentElement.hidden=cash;
        }
      }
    }
  }
  for(const id of ['costLeft','costRight']) $(id).addEventListener('change',()=>{
    invalidate();updateBudgetTitles();
    if($(id).value==='custom') $('compareBudgets').open=true;
  });
  document.querySelectorAll('[name="vehicleMode"]').forEach(input=>input.addEventListener('change',()=>{
    const compare=input.value==='compare';
    form.hidden=false;
    for(const id of ['singleVehicleFields','singleAssumptionFields','singleSubmitFields']) $(id).hidden=compare;
    for(const input of $('singleVehicleFields').querySelectorAll('input,select')) input.disabled=compare || (input.closest('.financing') && form.elements.payment_method.value==='cash');
    $('reviewed').disabled=compare;
    syncFinancialProfile();
    $('directComparison').hidden=!compare;$('decisionResults').hidden=compare || !$('includeFinancialProfile').checked || !vehicleContext;
    $('singleCostResults').hidden=compare || $('includeFinancialProfile').checked || !singleCostContext;
    $('error').hidden=true;
    if(!compare && controller) invalidate();
  }));
  comparisonForm.addEventListener('input',event=>{
    if(event.target.id==='compareReviewed') return;
    if(event.target.dataset.source) {event.target.dataset.source='user_provided';event.target.parentElement.querySelector('small').textContent='使用者修改';}
    invalidate();updateBudgetTitles();
  });
  form.addEventListener('input',invalidate);
  comparisonForm.addEventListener('submit',async event=>{
    event.preventDefault();if(!comparisonForm.reportValidity() || controller || button.disabled) return;
    if(!$('compareReviewed').checked) {status.textContent='請先確認財務資料與付款條件。';return;}
    const sharedInputs=Array.from($('sharedFinancialProfile').querySelectorAll('input')).concat(Array.from($('constraintFields').querySelectorAll('input')));
    const invalid=sharedInputs.find(input=>!input.checkValidity());
    if(invalid) {invalid.reportValidity();status.textContent='請先完成上方的財務資料與財務限制。';return;}
    const shared=buildRequest();
    const finance=(side,key)=>$(side+'Finance').querySelector(`[data-finance="${key}"]`);
    const selection=side=>({...($(side==='left'?'costLeft':'costRight').value==='custom'?{custom_vehicle:{name:$(side+'CustomName').value.trim(),monthly_fuel_or_energy:{value:Number($(side+'CustomFuel').value),source:'user_provided'}}}:{vehicle_id:$(side==='left'?'costLeft':'costRight').value}),...Object.fromEntries(budgetKeys.map(key=>{
      const input=comparisonForm.querySelector(`[data-side="${side}"][data-budget="${key}"]`);
      return [key,{value:Number(input.value),source:input.dataset.source}];
    }))});
    const request={left:selection('left'),right:selection('right'),annual_distance_km:Number($('costDistance').value),fuel_price_twd_l:Number($('costFuelPrice').value),ownership_years:Number($('costYears').value),
      financial_context:{profile:shared.profile,constraints:shared.constraints,assumption_sources:shared.assumption_sources,start_period:shared.start_period,target_period:$('comparePurchaseMonth').value,monthly_transportation_offset:shared.scenario.payload.monthly_transportation_offset}};
    for(const side of ['left','right']) {
      if(request[side].custom_vehicle) request[side].custom_vehicle.purchase_price=Number(finance(side,'purchase_price').value);
      request[side].payment_method=finance(side,'payment_method').value;
      if(request[side].payment_method==='financed') {
        request[side].down_payment=Number(finance(side,'down_payment').value);
        request[side].annual_interest_rate=Number(finance(side,'annual_interest_rate').value)/100;
        request[side].loan_term_months=Number(finance(side,'loan_term_months').value);
      }
    }
    const stamp=revision,active=new AbortController();controller=active;button.disabled=true;status.textContent='比較中…';$('costCompareResults').hidden=true;
    const timeout=setTimeout(()=>active.abort(),60000);
    try {
      const response=await fetch('/decisions/vehicle/cost-comparison',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request),signal:active.signal});
      const result=await response.json();if(stamp!==revision) return;
      if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'請檢查車款與費用。');
      renderRunningCostComparison(result);status.textContent='比較完成';
      $('costCompareResults').focus();$('costCompareResults').scrollIntoView({block:'start'});
    } catch(error) {if(stamp===revision) status.textContent=error.name==='AbortError'?'比較逾時，請再試一次。':['TypeError','SyntaxError'].includes(error.name)?'比較暫時無法完成，請確認服務連線後重試。':error.message;}
    finally {clearTimeout(timeout);if(controller===active) {controller=null;button.disabled=false;}}
  });
  Promise.all([window.vehicleCatalogReady,window.vehicleAssumptionsReady]).then(([items,assumptions])=>{
    if(!items?.length || !assumptions) throw new Error('無法載入比較資料，請重新整理；仍可使用單車評估。');
    catalog=items;
    $('comparePurchaseMonth').value=form.elements.target_period.value;
    for(const id of ['costLeft','costRight']) for(const item of items) {
      const option=document.createElement('option');option.value=item.id;option.textContent=`${item.brand} ${item.model} ${item.trim}`;$(id).append(option);
    }
    $('costLeft').value=items[0].id;$('costRight').value=(items[1] || items[0]).id;
    for(const side of ['left','right']) {
      for(const [key,label,value] of [['purchase_price','自訂車價（元）',''],['payment_method','付款方式','financed'],['down_payment','頭期款（元）','0'],['annual_interest_rate','年利率（%）','3'],['loan_term_months','貸款期數（月）','60']]) {
        const wrapper=document.createElement('label'),input=document.createElement(key==='payment_method'?'select':'input');wrapper.textContent=label;
        input.dataset.finance=key;input.required=true;input.value=value;
        if(key==='payment_method') {
          for(const [v,text] of [['financed','貸款'],['cash','現金一次付清']]) {const option=document.createElement('option');option.value=v;option.textContent=text;input.append(option);}
          input.value=value;
        } else {input.type='number';input.min=key==='purchase_price'||key==='loan_term_months'?'1':'0';input.max=key==='annual_interest_rate'?'98':key==='loan_term_months'?'600':'20000000';input.step=key==='loan_term_months'?'1':'any';}
        wrapper.append(input);$(side+'Finance').append(wrapper);
      }
    }
    for(const side of ['left','right']) for(const key of budgetKeys) {
      const assumption=assumptions.find(a=>a.key===key);if(!assumption) throw new Error('費用預算資料不完整，請重新整理。');
      const label=document.createElement('label'),input=document.createElement('input'),source=document.createElement('small');
      label.textContent=`${runningCostLabels[key]}（${key.startsWith('annual_')?'元／年':'元／月'}）`;
      input.type='number';input.min=0;input.max=20000000;input.step='any';input.value=assumption.value;input.required=true;input.dataset.side=side;input.dataset.budget=key;input.dataset.source='system_assumption';
      source.textContent='系統規劃預算';label.append(input,source);$(side+'Budgets').append(label);
    }
    updateBudgetTitles();button.disabled=false;status.textContent='';
  }).catch(error=>{button.disabled=true;status.textContent=error.message;});
})();
