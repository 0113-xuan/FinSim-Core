(function(root) {
  'use strict';
  const fields = {
    profiles: 'user_id,monthly_income,cash_balance,fixed_expense,variable_expense,investment_value,monthly_investment,raise_rate,emergency_target_months,updated_at',
    debts: 'id,user_id,name,monthly_payment,remaining_months,created_at',
    plans: 'id,user_id,name,kind,created_at,updated_at',
    plan_events: 'id,plan_id,user_id,type,name,start_period,end_period,amount,monthly_amount,new_salary,details,created_at'
  };
  async function checked(query) {
    const {data, error} = await query;
    if (error) throw new Error(error.message || '資料操作失敗');
    return data;
  }
  function createStore(client, userId) {
    const owned = table => client.from(table).select(fields[table]).eq('user_id', userId);
    const remove = async query => {
      const rows = await checked(query.select('id'));
      if (!rows?.length) throw new Error('資料已不存在或無法刪除，請重新載入');
    };
    return {
      profile: () => checked(owned('profiles').maybeSingle()),
      debts: () => checked(owned('debts').order('created_at')),
      plans: () => checked(owned('plans').order('created_at')),
      events: planId => checked(owned('plan_events').eq('plan_id', planId).order('start_period')),
      saveProfile: values => checked(client.from('profiles').upsert({...values, user_id:userId, updated_at:new Date().toISOString()}, {onConflict:'user_id'}).select(fields.profiles).single()),
      addDebt: values => checked(client.from('debts').insert({...values, user_id:userId}).select(fields.debts).single()),
      removeDebt: id => remove(client.from('debts').delete().eq('user_id', userId).eq('id', id)),
      addPlan: values => checked(client.from('plans').insert({...values, user_id:userId}).select(fields.plans).single()),
      removePlan: id => remove(client.from('plans').delete().eq('user_id', userId).eq('id', id)),
      addEvent: (planId, values) => checked(client.from('plan_events').insert({...values, plan_id:planId, user_id:userId}).select(fields.plan_events).single()),
      removeEvent: (planId, id) => remove(client.from('plan_events').delete().eq('user_id', userId).eq('plan_id', planId).eq('id', id))
    };
  }
  function taipeiPeriod(date = new Date()) {
    const parts = new Intl.DateTimeFormat('en', {timeZone:'Asia/Taipei', year:'numeric', month:'2-digit'}).formatToParts(date);
    return `${parts.find(p => p.type === 'year').value}-${parts.find(p => p.type === 'month').value}`;
  }

  async function start() {
    const $ = id => root.document.getElementById(id);
    const model = root.PlannerModel;
    const state = {client:null, store:null, userId:undefined, epoch:0, eventEpoch:0, accountEpoch:0, busy:false,
      ready:false, eventsReady:false, profile:null, debts:[], plans:[], events:[], profileDirty:false,
      selectedPlan:'', controller:null};
    const money = value => value == null ? '不適用' : new Intl.NumberFormat('zh-TW', {style:'currency', currency:'TWD', maximumFractionDigits:2}).format(value);
    function message(text) { $('plannerStatus').textContent = text; }
    function showError(error) {
      $('plannerError').textContent = `操作未完成：${error.message || '請稍後再試'}`;
      $('plannerError').hidden = false;
    }
    function invalidate() {
      $('simulationResults').hidden = true;
      $('simulationWarnings').replaceChildren();
      for (const result of root.document.querySelectorAll('[data-vehicle-analysis-result]')) result.replaceChildren();
    }
    function controls() {
      const available = state.ready && !state.busy;
      for (const id of ['profileFields','debtFields','planFields']) $(id).disabled = !available;
      $('eventFields').disabled = !available || !state.selectedPlan || !state.eventsReady;
      $('simulationFields').disabled = !available || !state.profile || state.profileDirty || !state.selectedPlan || !state.eventsReady;
      $('planSelect').disabled = !available;
      $('deletePlan').disabled = !available || !state.selectedPlan;
      $('signOut').disabled = state.busy;
      $('reloadData').disabled = state.busy;
      $('authFields').disabled = !state.client || state.busy;
      for (const button of root.document.querySelectorAll('[data-remove]')) button.disabled = !available || (button.dataset.remove === 'event' && !state.eventsReady);
      for (const button of root.document.querySelectorAll('[data-analyze]')) {
        const event = state.events.find(row => row.id === button.dataset.analyze);
        const reason = !state.profile || state.profileDirty ? '請先儲存財務資料再執行購車分析。'
          : model.vehicleAnalysisReason(taipeiPeriod(), event?.start_period);
        button.disabled = !available || !state.eventsReady || !!reason;
        button.parentElement.querySelector('[data-analysis-reason]').textContent = reason;
      }
    }
    async function perform(action) {
      if (state.busy) return;
      const epoch = state.epoch;
      state.busy = true;
      $('plannerError').hidden = true;
      controls();
      try { await action(epoch); }
      catch (error) { if (state.epoch === epoch) showError(error); }
      finally { if (state.epoch === epoch) { state.busy = false; controls(); } }
    }
    function list(id, rows, describe, removeKind) {
      const target = $(id);
      target.replaceChildren();
      if (!rows.length) { const item = root.document.createElement('li'); item.textContent = '尚無資料'; target.append(item); }
      for (const row of rows) {
        const item = root.document.createElement('li'), text = root.document.createElement('span'), button = root.document.createElement('button');
        text.textContent = describe(row);
        button.type = 'button'; button.textContent = '刪除'; button.dataset.remove = removeKind; button.dataset.id = row.id;
        button.setAttribute('aria-label', `刪除${row.name}`);
        item.append(text, button); target.append(item);
        if (removeKind === 'event' && row.type === 'vehicle_purchase') {
          item.classList.add('vehicle-event');
          const line = root.document.createElement('div'); line.className = 'event-row';
          line.append(text, button);
          const analyze = root.document.createElement('button'); analyze.type = 'button';
          analyze.dataset.analyze = row.id; analyze.textContent = '購車分析'; analyze.setAttribute('aria-label', `購車分析：${row.name}`);
          const reason = root.document.createElement('small'); reason.dataset.analysisReason = '';
          line.append(analyze, reason);
          const result = root.document.createElement('div'); result.className = 'vehicle-analysis';
          result.dataset.vehicleAnalysisResult = ''; result.setAttribute('aria-live','polite');
          item.append(line, result);
        }
      }
    }
    function renderProfile() {
      const form = $('profileForm');
      form.reset();
      form.elements.user_id.value = state.userId || '';
      if (state.profile) {
        for (const [key, value] of Object.entries(state.profile)) {
          if (form.elements.namedItem(key)) form.elements.namedItem(key).value = value ?? '';
        }
      }
      $('profileHint').textContent = state.profile ? '財務資料已載入。' : '尚無財務資料，請先填寫並儲存。';
      state.profileDirty = false;
    }
    function renderPlans() {
      const select = $('planSelect'); select.replaceChildren();
      const empty = root.document.createElement('option'); empty.value = ''; empty.textContent = state.plans.length ? '請選擇計畫' : '尚無計畫'; select.append(empty);
      for (const plan of state.plans) { const option = root.document.createElement('option'); option.value = plan.id; option.textContent = plan.name; select.append(option); }
      select.value = state.selectedPlan;
    }
    async function loadEvents(epoch = state.epoch) {
      const eventEpoch = ++state.eventEpoch, planId = state.selectedPlan, store = state.store;
      state.events = []; state.eventsReady = false; invalidate();
      list('eventList', [], () => '', 'event'); controls();
      if (!planId) return;
      try {
        const events = await store.events(planId);
        if (epoch !== state.epoch || eventEpoch !== state.eventEpoch) return;
        state.events = events; state.eventsReady = true;
        list('eventList', events, event => {
          const car = event.details || {};
          const detail = event.type === 'one_time' ? money(event.amount) : event.type === 'range' ? `每月 ${money(event.monthly_amount)}，至 ${event.end_period || '模擬結束'}` : event.type === 'salary_change' ? `新月薪 ${money(event.new_salary)}` : event.type === 'vehicle_purchase' ? `車價 ${money(car.purchase_price)}，${car.payment_method === 'financed' ? `貸款 ${car.loan_term_months} 期` : '現金購買'}` : '不支援的事件類型';
          return `${event.name}｜${event.start_period}｜${detail}`;
        }, 'event');
      } catch (error) { if (epoch === state.epoch && eventEpoch === state.eventEpoch) showError(error); }
      finally { if (epoch === state.epoch && eventEpoch === state.eventEpoch) controls(); }
    }
    async function loadAccount(epoch = state.epoch) {
      const store = state.store;
      if (!store) return;
      const accountEpoch = ++state.accountEpoch;
      state.ready = false; state.eventsReady = false; invalidate(); controls();
      try {
        const [profile, debts, plans] = await Promise.all([store.profile(), store.debts(), store.plans()]);
        if (epoch !== state.epoch || accountEpoch !== state.accountEpoch) return;
        Object.assign(state, {profile, debts, plans, ready:true});
        if (!plans.some(plan => plan.id === state.selectedPlan)) state.selectedPlan = plans[0]?.id || '';
        renderProfile(); renderPlans();
        list('debtList', debts, debt => `${debt.name}｜每月 ${money(debt.monthly_payment)}｜剩餘 ${debt.remaining_months} 期`, 'debt');
        await loadEvents(epoch);
        if (epoch === state.epoch && accountEpoch === state.accountEpoch) message('已載入你的資料。');
      } catch (error) { if (epoch === state.epoch && accountEpoch === state.accountEpoch) showError(error); }
      finally { if (epoch === state.epoch && accountEpoch === state.accountEpoch) controls(); }
    }
    function sessionChanged(session) {
      const userId = session?.user?.id || null;
      if (userId === state.userId) return;
      state.controller?.abort();
      Object.assign(state, {userId, store:userId ? createStore(state.client, userId) : null,
        epoch:state.epoch + 1, eventEpoch:state.eventEpoch + 1, accountEpoch:state.accountEpoch + 1, ready:false, eventsReady:false,
        profile:null, debts:[], plans:[], events:[], selectedPlan:'', busy:false, profileDirty:false});
      $('plannerWorkspace').hidden = !userId; $('signedIn').hidden = !userId; $('authForm').hidden = !!userId;
      $('plannerError').hidden = true;
      $('authForm').elements.password.value = '';
      for (const id of ['debtForm','planForm','eventForm']) $(id).reset();
      $('eventForm').elements.start_period.value = taipeiPeriod();
      $('startPeriod').value = taipeiPeriod();
      renderProfile(); renderPlans(); invalidate();
      list('debtList', [], () => '', 'debt'); list('eventList', [], () => '', 'event'); syncEventFields(); controls();
      message(userId ? '正在載入你的資料…' : '請登入或註冊以儲存財務資料。');
      // Keep the Auth callback synchronous: further Supabase calls run after its lock is released.
      if (userId) { const epoch = state.epoch; root.setTimeout(() => { if (epoch === state.epoch) loadAccount(epoch); }, 0); }
    }
    function numeric(form, key) {
      const raw = form.elements.namedItem(key).value;
      if (raw.trim() === '' || !Number.isFinite(Number(raw))) throw new Error('請填寫有效數字');
      return Number(raw);
    }
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
    }
    const ownershipLabels = {annual_insurance:'保險',annual_tax:'稅費',annual_maintenance_budget:'保養',monthly_fuel_or_energy:'油電',monthly_parking:'停車'};
    let vehicleCatalog = [];
    async function loadVehicleMetadata() {
      try {
        const responses = await Promise.all(['/decisions/vehicle/catalog','/decisions/vehicle/assumptions'].map(url=>root.fetch(url)));
        if (responses.some(response=>!response.ok)) throw new Error('載入失敗');
        const [catalog, assumptions] = await Promise.all(responses.map(response=>response.json()));
        vehicleCatalog = catalog;
        const select = $('eventForm').elements.vehicle_catalog_id;
        select.replaceChildren();
        for (const car of catalog) {
          const option = root.document.createElement('option'); option.value = car.id;
          option.textContent = `${car.brand} ${car.model} ${car.trim}`; select.append(option);
        }
        const custom = root.document.createElement('option'); custom.value = ''; custom.textContent = '自訂車款'; custom.defaultSelected = true; select.append(custom); select.value = '';
        for (const key of model.ownershipFields) {
          const assumption = assumptions.find(item=>item.key === key);
          if (!assumption || !Number.isFinite(Number(assumption.value))) throw new Error('預設值載入不完整');
          $('eventForm').elements.namedItem(key).placeholder = `留空使用預設 ${Number(assumption.value).toLocaleString('zh-TW')}／${key.startsWith('annual_') ? '年' : '月'}`;
        }
        $('vehicleMetadataStatus').textContent = '可修改車價；留空的持有成本於計算時套用預設值。';
      } catch (_) { $('vehicleMetadataStatus').textContent = '車款或預設值載入未完成；可使用自訂車款，留空成本由後端套用預設值。重新整理可重試。'; }
    }
    async function calculation(action) {
      const controller = new AbortController(); state.controller = controller;
      const timeout = root.setTimeout(() => controller.abort(), 30000);
      async function post(url, payload) {
        const response = await root.fetch(url, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
        let data; try { data = await response.json(); } catch (_) { /* A gateway may return HTML. */ }
        if (!response.ok) {
          const detail = typeof data?.detail === 'string' ? data.detail : Array.isArray(data?.detail) ? data.detail.map(error=>error.msg).join('；') : '';
          throw new Error(detail || `計算失敗（HTTP ${response.status}），請檢查金額及事件後重試`);
        }
        if (!data) throw new Error('計算回應無法讀取，請重試');
        return data;
      }
      try { return await action(post); }
      catch (error) {
        controller.abort();
        if (error.name === 'AbortError') throw new Error('計算逾時或已取消，請重試；儲存資料不受影響');
        throw error;
      } finally { root.clearTimeout(timeout); if (state.controller === controller) state.controller = null; }
    }
    function paragraph(parent, text) { const p = root.document.createElement('p'); p.textContent = text; parent.append(p); }
    function renderVehicleAnalysis(target, result) {
      target.replaceChildren();
      const allPassed = result.constraints.every(item=>item.applicable === false || item.passed === true);
      paragraph(target, `財務限制：${allPassed ? '全部通過' : '未全部通過'}`);
      const car = result.scenario;
      paragraph(target, `每月車貸：${money(car.monthly_loan_payment)}｜總利息：${money(car.total_loan_interest)}｜購車當月一次支出：${money(car.one_time_cash_requirement)}`);
      paragraph(target, `最低現金：${money(car.minimum_cash_balance)}｜發生月份：${car.minimum_cash_month}`);
      const limit = result.affordability;
      const reasons = {no_feasible_price:'目前財務限制下沒有可負擔車價',search_limit_reached:'已達搜尋上限，尚無法確認最高車價',verification_limit_reached:'已達驗證上限，尚無法確認最高車價'};
      paragraph(target, `最高可負擔車價：${limit.maximum_affordable_vehicle_price == null ? reasons[limit.status] || '尚無法判定' : money(limit.maximum_affordable_vehicle_price)}`);
      const stressNames = {income_reduction:'收入減少',unemployment:'失業',emergency_expense:'突發支出',interest_rate:'貸款利率上升'};
      for (const stress of result.stress_tests) paragraph(target, `${stressNames[stress.name] || stress.name}：${stress.applicable === false ? '不適用' : stress.passed === true ? '通過' : stress.passed === false ? '未通過' : '尚未判定'}`);
      paragraph(target, '這個分析只看這台車和現有貸款，不包含計畫中的其他事件與投資。');
      const link = root.document.createElement('a'); link.href = '/vehicle.html'; link.textContent = '完整購車分析'; target.append(link);
    }
    function onSubmit(id, action) {
      $(id).addEventListener('submit', event => { event.preventDefault(); if ($(id).reportValidity()) perform(epoch => action($(id), event, epoch)); });
    }
    onSubmit('authForm', async (form, event) => {
      const credentials = {email:form.elements.email.value.trim(), password:form.elements.password.value};
      const signup = event.submitter?.value === 'signup';
      const data = await checked(signup ? state.client.auth.signUp(credentials) : state.client.auth.signInWithPassword(credentials));
      form.elements.password.value = '';
      if (data.session) sessionChanged(data.session);
      else if (signup) message('請到信箱點確認連結後再登入');
      else throw new Error('未取得登入狀態，請重新登入');
    });
    $('signOut').addEventListener('click', () => perform(async () => { await checked(state.client.auth.signOut()); sessionChanged(null); }));
    $('reloadData').addEventListener('click', () => perform(epoch => loadAccount(epoch)));
    $('profileForm').addEventListener('input', () => { state.profileDirty = true; invalidate(); controls(); });
    onSubmit('profileForm', async (form, _, epoch) => {
      const values = {};
      for (const key of ['monthly_income','cash_balance','fixed_expense','variable_expense','investment_value','monthly_investment','emergency_target_months']) values[key] = numeric(form, key);
      values.raise_rate = form.elements.raise_rate.value === '' ? null : numeric(form, 'raise_rate');
      const profile = await state.store.saveProfile(values);
      if (epoch !== state.epoch) return;
      state.profile = profile; renderProfile(); invalidate(); message('財務資料已儲存。');
    });
    onSubmit('debtForm', async (form, _, epoch) => {
      const name = form.elements.name.value.trim(); if (!name) throw new Error('請填寫貸款名稱');
      await state.store.addDebt({name, monthly_payment:numeric(form, 'monthly_payment'), remaining_months:numeric(form, 'remaining_months')});
      if (epoch !== state.epoch) return;
      form.reset(); await loadAccount(epoch);
    });
    $('debtList').addEventListener('click', event => {
      const button = event.target.closest('[data-remove="debt"]');
      if (button) perform(async epoch => { await state.store.removeDebt(button.dataset.id); if (epoch === state.epoch) await loadAccount(epoch); });
    });
    onSubmit('planForm', async (form, _, epoch) => {
      const name = form.elements.name.value.trim(); if (!name) throw new Error('請填寫計畫名稱');
      const plan = await state.store.addPlan({name, kind:form.elements.kind.value});
      if (epoch !== state.epoch) return;
      state.selectedPlan = plan.id; form.reset(); await loadAccount(epoch);
    });
    $('planSelect').addEventListener('change', () => { state.selectedPlan = $('planSelect').value; $('plannerError').hidden = true; loadEvents(); });
    $('deletePlan').addEventListener('click', () => {
      if (!state.selectedPlan || !root.confirm('確定刪除所選計畫及其所有事件？')) return;
      perform(async epoch => { await state.store.removePlan(state.selectedPlan); if (epoch !== state.epoch) return; state.selectedPlan = ''; await loadAccount(epoch); });
    });
    $('eventForm').elements.type.addEventListener('change', syncEventFields);
    $('eventForm').elements.payment_method.addEventListener('change', syncEventFields);
    $('eventForm').elements.vehicle_catalog_id.addEventListener('change', () => {
      const car = vehicleCatalog.find(item=>item.id === $('eventForm').elements.vehicle_catalog_id.value);
      if (car) $('eventForm').elements.purchase_price.value = car.price_twd;
    });
    onSubmit('eventForm', async (form, _, epoch) => {
      if (!state.selectedPlan) throw new Error('請先選擇計畫');
      const name = form.elements.name.value.trim(); if (!name) throw new Error('請填寫事件名稱');
      const values = {name, type:form.elements.type.value, start_period:form.elements.start_period.value};
      if (values.type === 'one_time') values.amount = numeric(form, 'amount');
      else if (values.type === 'salary_change') values.new_salary = numeric(form, 'new_salary');
      else if (values.type === 'vehicle_purchase') {
        const raw = {};
        for (const key of ['vehicle_catalog_id','purchase_price','payment_method','down_payment','loan_term_months','annual_interest_rate',...model.ownershipFields]) raw[key] = form.elements.namedItem(key).value;
        values.details = model.vehicleDetails(raw);
        Object.assign(values, {amount:null, monthly_amount:null, new_salary:null, end_period:null});
      } else {
        values.monthly_amount = numeric(form, 'monthly_amount'); values.end_period = form.elements.end_period.value || null;
        if (values.end_period && values.end_period < values.start_period) throw new Error('結束月份不可早於開始月份');
      }
      await state.store.addEvent(state.selectedPlan, values);
      if (epoch !== state.epoch) return;
      form.reset(); form.elements.start_period.value = taipeiPeriod(); syncEventFields(); await loadEvents(epoch);
    });
    $('eventList').addEventListener('click', event => {
      const analyze = event.target.closest('[data-analyze]');
      if (analyze && !analyze.disabled) {
        perform(async epoch => {
          const car = state.events.find(row=>row.id === analyze.dataset.analyze), eventEpoch = state.eventEpoch;
          const request = model.buildVehicleDecisionRequest({profile:state.profile,debts:state.debts,event:car,startPeriod:taipeiPeriod()});
          const target = analyze.closest('li').querySelector('[data-vehicle-analysis-result]');
          target.replaceChildren(); paragraph(target, '正在分析購車…');
          try {
            const result = await calculation(post=>post('/decisions/vehicle', request));
            if (epoch === state.epoch && eventEpoch === state.eventEpoch) renderVehicleAnalysis(target, result);
          } catch (error) { if (epoch === state.epoch && eventEpoch === state.eventEpoch) target.replaceChildren(); throw error; }
        });
        return;
      }
      const button = event.target.closest('[data-remove="event"]');
      if (button) perform(async epoch => { await state.store.removeEvent(state.selectedPlan, button.dataset.id); if (epoch === state.epoch) await loadEvents(epoch); });
    });
    $('simulationForm').addEventListener('input', invalidate);
    onSubmit('simulationForm', async (form, _, epoch) => {
      const startPeriod = $('startPeriod').value;
      const {request, warnings, vehicles} = model.buildSimulationRequest({profile:state.profile, debts:state.debts, events:state.events, startPeriod, months:Number($('simulationMonths').value)});
      invalidate();
      for (const warning of warnings) { const li = root.document.createElement('li'); li.textContent = warning; $('simulationWarnings').append(li); }
      message('正在計算…');
      await calculation(async post => {
        let converted;
        if (vehicles.length) {
          converted = await post('/planner/vehicle-events', {start_period:startPeriod,months:request.months,inflation_rate:request.profile.inflation_rate ?? null,vehicles});
          request.events.push(...converted.events); request.loans = [...(request.loans || []),...converted.loans];
        }
        const [simulation, mc] = await Promise.all([post('/simulate', {...request, seed:42}), post('/monte-carlo', {...request, simulations:300, seed:42})]);
        if (epoch !== state.epoch) return;
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
            paragraph(section, `使用預設值：${car.defaults_used.map(key=>ownershipLabels[key] || key).join('、') || '無'}`);
            $('vehicleSummaries').append(section);
          }
          $('vehicleCostNote').textContent = converted.note;
        }
        $('simulationResults').hidden = false; message('模擬完成。');
      });
    });

    loadVehicleMetadata();
    try {
      const response = await root.fetch('/config/public', {cache:'no-store'});
      if (!response.ok) throw new Error('無法讀取登入設定，請重新整理');
      const config = await response.json();
      if (!config.configured) { message('尚未設定 Supabase'); return; }
      if (!root.supabase?.createClient || !model) throw new Error('登入元件載入失敗，請檢查網路後重新整理');
      state.client = root.supabase.createClient(config.supabase_url, config.supabase_anon_key);
      let authEvents = 0;
      state.client.auth.onAuthStateChange((_, session) => { authEvents++; sessionChanged(session); });
      const initialEvents = authEvents;
      const data = await checked(state.client.auth.getSession());
      if (authEvents === initialEvents) sessionChanged(data.session);
      controls();
    } catch (error) { showError(error); message('登入初始化未完成，請重新整理後再試。'); }
  }
  const api = {createStore, taipeiPeriod, start};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.PlannerApp = api; start(); }
})(globalThis);
