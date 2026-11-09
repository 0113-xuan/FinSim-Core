(function(root) {
  'use strict';
  async function start(ctx) {
    const S=root.FutureWalletShell,M=root.ShellModel,model=root.PlannerModel,E=root.ExplanationModel,T=root.EventTemplates,P=root.EventPicker,$=id=>root.document.getElementById(id),money=M.money;
    // Buying a car is entered in three steps; every other event type shows its fields at once.
    let vehicleStep=1;
    function syncEventFields() {
      const type = $('eventForm').elements.type.value;
      for (const label of root.document.querySelectorAll('[data-event-field]')) {
        const key = label.dataset.eventField;
        const visible = type === 'range' ? ['monthly_amount','end_period'].includes(key) : type === 'one_time' ? key === 'amount' : type === 'salary_change' && key === 'new_salary';
        label.hidden = !visible; for (const control of label.querySelectorAll('input,select')) control.disabled = !visible;
      }
      for (const label of root.document.querySelectorAll('[data-vehicle-field]')) {
        const visible = type === 'vehicle_purchase' && (label.dataset.vehicleField !== 'financed' || $('eventForm').elements.payment_method.value === 'financed');
        label.hidden = !visible;
        const control = label.querySelector('input,select'); if (control) control.disabled = !visible;
      }
      fees.sync();
      parking.sync();
      salaryReference.sync();
      syncVehicleSteps();
    }
    const stepControls=step=>[...$('eventForm').querySelectorAll(`[data-vehicle-step="${step}"] input,[data-vehicle-step="${step}"] select`)];
    function syncVehicleSteps() {
      const form=$('eventForm'),active=form.elements.type.value==='vehicle_purchase';
      // The browser cannot focus a control on a hidden step, so the steps validate themselves instead.
      form.noValidate=active;
      if(active)form.dataset.activeStep=String(vehicleStep);else delete form.dataset.activeStep;
      $('vehicleSteps').hidden=!active;
      for(const button of $('vehicleSteps').querySelectorAll('[data-step-button]')){
        if(Number(button.dataset.stepButton)===vehicleStep)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');
      }
      $('vehiclePrev').hidden=!active||vehicleStep===1;$('vehicleNext').hidden=!active||vehicleStep===3;
      form.querySelector('[type="submit"]').hidden=active&&vehicleStep<3;
    }
    function showVehicleStep(step,{focus=true}={}) {
      vehicleStep=step;syncVehicleSteps();
      if(focus)stepControls(step).find(control=>!control.disabled&&!control.closest('[hidden]'))?.focus();
    }
    function firstInvalidStep(from,to) {
      for(let step=from;step<=to;step++){const control=stepControls(step).find(item=>!item.checkValidity());if(control)return {step,control};}
      return null;
    }
    function advanceVehicleStep(target) {
      const invalid=firstInvalidStep(vehicleStep,target-1);
      if(invalid){showVehicleStep(invalid.step,{focus:false});invalid.control.reportValidity();return false;}
      showVehicleStep(target);return true;
    }
    const ownershipLabels = {annual_insurance:'保險',annual_tax:'稅費',annual_maintenance_budget:'保養',monthly_fuel_or_energy:'油電',monthly_parking:'停車',annual_depreciation_rate:'折舊率'};
    let vehicleCatalog = [];
    const fees=root.VehicleFeesForm.create({form:$('eventForm'),isAlive:()=>ctx.alive});
    const parking=root.ParkingForm.create({form:$('eventForm'),profile:ctx.profile,isAlive:()=>ctx.alive});
    const salaryReference=root.SalaryReferenceForm.create({form:$('eventForm'),profile:ctx.profile,isAlive:()=>ctx.alive});
    function syncVehicleSpec(){
      const select=$('eventForm').elements.vehicle_catalog_id;
      const id=select.dataset.pending??select.value;
      fees.spec(vehicleCatalog.find(car=>car.id===id));
    }
    async function loadVehicleMetadata() {
      try {
        const responses = await Promise.all(['/decisions/vehicle/catalog?include_ev=true','/decisions/vehicle/assumptions'].map(url=>root.fetch(url)));
        if (responses.some(response=>!response.ok)) throw new Error('載入失敗');
        const [catalog, assumptions] = await Promise.all(responses.map(response=>response.json()));
        if(!ctx.alive)return;
        vehicleCatalog = catalog;
        const select = $('eventForm').elements.vehicle_catalog_id;
        const selection = select.dataset.pending ?? select.value;
        select.replaceChildren();
        for (const {brand, vehicles} of model.groupVehicleCatalog(catalog)) {
          const group = root.document.createElement('optgroup'); group.label = brand;
          for (const car of vehicles) {
            const option = root.document.createElement('option'); option.value = car.id;
            option.textContent = car.label; group.append(option);
          }
          select.append(group);
        }
        const custom = root.document.createElement('option'); custom.value = ''; custom.textContent = '自訂車款'; custom.defaultSelected = true; select.append(custom); select.value = selection;
        for (const key of model.ownershipFields.filter(key=>!['annual_insurance','annual_tax'].includes(key))) {
          const assumption = assumptions.find(item=>item.key === key);
          if (!assumption || !Number.isFinite(Number(assumption.value))) throw new Error('預設值載入不完整');
          $('eventForm').elements.namedItem(key).placeholder = `留空使用預設 ${Number(assumption.value).toLocaleString('zh-TW')}／${key.startsWith('annual_') ? '年' : '月'}`;
        }
        $('vehicleMetadataStatus').textContent = '可修改車價；留空的持有成本於計算時套用預設值。';
        syncVehicleSpec();
      } catch (_) { if(ctx.alive)$('vehicleMetadataStatus').textContent = '車款或預設值載入未完成；可使用自訂車款，留空的成本會用系統預設值。重新整理可重試。'; }
    }

    // Keep a YYYY-MM period on one line instead of breaking at its hyphen.
    function setText(node,text) { node.replaceChildren(...text.split(/(\d{4}-\d{2})/).map((part,i) => i % 2 ? S.element('span',part,'nowrap') : root.document.createTextNode(part))); }
    function renderConclusion(summary,mc,startPeriod,months,baseline) {
        const view = root.ResultsModel.conclusion({summary, mc, startPeriod, months, simulations:300, baseline});
        $('conclusion').dataset.tone = view.tone;
        setText($('conclusionHeadline'), view.headline);
        $('conclusionFacts').replaceChildren(...view.facts.map(fact => {
          const value = S.element('dd'), item = S.element('div');
          const note = S.element('small'), label = S.element('dt');
          setText(note, fact.note); setText(label, fact.label);
          value.append(S.element('strong', fact.value), note);
          item.append(label, value);
          return item;
        }));
        const compare = $('conclusionCompare');
        compare.hidden = !view.comparison;
        if (view.comparison) { compare.querySelector('strong').textContent = `${view.comparison.lead}：`; setText(compare.querySelector('span'), view.comparison.text); }
        $('conclusionAction').hidden = view.tone === 'calm';
        $('conclusionCaveat').textContent = view.caveat;
    }
    function renderResults(simulation,mc,converted,startPeriod,months,baseline) {
        const summary = simulation.result.summary;
        renderConclusion(summary, mc, startPeriod, months, baseline?.result?.summary);
        $('minimumCash').textContent = money(summary.minimum_cash_balance);
        $('minimumCashPeriod').textContent = model.monthToPeriod(startPeriod, summary.minimum_cash_month);
        $('firstNegativePeriod').textContent = summary.first_negative_cash_month == null ? '未出現' : model.monthToPeriod(startPeriod, summary.first_negative_cash_month);
        $('minimumEmergency').textContent = summary.minimum_emergency_fund_months == null ? '不適用（無必要支出）' : `${Math.round(Number(summary.minimum_emergency_fund_months))} 個月`;
        $('endingCash').textContent = money(summary.final_balance);
        $('cashShortfall').textContent = M.wholePercent(mc.probability_cash_shortfall);
        for (const [id, key] of [['cashP5','p5'],['cashP50','p50'],['cashP95','p95']]) $(id).textContent = money(mc.percentiles[key]);
        $('shortfallDefinition').textContent = `現金不足機率的定義：${mc.cash_shortfall_definition}。`;
        $('endingInvestment').textContent = money(summary.final_investment_value);
        const investmentBand = mc.monthly_bands?.investment;
        for (const [id, key] of [['investmentP5','p5'],['investmentP50','p50'],['investmentP95','p95']]) $(id).textContent = investmentBand?.[key] ? money(investmentBand[key].at(-1)) : '—';
        $('endingNetWorth').textContent = summary.final_net_worth == null ? '—' : money(summary.final_net_worth);
        for (const [id, key] of [['netWorthP5','p5'],['netWorthP50','p50'],['netWorthP95','p95']]) $(id).textContent = money(mc.net_worth_percentiles[key]);
        for (const [id, key] of [['realNetWorthP5','p5'],['realNetWorthP50','p50'],['realNetWorthP95','p95']]) $(id).textContent = mc.real_net_worth_percentiles[key] == null ? '—' : money(mc.real_net_worth_percentiles[key]);
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
            paragraph(section, `期末車輛估值：${money(car.ending_vehicle_value)}（年折舊 ${Math.round(car.annual_depreciation_rate * 100)}%）`);
            paragraph(section, `模擬期間經濟成本：${money(car.economic_cost_in_horizon)}＝折舊 ${money(car.depreciation_in_horizon)}＋車貸利息 ${money(car.interest_in_horizon)}＋持有成本 ${money(car.ownership_cost_in_horizon)}`);
            paragraph(section, `使用預設值：${car.defaults_used.map(key=>ownershipLabels[key] || key).join('、') || '無'}`);
            $('vehicleSummaries').append(section);
          }
          $('vehicleCostNote').textContent = converted.note;
        }

      $('simulationResults').hidden=false;
    }
    let events=[],editing=null,lastRun=null,qa=null;
    // Progress and failures of a long action show next to its button, where the user is looking.
    function runStatus(id,text,working=false){
      const node=$(id);node.textContent=text;
      if(working)node.dataset.state='working';else delete node.dataset.state;
    }
    function clearExplanation(){
      $('explanationResult').replaceChildren();$('explanationSource').hidden=true;$('explanationNotice').hidden=true;runStatus('explanationStatus','');
      $('explanationError').hidden=true;$('explanationError').textContent='';
    }
    function invalidate(){
      const hadResults=!$('simulationResults').hidden;
      $('simulationResults').hidden=true;$('simulationWarnings').replaceChildren();lastRun=null;clearExplanation();runStatus('simulationStatus',hadResults?'計畫或輸入已變更，上一次的結果已清除，請重新執行模擬。':'');
      $('simulationError').hidden=true;$('simulationError').textContent='';
      qa?.clear();
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
    // Once a template is chosen the picker collapses; the heading names the event and life events take the template name.
    function showTemplate(template,mode){
      const form=$('eventForm'),named=T.asksForName(template);
      $('eventTemplatePicker').hidden=true;$('changeTemplate').hidden=mode!=='新增事件';
      $('eventEditorHeading').textContent=`${mode}：${template.name}`;
      form.querySelector('[data-event-name]').hidden=!named;
      if(!named&&!form.elements.name.value.trim())form.elements.name.value=template.name;
      form.hidden=false;
    }
    // A plan holds one event: once it exists the picker is gone and the event can only be edited or deleted.
    function syncEditorPanel(){
      $('eventEditorPanel').hidden=events.length>0&&!editing;
    }
    function selectTemplate(template){
      if(ctx.busy||editing||events.length||template?.status!=='available')return;
      vehicleStep=1;$('eventForm').elements.type.value=template.eventType;$('eventForm').elements.name.value=T.asksForName(template)?'':template.name;
      showTemplate(template,'新增事件');syncEventFields();
      if(template.eventType==='vehicle_purchase'){syncVehicleSpec();parking.refresh();}
      if(template.eventType==='salary_change')salaryReference.refresh();
    }
    function focusFirstField(options){
      const field=[...$('eventForm').querySelectorAll('input:not([type="hidden"]),select')].find(control=>!control.disabled&&!control.closest('[hidden]'));
      field?.focus(options);
    }
    function renderPicker(template=null,locked=false){
      P.render($('eventTemplatePicker'),{selected:template?.id,locked,onSelect:selectTemplate});
    }
    function resetEditor(){
      editing=null;vehicleStep=1;$('vehicleOptionalCosts').open=false;$('eventForm').reset();$('eventForm').elements.vehicle_catalog_id.value='';
      delete $('eventForm').elements.vehicle_catalog_id.dataset.pending;
      $('eventForm').elements.start_period.value=S.taipeiPeriod();$('eventEditorHeading').textContent='新增事件';
      $('eventForm').elements.type.value='';$('eventForm').hidden=true;fees.reset();parking.reset();salaryReference.reset();
      $('eventTemplatePicker').hidden=false;$('changeTemplate').hidden=true;$('eventForm').querySelector('[data-event-name]').hidden=true;
      $('eventForm').querySelector('[type="submit"]').textContent='新增事件';$('cancelEdit').hidden=true;renderPicker();syncEventFields();syncEditorPanel();
    }
    function editEvent(event){
      const form=$('eventForm');form.reset();editing=event.id;vehicleStep=1;
      for(const key of ['name','type','start_period','end_period','amount','monthly_amount','new_salary'])form.elements.namedItem(key).value=event[key]??'';
      for(const key of ['amount','monthly_amount']){
        const stored=Number(event[key]);if(event[key]==null||event[key]===''||!Number.isFinite(stored))continue;
        const split=model.splitAmount(stored);form.elements.namedItem(key).value=split.value;form.elements.namedItem(`${key}_direction`).value=split.direction;
      }
      form.elements.vehicle_catalog_id.value='';
      form.elements.vehicle_catalog_id.dataset.pending=event.details?.vehicle_catalog_id||'';
      for(const[key,value]of Object.entries(event.details||{})){
        const input=form.elements.namedItem(key);if(input)input.value=['annual_interest_rate','annual_depreciation_rate'].includes(key)?Number(value)*100:value??'';
      }
      $('vehicleOptionalCosts').open=[...$('vehicleOptionalCosts').querySelectorAll('input')].some(input=>input.value!=='');
      fees.reset(event.details);syncVehicleSpec();
      parking.reset(event.details);
      salaryReference.reset(event.details||{});
      form.querySelector('[type="submit"]').textContent='儲存事件';$('cancelEdit').hidden=false;
      const template=T.templateForEvent(event);renderPicker(template,true);showTemplate(template,'修改事件');
      syncEditorPanel();syncEventFields();$('eventEditorHeading').scrollIntoView({block:'start'});focusFirstField();
    }
    function renderEvents(){
      const list=$('eventList');list.replaceChildren();
      if(!events.length)list.append(S.element('li','還沒有事件，請從下方選一個。'));
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
      syncEditorPanel();
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
    $('startPeriod').value=S.taipeiPeriod();
    qa=root.PlanQAForm.mount({after:$('simulationResults'),ctx,getRequest:()=>lastRun
      ? E.buildExplanationRequest({prepared:lastRun.built,events:lastRun.events,months:lastRun.months,
          emergencyTargetMonths:ctx.profile.emergency_target_months,eventSummary:M.eventSummary})
      : {start_period:$('startPeriod').value}});
    resetEditor();await loadEvents();if(!ctx.alive)return;
    function onSubmit(id,action,options){$(id).addEventListener('submit',event=>{event.preventDefault();if($(id).reportValidity())ctx.perform(action,options);});}
    $('eventForm').elements.payment_method.addEventListener('change',syncEventFields);
    $('eventForm').elements.vehicle_catalog_id.addEventListener('change',()=>{
      delete $('eventForm').elements.vehicle_catalog_id.dataset.pending;
      const car=vehicleCatalog.find(item=>item.id===$('eventForm').elements.vehicle_catalog_id.value);if(car)$('eventForm').elements.purchase_price.value=car.price_twd;
      syncVehicleSpec();
    });
    $('vehicleSteps').addEventListener('click',event=>{
      const button=event.target.closest('[data-step-button]');if(!button||ctx.busy)return;
      const target=Number(button.dataset.stepButton);if(target<=vehicleStep)showVehicleStep(target);else advanceVehicleStep(target);
    });
    $('vehicleNext').addEventListener('click',()=>{if(!ctx.busy)advanceVehicleStep(vehicleStep+1);});
    $('vehiclePrev').addEventListener('click',()=>{if(!ctx.busy&&vehicleStep>1)showVehicleStep(vehicleStep-1);});
    // Enter on an early step moves on; only the last step saves, and only when every step is valid.
    $('eventForm').addEventListener('submit',event=>{
      if(!$('eventForm').noValidate)return;
      if(vehicleStep<3){event.preventDefault();event.stopImmediatePropagation();advanceVehicleStep(vehicleStep+1);return;}
      const invalid=firstInvalidStep(1,3);
      if(invalid){event.preventDefault();event.stopImmediatePropagation();showVehicleStep(invalid.step,{focus:false});invalid.control.reportValidity();}
    },true);
    $('cancelEdit').addEventListener('click',resetEditor);
    // A rejected value inside the collapsed optional costs must not fail silently.
    $('vehicleOptionalCosts').addEventListener('invalid',()=>{$('vehicleOptionalCosts').open=true;},true);
    $('changeTemplate').addEventListener('click',()=>{if(!ctx.busy)resetEditor();});
    onSubmit('planNameForm',async()=>{
      const name=$('planNameForm').elements.name.value.trim();if(!name)throw new Error('請填寫計畫名稱');
      const saved=await ctx.store.updatePlan(ctx.planId,{name});if(!ctx.alive)return;
      $('pageTitle').textContent=saved.name;ctx.plans=ctx.plans.map(p=>p.id===saved.id?saved:p);S.renderNavigation(ctx);S.status('計畫名稱已儲存。');
    });
    $('renamePlan').addEventListener('click',()=>{const settings=$('planSettings');settings.open=true;settings.scrollIntoView({block:'center'});$('planNameForm').elements.name.focus();});
    $('deletePlan').addEventListener('click',()=>ctx.perform(async()=>{
      if(!root.confirm('確定刪除這個計畫及其所有事件？'))return;
      await ctx.store.removePlan(ctx.planId);if(ctx.alive)root.location.assign('/dashboard.html');
    }));
    onSubmit('eventForm',async()=>{
      const form=$('eventForm'),name=form.elements.name.value.trim();if(!name)throw new Error('請填寫事件名稱');
      const numeric=key=>{const raw=form.elements.namedItem(key).value.trim();if(!raw||!Number.isFinite(Number(raw)))throw new Error('請填寫有效數字');return Number(raw);};
      const signed=key=>model.signedAmount(form.elements.namedItem(key).value,form.elements.namedItem(`${key}_direction`).value);
      const values={name,type:form.elements.type.value,start_period:form.elements.start_period.value,
        amount:null,monthly_amount:null,new_salary:null,end_period:null,details:{}};
      if(!T.templateForEvent(values))throw new Error('請先選擇可用的事件');
      if(editing&&events.find(event=>event.id===editing)?.type!==values.type)throw new Error('修改事件時不可變更事件類型');
      if(values.type==='one_time')values.amount=signed('amount');
      else if(values.type==='salary_change'){values.new_salary=numeric('new_salary');values.details=salaryReference.details();}
      else if(values.type==='range'){
        values.monthly_amount=signed('monthly_amount');values.end_period=form.elements.end_period.value||null;
        if(values.end_period&&values.end_period<values.start_period)throw new Error('結束月份不可早於開始月份');
      }else{
        const raw={};for(const key of ['vehicle_catalog_id','purchase_price','payment_method','down_payment','loan_term_months','annual_interest_rate','annual_depreciation_rate',...model.ownershipFields])raw[key]=form.elements.namedItem(key).value;
        raw.vehicle_catalog_id=form.elements.vehicle_catalog_id.dataset.pending??raw.vehicle_catalog_id;
        values.details={...model.vehicleDetails(raw),...fees.details(),...parking.details()};
      }
      if(editing)await ctx.store.updateEvent(ctx.planId,editing,values);else await ctx.store.addEvent(ctx.planId,values);
      if(!ctx.alive)return;resetEditor();await loadEvents();S.status('事件已儲存。');
    });
    $('simulationForm').addEventListener('input',invalidate);
    onSubmit('simulationForm',async()=>{
      invalidate();runStatus('simulationStatus','正在計算，請稍候…',true);
      try{
      const startPeriod=$('startPeriod').value,months=Number($('simulationMonths').value);
      const built=await S.prepareSimulation(ctx,events,months,startPeriod);if(!ctx.alive)return;
      for(const warning of built.warnings)$('simulationWarnings').append(S.element('li',warning));
      // The same plan without its events, so the answer can say what the event changed; a failure here only drops the comparison.
      const hasEvents=built.request.events.length>0||!!built.converted;
      const baseRequest=hasEvents?(await S.prepareSimulation(ctx,[],months,startPeriod)).request:null;
      const [simulation,mc,baseline]=await ctx.calculation(post=>Promise.all([post('/simulate',{...built.request,seed:42}),post('/monte-carlo',{...built.request,simulations:300,seed:42}),
        baseRequest?post('/simulate',{...baseRequest,seed:42}).catch(()=>null):null]));
      if(!ctx.alive)return;
      renderResults(simulation,mc,built.converted,startPeriod,months,baseline);lastRun={built,months,events};
      $('assumptionList').replaceChildren(...root.ResultsModel.assumptionRows({simulation:simulation.result,mc,request:built.request,
        startPeriod,months,simulations:300,seed:42,converted:built.converted}).flatMap(row=>[S.element('dt',row.label),S.element('dd',row.value)]));
      root.WalletCharts.draw($('planChart'),$('planChartSummary'),simulation.result.simulation_curve,startPeriod,events,ctx.profile,{debts:ctx.debts});
      if(mc.monthly_bands)root.WalletCharts.drawBands($('bandChart'),$('bandChartSummary'),mc.monthly_bands,startPeriod,events,ctx.profile,{debts:ctx.debts});
      root.WalletCharts.drawCashflow($('cashflowChart'),$('cashflowChartSummary'),simulation.result.simulation_curve,startPeriod);
      root.WalletCharts.drawComposition($('compositionChart'),$('compositionChartSummary'),simulation.result.simulation_curve);
      runStatus('simulationStatus','模擬完成，結果在下方。');
      return $('conclusionHeading');
      }catch(error){runStatus('simulationStatus','');throw error;}
    },{scope:'simulationPanel',errorId:'simulationError'});
    $('explainResults').addEventListener('click',()=>ctx.perform(async()=>{
      const run=lastRun;if(!run)throw new Error('請先執行模擬');
      clearExplanation();runStatus('explanationStatus','正在產生說明…',true);
      try{
        const request=E.buildExplanationRequest({prepared:run.built,events:run.events,months:run.months,
          emergencyTargetMonths:ctx.profile.emergency_target_months,eventSummary:M.eventSummary});
        const data=await ctx.calculation(post=>post('/ai/plan-explanation',request));
        if(!ctx.alive||lastRun!==run){runStatus('explanationStatus','');return;}
        renderExplanation(data);runStatus('explanationStatus','說明已產生。');
      }catch(error){runStatus('explanationStatus','');throw error;}
    },{scope:'explanationSection',errorId:'explanationError'}));
    const add=T.resolveAddParameter(root.location.search);
    if(new URLSearchParams(root.location.search).has('add'))root.history.replaceState(root.history.state,'',`${root.location.pathname}${add.search}${root.location.hash}`);
    if(add.template){
      selectTemplate(add.template);$('eventEditorHeading').scrollIntoView({block:'start'});focusFirstField({preventScroll:true});
    }
    loadVehicleMetadata();
  }
  root.PlanPage={start};
})(globalThis);
