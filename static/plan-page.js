(function(root) {
  'use strict';
  async function start(ctx) {
    const S=root.FutureWalletShell,M=root.ShellModel,model=root.PlannerModel,E=root.ExplanationModel,T=root.EventTemplates,P=root.EventPicker,$=id=>root.document.getElementById(id),money=M.money;
    function syncEventFields() {
      const type = $('eventForm').elements.type.value;
      for (const label of root.document.querySelectorAll('[data-event-field]')) {
        const key = label.dataset.eventField;
        const visible = type === 'range' ? ['monthly_amount','end_period'].includes(key) : type === 'one_time' ? key === 'amount' : type === 'salary_change' && key === 'new_salary';
        label.hidden = !visible; label.querySelector('input').disabled = !visible;
      }
      for (const label of root.document.querySelectorAll('[data-vehicle-field]')) {
        const visible = type === 'vehicle_purchase' && (label.dataset.vehicleField !== 'financed' || $('eventForm').elements.payment_method.value === 'financed');
        label.hidden = !visible;
        const control = label.querySelector('input,select'); if (control) control.disabled = !visible;
      }
      fees.sync();
    }
    const ownershipLabels = {annual_insurance:'保險',annual_tax:'稅費',annual_maintenance_budget:'保養',monthly_fuel_or_energy:'油電',monthly_parking:'停車',annual_depreciation_rate:'折舊率'};
    let vehicleCatalog = [];
    const fees=root.VehicleFeesForm.create({form:$('eventForm'),isAlive:()=>ctx.alive});
    function syncVehicleSpec(){
      const select=$('eventForm').elements.vehicle_catalog_id;
      const id=select.dataset.pending??select.value;
      fees.spec(vehicleCatalog.find(car=>car.id===id));
    }
    async function loadVehicleMetadata() {
      try {
        const responses = await Promise.all(['/decisions/vehicle/catalog','/decisions/vehicle/assumptions'].map(url=>root.fetch(url)));
        if (responses.some(response=>!response.ok)) throw new Error('載入失敗');
        const [catalog, assumptions] = await Promise.all(responses.map(response=>response.json()));
        if(!ctx.alive)return;
        vehicleCatalog = catalog;
        const select = $('eventForm').elements.vehicle_catalog_id;
        const selection = select.dataset.pending ?? select.value;
        select.replaceChildren();
        for (const car of catalog) {
          const option = root.document.createElement('option'); option.value = car.id;
          option.textContent = `${car.brand} ${car.model} ${car.trim}`; select.append(option);
        }
        const custom = root.document.createElement('option'); custom.value = ''; custom.textContent = '自訂車款'; custom.defaultSelected = true; select.append(custom); select.value = selection;
        for (const key of model.ownershipFields.filter(key=>!['annual_insurance','annual_tax'].includes(key))) {
          const assumption = assumptions.find(item=>item.key === key);
          if (!assumption || !Number.isFinite(Number(assumption.value))) throw new Error('預設值載入不完整');
          $('eventForm').elements.namedItem(key).placeholder = `留空使用預設 ${Number(assumption.value).toLocaleString('zh-TW')}／${key.startsWith('annual_') ? '年' : '月'}`;
        }
        $('vehicleMetadataStatus').textContent = '可修改車價；留空的持有成本於計算時套用預設值。';
        syncVehicleSpec();
      } catch (_) { if(ctx.alive)$('vehicleMetadataStatus').textContent = '車款或預設值載入未完成；可使用自訂車款，留空成本由後端套用預設值。重新整理可重試。'; }
    }

    function renderResults(simulation,mc,converted,startPeriod) {
        const summary = simulation.result.summary;
        $('minimumCash').textContent = money(summary.minimum_cash_balance);
        $('minimumCashPeriod').textContent = model.monthToPeriod(startPeriod, summary.minimum_cash_month);
        $('firstNegativePeriod').textContent = summary.first_negative_cash_month == null ? '未出現' : model.monthToPeriod(startPeriod, summary.first_negative_cash_month);
        $('minimumEmergency').textContent = summary.minimum_emergency_fund_months == null ? '不適用（無必要支出）' : `${Number(summary.minimum_emergency_fund_months).toFixed(2)} 個月`;
        $('endingCash').textContent = money(summary.final_balance);
        $('cashShortfall').textContent = new Intl.NumberFormat('zh-TW', {style:'percent', maximumFractionDigits:2}).format(mc.probability_cash_shortfall);
        for (const [id, key] of [['cashP5','p5'],['cashP50','p50'],['cashP95','p95']]) $(id).textContent = money(mc.percentiles[key]);
        $('shortfallDefinition').textContent = mc.cash_shortfall_definition;
        $('endingInvestment').textContent = money(summary.final_investment_value);
        for (const [id, key] of [['netWorthP5','p5'],['netWorthP50','p50'],['netWorthP95','p95']]) $(id).textContent = money(mc.net_worth_percentiles[key]);
        $('realNetWorthP50').textContent = money(mc.real_net_worth_percentiles.p50);
        $('samplingNote').textContent = mc.sampling_note;
        $('dataSources').replaceChildren(...mc.data_sources.map(source => {
          const li = root.document.createElement('li');
          li.textContent = `資料來源：${source.publisher}「${source.name}」，${source.period_start} 至 ${source.period_end}`;
          return li;
        }));
        $('vehicleResults').hidden = !converted?.vehicles.length;
        $('vehicleSummaries').replaceChildren();
        if (converted) {
          for (const car of converted.vehicles) {
            const section = root.document.createElement('article');
            paragraph(section, `${car.name}｜${model.monthToPeriod(startPeriod, car.purchase_month)}`);
            paragraph(section, `購車當月一次支出：${money(car.one_time_cash)}｜每月車貸：${money(car.monthly_loan_payment)}｜總利息：${money(car.total_loan_interest)}`);
            paragraph(section, `第一年每月持有成本：${money(car.first_year_monthly_ownership_cost)}`);
            paragraph(section, `期末車輛估值：${money(car.ending_vehicle_value)}（年折舊 ${(car.annual_depreciation_rate * 100).toLocaleString('zh-TW')}%）`);
            paragraph(section, `模擬期間經濟成本：${money(car.economic_cost_in_horizon)}＝折舊 ${money(car.depreciation_in_horizon)}＋車貸利息 ${money(car.interest_in_horizon)}＋持有成本 ${money(car.ownership_cost_in_horizon)}`);
            paragraph(section, `使用預設值：${car.defaults_used.map(key=>ownershipLabels[key] || key).join('、') || '無'}`);
            $('vehicleSummaries').append(section);
          }
          $('vehicleCostNote').textContent = converted.note;
        }

      $('simulationResults').hidden=false;
    }
    let events=[],editing=null,lastRun=null;
    function clearExplanation(){
      $('explanationResult').replaceChildren();$('explanationSource').hidden=true;$('explanationNotice').hidden=true;
    }
    function invalidate(){
      $('simulationResults').hidden=true;$('simulationWarnings').replaceChildren();lastRun=null;clearExplanation();
      for(const target of root.document.querySelectorAll('[data-analysis-result]'))target.replaceChildren();
    }
    function renderExplanation(data){
      clearExplanation();
      if(data.source==='template'){$('explanationSource').hidden=false;$('explanationNotice').textContent=E.fallbackNotice(data.fallback_reason);$('explanationNotice').hidden=false;}
      $('explanationResult').append(...E.explanationNodes(root.document,data));
    }
    function paragraph(parent,text){parent.append(S.element('p',text));}
    function group(parent,title,rows){
      const section=S.element('section',null,'analysis-group');section.append(S.element('h4',title));
      const dl=S.element('dl');for(const[label,value]of rows){dl.append(S.element('dt',label),S.element('dd',value));}section.append(dl);parent.append(section);return section;
    }
    function renderAnalysis(target,result){
      target.replaceChildren();
      group(target,'財務限制',[['原本條件',result.constraints.every(c=>c.applicable===false||c.passed===true)?'全部通過':'未全部通過']]);
      const car=result.scenario,limit=result.affordability;
      const reasons={no_feasible_price:'目前財務限制下沒有可負擔車價',search_limit_reached:'已達搜尋上限，尚無法確認最高車價',verification_limit_reached:'已達驗證上限，尚無法確認最高車價'};
      group(target,'購車成本',[
        ['每月車貸',money(car.monthly_loan_payment)],['總利息',money(car.total_loan_interest)],['購車當月一次支出',money(car.one_time_cash_requirement)],
        ['最低現金',`${money(car.minimum_cash_balance)}（${car.minimum_cash_month}）`],
        ['最高可負擔車價',limit.maximum_affordable_vehicle_price==null?reasons[limit.status]||'尚無法判定':money(limit.maximum_affordable_vehicle_price)]]);
      const names={income_reduction:'收入減少',unemployment:'失業',emergency_expense:'突發支出',interest_rate:'貸款利率上升'};
      const stresses=group(target,'壓力測試',result.stress_tests.map(stress=>[names[stress.name]||'壓力測試',stress.applicable===false?'不適用':stress.passed===true?'通過':stress.passed===false?'未通過':'尚未判定']));
      paragraph(stresses,'壓力測試是在原本條件上再加壓，未通過代表遇到這種情況時現金會低於你設定的限制。');
      paragraph(target,'這個分析只看這台車和現有貸款，不包含計畫中的其他事件與投資。');
      const link=S.element('a','完整購車分析');link.href='/vehicle.html';target.append(link);
    }
    function selectTemplate(template){
      if(ctx.busy||editing||template?.status!=='available')return;
      $('eventForm').elements.type.value=template.eventType;$('eventForm').hidden=false;
      P.select($('eventTemplatePicker'),template.id);syncEventFields();
      if(template.eventType==='vehicle_purchase')syncVehicleSpec();
    }
    function renderPicker(template=null,locked=false){
      P.render($('eventTemplatePicker'),{selected:template?.id,locked,onSelect:selectTemplate});
    }
    function resetEditor(){
      editing=null;$('eventForm').reset();$('eventForm').elements.vehicle_catalog_id.value='';
      delete $('eventForm').elements.vehicle_catalog_id.dataset.pending;
      $('eventForm').elements.start_period.value=S.taipeiPeriod();$('eventEditorHeading').textContent='新增事件';
      $('eventForm').elements.type.value='';$('eventForm').hidden=true;fees.reset();
      $('eventForm').querySelector('[type="submit"]').textContent='新增事件';$('cancelEdit').hidden=true;renderPicker();syncEventFields();
    }
    function editEvent(event){
      const form=$('eventForm');form.reset();editing=event.id;
      for(const key of ['name','type','start_period','end_period','amount','monthly_amount','new_salary'])form.elements.namedItem(key).value=event[key]??'';
      form.elements.vehicle_catalog_id.value='';
      form.elements.vehicle_catalog_id.dataset.pending=event.details?.vehicle_catalog_id||'';
      for(const[key,value]of Object.entries(event.details||{})){
        const input=form.elements.namedItem(key);if(input)input.value=['annual_interest_rate','annual_depreciation_rate'].includes(key)?Number(value)*100:value??'';
      }
      fees.reset(event.details);syncVehicleSpec();
      $('eventEditorHeading').textContent='修改事件';form.querySelector('[type="submit"]').textContent='儲存事件';$('cancelEdit').hidden=false;
      renderPicker(T.templateForEvent(event),true);form.hidden=false;
      syncEventFields();$('eventEditorHeading').scrollIntoView({block:'start'});form.elements.name.focus();
    }
    function renderEvents(){
      const list=$('eventList');list.replaceChildren();
      if(!events.length)list.append(S.element('li','尚無事件，從下方新增第一筆。'));
      for(const event of M.sortEvents(events)){
        const li=S.element('li'),head=S.element('div',null,'event-head'),copy=S.element('div',null,'event-copy');
        const template=T.templateForEvent(event);
        copy.append(S.element('strong',event.name),S.element('span',`${template?.name||'事件'}｜${event.start_period}｜${M.eventSummary(event)}`));head.append(P.icon(template?.icon),copy);
        const edit=S.element('button','修改'),remove=S.element('button','刪除');edit.type=remove.type='button';edit.setAttribute('aria-label',`修改${event.name}`);remove.setAttribute('aria-label',`刪除${event.name}`);
        edit.addEventListener('click',()=>{if(!ctx.busy)editEvent(event);});
        remove.addEventListener('click',()=>ctx.perform(async()=>{
          if(!root.confirm(`確定刪除「${event.name}」？`))return;
          await ctx.store.removeEvent(ctx.planId,event.id);if(!ctx.alive)return;if(editing===event.id)resetEditor();await loadEvents();S.status('事件已刪除。');
        }));head.append(edit,remove);li.append(head);
        if(event.type==='vehicle_purchase'){
          const button=S.element('button','購車分析'),reason=model.vehicleAnalysisReason(S.taipeiPeriod(),event.start_period);button.type='button';button.setAttribute('aria-label',`購車分析：${event.name}`);button.disabled=!!reason;head.append(button);
          if(reason)li.append(S.element('small',reason));
          const result=S.element('div',null,'event-analysis');result.dataset.analysisResult='';result.setAttribute('aria-live','polite');li.append(result);
          button.addEventListener('click',()=>ctx.perform(async()=>{
            result.replaceChildren();paragraph(result,'正在分析購車…');
            try{
              const request=model.buildVehicleDecisionRequest({profile:ctx.profile,debts:ctx.debts,event,startPeriod:S.taipeiPeriod()});
              const response=await ctx.calculation(post=>post('/decisions/vehicle',request));if(ctx.alive)renderAnalysis(result,response);
            }catch(error){if(ctx.alive)result.replaceChildren();throw error;}
          }));
        }
        list.append(li);
      }
    }
    async function loadEvents(){
      const rows=await ctx.store.events(ctx.planId);if(!ctx.alive)return;
      events=rows;invalidate();renderEvents();
    }
    const notFound=()=>{$('notFound').hidden=false;$('planWorkspace').hidden=true;S.status('');};
    if(!ctx.planId||!ctx.plans.some(plan=>plan.id===ctx.planId)){notFound();return;}
    const plan=await ctx.store.plan(ctx.planId);if(!ctx.alive)return;if(!plan){notFound();return;}
    $('planWorkspace').hidden=false;$('pageTitle').textContent=plan.name;$('planNameForm').elements.name.value=plan.name;
    $('eventFields').disabled=false;
    $('startPeriod').value=S.taipeiPeriod();resetEditor();await loadEvents();if(!ctx.alive)return;
    function onSubmit(id,action){$(id).addEventListener('submit',event=>{event.preventDefault();if($(id).reportValidity())ctx.perform(action);});}
    $('eventForm').elements.payment_method.addEventListener('change',syncEventFields);
    $('eventForm').elements.vehicle_catalog_id.addEventListener('change',()=>{
      delete $('eventForm').elements.vehicle_catalog_id.dataset.pending;
      const car=vehicleCatalog.find(item=>item.id===$('eventForm').elements.vehicle_catalog_id.value);if(car)$('eventForm').elements.purchase_price.value=car.price_twd;
      syncVehicleSpec();
    });
    $('cancelEdit').addEventListener('click',resetEditor);
    onSubmit('planNameForm',async()=>{
      const name=$('planNameForm').elements.name.value.trim();if(!name)throw new Error('請填寫計畫名稱');
      const saved=await ctx.store.updatePlan(ctx.planId,{name});if(!ctx.alive)return;
      $('pageTitle').textContent=saved.name;ctx.plans=ctx.plans.map(p=>p.id===saved.id?saved:p);S.renderNavigation(ctx);S.status('計畫名稱已儲存。');
    });
    $('deletePlan').addEventListener('click',()=>ctx.perform(async()=>{
      if(!root.confirm('確定刪除這個計畫及其所有事件？'))return;
      await ctx.store.removePlan(ctx.planId);if(ctx.alive)root.location.assign('/dashboard.html');
    }));
    onSubmit('eventForm',async()=>{
      const form=$('eventForm'),name=form.elements.name.value.trim();if(!name)throw new Error('請填寫事件名稱');
      const numeric=key=>{const raw=form.elements.namedItem(key).value.trim();if(!raw||!Number.isFinite(Number(raw)))throw new Error('請填寫有效數字');return Number(raw);};
      const values={name,type:form.elements.type.value,start_period:form.elements.start_period.value,
        amount:null,monthly_amount:null,new_salary:null,end_period:null,details:{}};
      if(!T.templateForEvent(values))throw new Error('請先選擇可用的事件');
      if(editing&&events.find(event=>event.id===editing)?.type!==values.type)throw new Error('修改事件時不可變更事件類型');
      if(values.type==='one_time')values.amount=numeric('amount');
      else if(values.type==='salary_change')values.new_salary=numeric('new_salary');
      else if(values.type==='range'){
        values.monthly_amount=numeric('monthly_amount');values.end_period=form.elements.end_period.value||null;
        if(values.end_period&&values.end_period<values.start_period)throw new Error('結束月份不可早於開始月份');
      }else{
        const raw={};for(const key of ['vehicle_catalog_id','purchase_price','payment_method','down_payment','loan_term_months','annual_interest_rate','annual_depreciation_rate',...model.ownershipFields])raw[key]=form.elements.namedItem(key).value;
        raw.vehicle_catalog_id=form.elements.vehicle_catalog_id.dataset.pending??raw.vehicle_catalog_id;
        values.details={...model.vehicleDetails(raw),...fees.details()};
      }
      if(editing)await ctx.store.updateEvent(ctx.planId,editing,values);else await ctx.store.addEvent(ctx.planId,values);
      if(!ctx.alive)return;resetEditor();await loadEvents();S.status('事件已儲存。');
    });
    $('simulationForm').addEventListener('input',()=>{$('simulationResults').hidden=true;});
    onSubmit('simulationForm',async()=>{
      invalidate();S.status('正在計算…');
      const startPeriod=$('startPeriod').value,months=Number($('simulationMonths').value);
      const built=await S.prepareSimulation(ctx,events,months,startPeriod);if(!ctx.alive)return;
      for(const warning of built.warnings)$('simulationWarnings').append(S.element('li',warning));
      const [simulation,mc]=await ctx.calculation(post=>Promise.all([post('/simulate',{...built.request,seed:42}),post('/monte-carlo',{...built.request,simulations:300,seed:42})]));
      if(!ctx.alive)return;
      renderResults(simulation,mc,built.converted,startPeriod);lastRun={built,months,events};
      root.WalletCharts.draw($('planChart'),$('planChartSummary'),simulation.result.simulation_curve,startPeriod,events,ctx.profile,{debts:ctx.debts});
      S.status('模擬完成。');
    });
    $('explainResults').addEventListener('click',()=>ctx.perform(async()=>{
      const run=lastRun;if(!run)throw new Error('請先執行模擬');
      clearExplanation();S.status('正在產生說明…');
      const request=E.buildExplanationRequest({prepared:run.built,events:run.events,months:run.months,
        emergencyTargetMonths:ctx.profile.emergency_target_months,eventSummary:M.eventSummary});
      const data=await ctx.calculation(post=>post('/ai/plan-explanation',request));
      if(!ctx.alive||lastRun!==run)return;
      renderExplanation(data);S.status('說明已產生。');
    }));
    const add=T.resolveAddParameter(root.location.search);
    if(new URLSearchParams(root.location.search).has('add'))root.history.replaceState(root.history.state,'',`${root.location.pathname}${add.search}${root.location.hash}`);
    if(add.template){
      selectTemplate(add.template);$('eventForm').scrollIntoView({block:'start'});$('eventForm').elements.name.focus({preventScroll:true});
    }
    loadVehicleMetadata();
  }
  root.PlanPage={start};
})(globalThis);
