const T = window.FinSimTransparency;
const P = window.FinSimProfileOnboarding;
const $ = id => document.getElementById(id);

const state = {
  categories: [],
  scenarios: [],
  activeScenarioId: null,
  events: [],
  allocationRatios: { ...T.DEFAULT_ALLOCATION },
  assumptionBindings: [],
  lastSimulation: null,
  lastMonteCarlo: null,
  lastOptimization: null,
  profileDraft: null,
  profileMode: null,
  referenceDate: new Intl.DateTimeFormat('en-CA', {
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Taipei',
    year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(new Date())
};

const chartControllers = {};
const initialChatMarkup = $('chatLog').innerHTML;
const initialOnboardingChatMarkup = $('onboardingChatLog').innerHTML;
const currency = T.formatCurrency;

function toast(message, type = 'ok') {
  const element = $('toast');
  element.textContent = message;
  element.className = type;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => {
    element.textContent = '';
    element.className = '';
  }, 3500);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `API failed: ${path}`);
  return data;
}

function appendOnboardingMessage(role, content) {
  const message = document.createElement('div');
  message.className = `chat-message ${role}`;
  const avatar = document.createElement('span');
  avatar.className = 'chat-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'user' ? '你' : 'AI';
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  const paragraph = document.createElement('p');
  paragraph.textContent = content;
  bubble.appendChild(paragraph);
  message.append(...(role === 'user' ? [bubble, avatar] : [avatar, bubble]));
  $('onboardingChatLog').appendChild(message);
  $('onboardingChatLog').scrollTop = $('onboardingChatLog').scrollHeight;
}

function persistDraftLocally() {
  if (state.profileDraft) {
    sessionStorage.setItem('finsim-profile-draft', JSON.stringify(state.profileDraft));
  } else {
    sessionStorage.removeItem('finsim-profile-draft');
  }
}

function draftFuturePlansHtml() {
  const plans = state.profileDraft?.future_plans || [];
  if (!plans.length) return '<div class="empty-state">尚未提供未來計畫。</div>';
  return `<div class="future-plan-list">${plans.map((item, index) => `
    <div class="future-plan-item ${P.isEstimated(item) ? 'is-estimated' : ''}">
      <div><strong>${T.escapeHtml(item.value)}</strong><small>${P.sourceLabel(item.source)} · ${T.escapeHtml(item.reason)}</small></div>
      <label class="confirm-check"><input data-confirm-plan="${index}" type="checkbox" ${item.confirmed ? 'checked' : ''}> ${item.confirmed ? '已確認' : '等待確認'}</label>
    </div>`).join('')}</div>`;
}

function renderProfileDraft(openReview = false) {
  const draft = state.profileDraft;
  if (!draft) {
    $('draftProgressList').className = 'draft-progress-list empty-state';
    $('draftProgressList').textContent = '送出第一則訊息後顯示完整度。';
    $('openDraftReviewBtn').disabled = true;
    return;
  }
  $('onboardingStatus').textContent = draft.status === 'confirmed' ? '已確認' : '草稿進行中';
  $('onboardingStatus').className = `draft-status ${draft.status === 'confirmed' ? 'status-confirmed' : 'status-review'}`;
  $('draftVersion').textContent = `v${draft.version}`;
  $('draftProgressList').className = 'draft-progress-list';
  $('draftProgressList').innerHTML = P.renderProgress(draft);
  $('openDraftReviewBtn').disabled = false;
  $('draftReviewRows').innerHTML = P.renderReview(draft);
  $('draftAllocationRows').innerHTML = P.renderAllocation(draft);
  $('draftFuturePlans').innerHTML = draftFuturePlansHtml();
  const errors = P.clientValidation(draft);
  $('draftValidation').innerHTML = errors.length
    ? `<strong>確認前請先修正：</strong><ul>${errors.map(error => `<li>${T.escapeHtml(error)}</li>`).join('')}</ul>`
    : '';
  const requiredKeys = ['cash_and_deposits', 'monthly_salary', 'fixed_expenses', 'total_variable_expenses', 'simulation_months'];
  const unconfirmedRequired = requiredKeys.some(key => !draft[key]?.confirmed);
  const allocationUnconfirmed = (draft.variable_expense_allocation || []).some(item => !item.confirmed);
  $('confirmProfileDraftBtn').disabled = errors.length > 0 || unconfirmedRequired || allocationUnconfirmed;
  $('draftReviewStatus').textContent = draft.status === 'confirmed' ? '已確認' : '等待確認';
  $('draftReviewStatus').className = `draft-status ${draft.status === 'confirmed' ? 'status-confirmed' : 'status-review'}`;
  if (openReview) {
    $('profileDraftReview').hidden = false;
    $('profileDraftReview').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  persistDraftLocally();
}

function setProfileSetupMode(mode, { scroll = true } = {}) {
  const useAi = mode === 'ai';
  const useManual = mode === 'manual';
  $('onboardingWorkspace').hidden = !useAi;
  $('profile').hidden = !useManual;
  $('profileDraftReview').hidden = true;
  $('startAiOnboardingBtn').classList.toggle('is-selected', useAi);
  $('startManualProfileBtn').classList.toggle('is-selected', useManual);
  $('startAiOnboardingBtn').setAttribute('aria-pressed', String(useAi));
  $('startManualProfileBtn').setAttribute('aria-pressed', String(useManual));

  if (useManual) {
    state.profileMode = 'manual';
    $('runBtn').disabled = false;
    $('manualProfileStatus').textContent = '手動模式';
    if (scroll) $('profile').scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  state.profileMode = state.profileDraft?.status === 'confirmed' ? 'confirmed-ai' : null;
  $('runBtn').disabled = !state.profileMode;
  $('onboardingStatus').textContent = state.profileDraft ? '草稿進行中' : '開始建立';
  $('onboardingStatus').className = 'draft-status status-review';
  if (scroll) $('onboardingWorkspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
  $('onboardingText').focus();
}

function openManualProfile() {
  setProfileSetupMode('manual');
}

async function sendOnboardingMessage() {
  const text = $('onboardingText').value.trim();
  if (!text) return;
  appendOnboardingMessage('user', text);
  $('onboardingText').value = '';
  const button = $('sendOnboardingBtn');
  setLoading(button, true, '…');
  try {
    const data = await api('/ai/financial-onboarding/message', {
      method: 'POST',
      body: JSON.stringify({ text, draft_id: state.profileDraft?.id || null })
    });
    state.profileDraft = data.draft;
    appendOnboardingMessage('assistant', data.assistant_message);
    $('providerStatus').textContent = data.provider_available
      ? 'AI 擷取服務可用'
      : '使用安全的本機擷取模式';
    $('advisorProgress').textContent = `第 ${data.current_step} 步，共 ${data.total_steps} 步 · ${data.stage_label}`;
    $('onboardingFallback').hidden = data.provider_available;
    renderProfileDraft(data.ready_for_review);
  } catch (error) {
    appendOnboardingMessage('assistant', '自動擷取暫時無法使用。你的訊息仍保留在這個對話中，可以改用手動填寫。');
    $('onboardingFallback').hidden = false;
    sessionStorage.setItem('finsim-onboarding-unsent', text);
  } finally {
    setLoading(button, false);
    $('onboardingText').focus();
  }
}

async function saveProfileDraft() {
  if (!state.profileDraft) return;
  const data = await api(`/financial-profile-drafts/${state.profileDraft.id}`, {
    method: 'PUT',
    body: JSON.stringify({ draft: state.profileDraft })
  });
  state.profileDraft = data.draft;
  renderProfileDraft();
}

function applyConfirmedDraft(profile) {
  const draft = state.profileDraft;
  $('balance').value = profile.balance;
  $('salary').value = Number(draft.monthly_salary.value || 0) + Number(draft.other_recurring_income.value || 0);
  $('fixedExpense').value = draft.fixed_expenses.value || 0;
  $('variableExpense').value = draft.total_variable_expenses.value || 0;
  $('monthlyDebtPayment').value = draft.monthly_debt_payments.value || 0;
  $('months').value = draft.simulation_months.value || 60;
  if (profile.variable_expense_model?.categories?.length) {
    renderCategories(profile.variable_expense_model.categories.map(item => ({
      category: item.category,
      amount: item.baseline
    })));
    $('advancedMode').checked = true;
  }
  state.profileMode = 'confirmed-ai';
  $('profile').hidden = false;
  $('manualProfileStatus').textContent = 'AI 草稿已確認';
  $('manualProfileStatus').className = 'draft-status status-confirmed';
  $('runBtn').disabled = false;
}

function profileFromConfirmedDraft(draft) {
  return {
    balance: Number(draft.cash_and_deposits.value || 0)
      + Number(draft.investments.value || 0)
      + Number(draft.other_assets.value || 0),
    variable_expense_model: {
      categories: (draft.variable_expense_allocation || []).map(item => ({
        category: item.category,
        baseline: Number(item.amount || 0)
      }))
    }
  };
}

function setLoading(button, loading, label = '處理中...') {
  button.disabled = loading;
  button.dataset.originalText ||= button.textContent;
  button.textContent = loading ? label : button.dataset.originalText;
}

function activeScenario() {
  return state.scenarios.find(item => item.id === state.activeScenarioId) || null;
}

function pendingScenarios() {
  return state.scenarios.filter(item => !['使用者已確認', '使用系統預設'].includes(item.status));
}

function appendChatMessage(role, content, options = {}) {
  const message = document.createElement('div');
  message.className = `chat-message ${role}${options.loading ? ' loading' : ''}`;
  const avatar = document.createElement('span');
  avatar.className = 'chat-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'user' ? '你' : 'AI';
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  const paragraph = document.createElement('p');
  paragraph.textContent = content;
  bubble.appendChild(paragraph);
  message.append(...(role === 'user' ? [bubble, avatar] : [avatar, bubble]));
  $('chatLog').appendChild(message);
  $('chatLog').scrollTop = $('chatLog').scrollHeight;
  return message;
}

function directReplyForInput(text) {
  const compact = text.trim().replace(/\s+/g, '');
  if (!/[\p{L}\p{N}]/u.test(compact) || /^(.)\1{3,}$/u.test(compact)) {
    return '我看不太懂這段內容。可以改成「時間 + 計畫 + 金額」，例如：半年後買車，每月車貸 12,000 元。';
  }
  if (/^(嗨|哈囉|你好|hello|hi)[!！。.]?$/iu.test(compact)) {
    return '嗨！告訴我一個可能影響收入或支出的未來計畫，我會幫你整理成財務情境。';
  }
  if (compact.length < 4) {
    return '可以再多說一點嗎？我需要知道你打算做什麼，以及大約何時發生。';
  }
  if (/(天氣|笑話|歌詞|遊戲攻略|寫作業|翻譯)/u.test(compact)) {
    return '這裡主要協助評估生活計畫的財務影響。你可以告訴我搬家、換工作、買車或旅行等計畫。';
  }
  return null;
}

function scenarioClarificationText(clarification) {
  const known = (clarification.known_values || [])
    .map(item => `${item.label}：${item.value}（${item.source}）`)
    .join('、');
  const questions = (clarification.questions || []).join(' ');
  const candidates = T.ClarificationCandidateList(clarification.candidates || []);
  return [
    clarification.summary,
    known ? `已知：${known}。` : '',
    candidates,
    questions,
    clarification.system_assumption_offer || ''
  ].filter(Boolean).join(' ');
}

function monthlyDebtLoan() {
  const payment = Number($('monthlyDebtPayment').value) || 0;
  const months = Number($('months').value) || 60;
  if (payment <= 0) return [];
  return [{
    principal: payment * months,
    apr: 0,
    months,
    start_month: 1,
    note: '使用者輸入的既有每月債務'
  }];
}

function allocationToCategories(total) {
  return T.allocationFromTotal(total, state.allocationRatios, '使用者修改').map(item => ({
    category: item.category,
    baseline: item.monthly_amount,
    monthly_volatility: 0,
    annual_inflation_rate: Number($('inflationRate').value) || 0.02,
    income_elasticity: 0,
    seasonal_factors: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    minimum: null,
    maximum: null,
    enabled: true
  }));
}

function buildProfile() {
  const quickTotal = Number($('variableExpense').value) || 0;
  return {
    salary: Number($('salary').value) || 0,
    fixed_expense: Number($('fixedExpense').value) || 0,
    variable_expense: quickTotal,
    balance: Number($('balance').value) || 0,
    raise_rate: Number($('raiseRate').value) || 0,
    inflation_rate: Number($('inflationRate').value) || 0,
    target_emergency_months: Number($('emergencyMonths').value) || 3,
    variable_expense_model: {
      mode: $('advancedMode').checked && state.categories.length ? 'advanced' : 'quick',
      total_variable_expense: quickTotal,
      categories: state.categories
    }
  };
}

function rebuildConfirmedEvents() {
  const months = Number($('months').value) || 60;
  state.events = state.scenarios
    .filter(item => item.status === '使用者已確認')
    .flatMap(item => T.scenarioEvents(item, months));
}

function basePayload() {
  const shocks = $('enableShocks').checked ? [
    { name: 'Medical expense', target_category: 'medical', monthly_probability: 0.03, min_amount: 3000, max_amount: 30000, duration_months: 1, distribution: 'uniform', enabled: true },
    { name: 'Temporary income loss', monthly_probability: 0.01, min_amount: 10000, max_amount: 40000, duration_months: 1, distribution: 'uniform', enabled: true }
  ] : [];
  return {
    profile: buildProfile(),
    months: Number($('months').value) || 60,
    events: state.events,
    loans: monthlyDebtLoan(),
    random_shocks: shocks,
    seed: Number($('seed').value) || 42,
    scenario_context: state.scenarios.map(T.scenarioContext)
  };
}

function eventCost(event) {
  const oneTime = event.type === 'one_time' ? event.amount : event.one_time_amount;
  return {
    oneTime: Math.max(0, -Number(oneTime || 0)),
    recurring: Math.max(0, -Number(event.monthly_amount || 0))
      + Math.max(0, Number(event.category_monthly_adjustment || 0)),
    offset: Math.max(0, Number(event.monthly_amount || 0))
      + Math.max(0, -Number(event.category_monthly_adjustment || 0))
  };
}

function renderScenarioWorkspace() {
  const list = $('scenarioSummaryList');
  if (!state.scenarios.length) {
    list.className = 'scenario-summary-list empty-state';
    list.textContent = '尚無 AI 情境。請先在上方描述你的未來計畫。';
    $('scenarioEventsList').innerHTML = '';
    $('scenarioReview').hidden = true;
    $('runBtn').disabled = !state.profileMode;
    return;
  }

  list.className = 'scenario-summary-list';
  list.innerHTML = state.scenarios.map(T.ScenarioSummaryCard).join('');
  list.querySelectorAll('[data-scenario-id]').forEach(card => {
    card.addEventListener('click', () => {
      state.activeScenarioId = card.dataset.scenarioId;
      renderScenarioWorkspace();
    });
  });

  const rows = state.scenarios.flatMap(scenario => (
    T.scenarioEvents(scenario, Number($('months').value) || 60).map(event => ({
      scenario,
      event,
      cost: eventCost(event)
    }))
  ));
  $('scenarioEventsList').innerHTML = rows.length ? `
    <h3>AI 建立的財務事件</h3>
    <div class="table-scroll"><table>
      <thead><tr><th>情境</th><th>事件</th><th>月份</th><th>一次性</th><th>每月</th><th>抵銷</th><th>來源</th></tr></thead>
      <tbody>${rows.map(({ scenario, event, cost }) => `
        <tr>
          <td>${T.escapeHtml(scenario.title)}</td>
          <th>${T.escapeHtml(event.name || '財務事件')}</th>
          <td>${T.formatPeriod(event.start_period || scenario.start_period)}</td>
          <td>${currency(cost.oneTime)}</td>
          <td>${currency(cost.recurring)}</td>
          <td>${cost.offset ? `-${currency(cost.offset)}` : '無變化'}</td>
          <td>${T.sourceLabel(event.source)}</td>
        </tr>`).join('')}</tbody>
    </table></div>` : '';

  const scenario = activeScenario();
  $('scenarioReview').hidden = !scenario;
  if (scenario) {
    fillReviewForm(scenario);
    renderEventEditor(scenario);
    renderAdjustmentEditor(scenario);
    renderAssumptions(scenario.assumptions);
    $('sourceList').className = 'details-body';
    $('sourceList').innerHTML = T.SourceList(scenario.sources);
  }
  $('runBtn').disabled = !state.profileMode || pendingScenarios().length > 0;
}

function fillReviewForm(scenario) {
  $('reviewTitle').value = scenario.title;
  $('reviewType').value = scenario.scenario_type;
  $('reviewStartMonth').value = scenario.start_month;
  $('reviewDuration').value = scenario.duration_months;
  $('reviewOneTime').value = scenario.one_time_cost;
  $('reviewRecurring').value = scenario.recurring_monthly_cost;
  $('reviewLow').value = scenario.low_estimate;
  $('reviewExpected').value = scenario.expected_estimate;
  $('reviewHigh').value = scenario.high_estimate;
}

function readReviewForm(scenario, markModified = true) {
  scenario.title = $('reviewTitle').value.trim() || scenario.title;
  scenario.scenario_type = $('reviewType').value.trim() || scenario.scenario_type;
  scenario.start_month = Math.max(1, Number($('reviewStartMonth').value) || 1);
  scenario.duration_months = Math.max(1, Number($('reviewDuration').value) || 1);
  scenario.one_time_cost = Math.max(0, Number($('reviewOneTime').value) || 0);
  scenario.recurring_monthly_cost = Math.max(0, Number($('reviewRecurring').value) || 0);
  scenario.low_estimate = Math.max(0, Number($('reviewLow').value) || 0);
  scenario.expected_estimate = Math.max(0, Number($('reviewExpected').value) || 0);
  scenario.high_estimate = Math.max(0, Number($('reviewHigh').value) || 0);
  if (markModified) scenario.status = '使用者已修改';
}

function applyReviewToEvents(scenario) {
  const all = [...scenario.events, ...scenario.expense_adjustments];
  const currentStart = Math.min(...all.map(item => Number(item.start_month || item.month || scenario.start_month)));
  const shift = scenario.start_month - currentStart;
  const end = Math.min(Number($('months').value) || 60, scenario.start_month + scenario.duration_months - 1);
  all.forEach(item => {
    if (item.start_month) item.start_month = Math.max(1, Number(item.start_month) + shift);
    if (item.month) item.month = Math.max(1, Number(item.month) + shift);
    if (item.end_month) item.end_month = Math.max(item.start_month || item.month || 1, Number(item.end_month) + shift);
    const recurring = Number(item.monthly_amount || 0) !== 0
      || Number(item.category_monthly_adjustment || 0) !== 0
      || Number(item.multiplier || 1) !== 1;
    if (recurring) item.end_month = end;
  });

  const oneTimeEvents = scenario.events.filter(event => (
    Number(event.one_time_amount || 0) !== 0 || (event.type === 'one_time' && Number(event.amount || 0) !== 0)
  ));
  const originalOneTime = oneTimeEvents.reduce((sum, event) => {
    const value = event.type === 'one_time' ? event.amount : event.one_time_amount;
    return sum + Math.max(0, -Number(value || 0));
  }, 0);
  if (oneTimeEvents.length) {
    oneTimeEvents.forEach((event, index) => {
      const current = Math.max(0, -Number(event.type === 'one_time' ? event.amount : event.one_time_amount || 0));
      const share = originalOneTime > 0 ? current / originalOneTime : index === 0 ? 1 : 0;
      const value = -Math.round(scenario.one_time_cost * share * 100) / 100;
      if (event.type === 'one_time') event.amount = value;
      else event.one_time_amount = value;
    });
  } else if (scenario.one_time_cost > 0) {
    scenario.events.push({
      type: 'life_event',
      name: `${scenario.title}一次性支出`,
      start_month: scenario.start_month,
      one_time_amount: -scenario.one_time_cost,
      source: 'manual',
      display_source: '使用者修改',
      reason: '使用者在確認頁新增'
    });
  }

  const positiveRecurring = [
    ...scenario.events.map(event => ({
      owner: event,
      field: Number(event.category_monthly_adjustment || 0) > 0 ? 'category_monthly_adjustment' : Number(event.monthly_amount || 0) < 0 ? 'monthly_amount' : null,
      amount: Math.max(0, Number(event.category_monthly_adjustment || 0)) + Math.max(0, -Number(event.monthly_amount || 0))
    })),
    ...scenario.expense_adjustments.map(item => ({
      owner: item,
      field: Number(item.monthly_amount || 0) > 0 ? 'monthly_amount' : null,
      amount: Math.max(0, Number(item.monthly_amount || 0))
    }))
  ].filter(item => item.field);
  const originalRecurring = positiveRecurring.reduce((sum, item) => sum + item.amount, 0);
  if (originalRecurring > 0) {
    positiveRecurring.forEach(item => {
      const value = Math.round(scenario.recurring_monthly_cost * item.amount / originalRecurring * 100) / 100;
      item.owner[item.field] = item.field === 'monthly_amount' && item.owner.type ? -value : value;
    });
  } else if (scenario.recurring_monthly_cost > 0) {
    scenario.expense_adjustments.push({
      category: 'other',
      start_month: scenario.start_month,
      end_month: end,
      multiplier: 1,
      monthly_amount: scenario.recurring_monthly_cost,
      reason: '使用者在確認頁新增',
      expense_role: 'additional',
      source: '使用者修改'
    });
  }
}

function renderEventEditor(scenario) {
  const container = $('eventEditor');
  container.classList.toggle('empty', !scenario.events.length);
  container.innerHTML = scenario.events.length ? scenario.events.map((event, index) => `
    <div class="editor-row event-editor-row">
      <label>事件<input value="${T.escapeHtml(event.name || '')}" data-event-index="${index}" data-field="name"></label>
      <label>開始<input type="number" min="1" value="${event.start_month || event.month || 1}" data-event-index="${index}" data-field="start_month"></label>
      <label>結束<input type="number" min="1" value="${event.end_month || event.start_month || event.month || 1}" data-event-index="${index}" data-field="end_month"></label>
      <label>一次性<input type="number" value="${event.one_time_amount || event.amount || 0}" data-event-index="${index}" data-field="one_time_amount"></label>
      <label>每月現金流<input type="number" value="${event.monthly_amount || 0}" data-event-index="${index}" data-field="monthly_amount"></label>
      <label>分類調整<input type="number" value="${event.category_monthly_adjustment || 0}" data-event-index="${index}" data-field="category_monthly_adjustment"></label>
      <label>分類<input value="${T.escapeHtml(event.target_expense_category || 'other')}" data-event-index="${index}" data-field="target_expense_category"></label>
    </div>`).join('') : '尚無事件。';
  container.querySelectorAll('[data-event-index]').forEach(input => input.addEventListener('change', event => {
    const target = scenario.events[Number(event.target.dataset.eventIndex)];
    target[event.target.dataset.field] = event.target.type === 'number' ? Number(event.target.value) : event.target.value;
    target.display_source = '使用者修改';
    scenario.status = '使用者已修改';
    renderScenarioWorkspace();
  }));
}

function renderAdjustmentEditor(scenario) {
  const container = $('adjustmentEditor');
  container.classList.toggle('empty', !scenario.expense_adjustments.length);
  container.innerHTML = scenario.expense_adjustments.length ? scenario.expense_adjustments.map((item, index) => `
    <div class="editor-row adjustment-editor-row">
      <label>分類<input value="${T.escapeHtml(item.category)}" data-adjustment-index="${index}" data-field="category"></label>
      <label>開始<input type="number" min="1" value="${item.start_month}" data-adjustment-index="${index}" data-field="start_month"></label>
      <label>結束<input type="number" min="1" value="${item.end_month || Number($('months').value) || 60}" data-adjustment-index="${index}" data-field="end_month"></label>
      <label>倍率<input type="number" value="${item.multiplier}" step="0.1" data-adjustment-index="${index}" data-field="multiplier"></label>
      <label>每月金額<input type="number" value="${item.monthly_amount}" data-adjustment-index="${index}" data-field="monthly_amount"></label>
      <label>原因<input value="${T.escapeHtml(item.reason || '')}" data-adjustment-index="${index}" data-field="reason"></label>
    </div>`).join('') : '尚無支出調整。';
  container.querySelectorAll('[data-adjustment-index]').forEach(input => input.addEventListener('change', event => {
    const target = scenario.expense_adjustments[Number(event.target.dataset.adjustmentIndex)];
    target[event.target.dataset.field] = event.target.type === 'number' ? Number(event.target.value) : event.target.value;
    target.source = '使用者修改';
    scenario.status = '使用者已修改';
    renderScenarioWorkspace();
  }));
}

function renderAssumptions(items) {
  state.assumptionBindings = items || [];
  $('assumptionList').className = '';
  $('assumptionList').innerHTML = T.AssumptionList(items);
  $('assumptionList').querySelectorAll('[data-assumption-index]').forEach(input => {
    input.addEventListener('input', event => {
      const assumption = state.assumptionBindings[Number(event.target.dataset.assumptionIndex)];
      if (!assumption) return;
      assumption.value = event.target.value;
      assumption.edited = true;
      const owner = state.scenarios.find(scenario => scenario.assumptions.includes(assumption));
      if (owner) {
        owner.status = '使用者已修改';
        rebuildConfirmedEvents();
        const card = document.querySelector(`[data-scenario-id="${CSS.escape(owner.id)}"]`);
        if (card) {
          const badge = card.querySelector('.status-badge');
          badge.className = 'status-badge status-使用者已修改';
          badge.textContent = '使用者已修改';
        }
        $('runBtn').disabled = true;
      }
      const settingMap = {
        年調薪率: 'raiseRate',
        年通膨率: 'inflationRate',
        緊急備用金目標: 'emergencyMonths',
        'Random seed': 'seed'
      };
      const setting = settingMap[assumption.label];
      if (setting && Number.isFinite(Number(event.target.value))) {
        $(setting).value = Number(event.target.value);
      }
    });
  });
}

function renderDraftAllocationEditor() {
  const total = Number($('variableExpense').value) || 0;
  const allocation = T.allocationFromTotal(total, state.allocationRatios, state.categories.length ? '使用者修改' : '系統預設');
  $('draftAllocationEditor').hidden = false;
  $('draftAllocationEditor').innerHTML = `
    <p class="notice">總額固定為 ${currency(total)}；比例會自動正規化為 100%。未修改前來源為「系統預設」。</p>
    <div class="allocation-input-grid">${allocation.map(item => `
      <label>${item.label}
        <span><input type="number" min="0" step="0.1" value="${item.percentage}" data-allocation-category="${item.category}"> %</span>
        <small>${currency(item.monthly_amount)}</small>
      </label>`).join('')}</div>`;
  $('draftAllocationEditor').querySelectorAll('[data-allocation-category]').forEach(input => {
    input.addEventListener('change', event => {
      state.allocationRatios[event.target.dataset.allocationCategory] = Number(event.target.value) || 0;
      state.allocationRatios = T.normalizePercentages(state.allocationRatios);
      state.categories = allocationToCategories(total);
      $('advancedMode').checked = true;
      const scenario = activeScenario();
      if (scenario && scenario.status !== '使用者已確認') scenario.status = '使用者已修改';
      renderDraftAllocationEditor();
      renderScenarioWorkspace();
    });
  });
}

function ensureChartEmpty(canvas, message) {
  let empty = canvas.parentElement.querySelector('.chart-empty');
  if (!empty) {
    empty = document.createElement('div');
    empty.className = 'chart-empty';
    empty.textContent = message;
    canvas.parentElement.prepend(empty);
  }
  return empty;
}

function chartOptions(unit, legend = true) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: {
        display: legend,
        onClick: () => {}
      },
      tooltip: {
        callbacks: {
          label(context) {
            if (context.raw?.meta) {
              const marker = context.raw.meta;
              return [
                marker.name,
                `月份：${marker.period ? T.formatPeriod(marker.period) : '依模擬年月'}`,
                `成本：${currency(marker.cost)}`,
                `分類：${marker.category}`,
                `來源：${marker.source}`,
                `資產影響：${T.formatDifference(marker.effect_on_assets)}`
              ];
            }
            return `${context.dataset.label}: ${Number(context.raw || 0).toLocaleString('zh-TW')}`;
          }
        }
      }
    },
    scales: {
      y: { ticks: { callback: value => Number(value).toLocaleString('zh-TW') }, title: { display: true, text: unit } },
      x: { grid: { display: false } }
    }
  };
}

function createChartController({ key, canvas, emptyMessage, hasData, build }) {
  const empty = ensureChartEmpty(canvas, emptyMessage || '尚無模擬資料。');
  const controller = {
    chart: null,
    destroy() {
      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }
      delete canvas.dataset.markerCount;
    },
    render(data, metadata = {}) {
      this.destroy();
      if (!hasData(data)) {
        empty.hidden = false;
        canvas.hidden = true;
        return;
      }
      empty.hidden = true;
      canvas.hidden = false;
      this.chart = new Chart(canvas, build(data, metadata));
      canvas.dataset.markerCount = String(metadata.markers?.length || 0);
      canvas.dataset.legendClickDisabled = 'true';
    }
  };
  chartControllers[key] = controller;
}

function setupCharts() {
  createChartController({
    key: 'balance',
    canvas: $('balanceChart'),
    emptyMessage: '尚無模擬資料，請先確認 AI 建立的情境並執行模擬。',
    hasData: rows => Array.isArray(rows) && rows.some(row => Number.isFinite(Number(row.balance))),
    build: (rows, metadata) => {
      const labels = rows.map(row => T.formatPeriod(T.periodForMonth(state.referenceDate, row.month)));
      const markerDatasets = (metadata.markers || []).map((marker, index) => {
        const row = rows.find(item => item.month === marker.month);
        return {
          type: 'scatter',
          label: marker.name,
          data: row ? [{ x: T.formatPeriod(T.periodForMonth(state.referenceDate, marker.month)), y: row.balance, meta: { ...marker, period: marker.period || T.periodForMonth(state.referenceDate, marker.month) } }] : [],
          pointRadius: 6,
          pointHoverRadius: 8,
          pointStyle: 'triangle',
          backgroundColor: index % 2 ? '#dc2626' : '#f59e0b',
          borderColor: '#fff',
          borderWidth: 1.5
        };
      });
      return {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: '每月資產',
            data: rows.map(row => row.balance),
            borderColor: '#047857',
            backgroundColor: 'rgba(4,120,87,.12)',
            borderWidth: 2,
            pointRadius: 0,
            tension: .22,
            fill: true
          }, ...markerDatasets]
        },
        options: chartOptions('金額 TWD', false)
      };
    }
  });

  createChartController({
    key: 'cashflow',
    canvas: $('cashflowChart'),
    hasData: rows => Array.isArray(rows) && rows.length > 0,
    build: rows => ({
      type: 'bar',
      data: {
        labels: rows.map(row => T.formatPeriod(T.periodForMonth(state.referenceDate, row.month))),
        datasets: [
          { label: '收入', data: rows.map(row => row.income), backgroundColor: 'rgba(4,120,87,.55)' },
          { label: '總支出', data: rows.map(row => row.expense + row.debt_payment), backgroundColor: 'rgba(220,38,38,.45)' }
        ]
      },
      options: chartOptions('金額 TWD')
    })
  });

  createChartController({
    key: 'fsi',
    canvas: $('fsiChart'),
    hasData: rows => Array.isArray(rows) && rows.length > 0,
    build: rows => ({
      type: 'line',
      data: {
        labels: rows.map(row => T.formatPeriod(T.periodForMonth(state.referenceDate, row.month))),
        datasets: [{ label: 'FSI', data: rows.map(row => row.fsi), borderColor: '#7c3aed', pointRadius: 0, tension: .2 }]
      },
      options: chartOptions('FSI', false)
    })
  });

  createChartController({
    key: 'category',
    canvas: $('categoryChart'),
    hasData: items => Array.isArray(items) && items.length > 0,
    build: items => ({
      type: 'doughnut',
      data: {
        labels: items.map(item => T.CATEGORY_LABELS[item.category] || item.category),
        datasets: [{ data: items.map(item => item.baseline), backgroundColor: ['#047857', '#0f3f91', '#7c3aed', '#dc2626', '#f59e0b', '#0891b2', '#16a34a', '#475569'] }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { onClick: () => {} } } }
    })
  });

  createChartController({
    key: 'mc',
    canvas: $('mcChart'),
    hasData: paths => Array.isArray(paths) && paths.some(path => path.points?.length),
    build: paths => ({
      type: 'line',
      data: {
        labels: paths[0].points.map(point => T.formatPeriod(T.periodForMonth(state.referenceDate, point.month))),
        datasets: paths.map((path, index) => ({ label: `Path ${index + 1}`, data: path.points.map(point => point.balance), borderWidth: 1.2, pointRadius: 0 }))
      },
      options: chartOptions('金額 TWD')
    })
  });

  createChartController({
    key: 'comparison',
    canvas: $('comparisonChart'),
    hasData: items => Array.isArray(items) && items.filter(Boolean).length > 0,
    build: items => ({
      type: 'bar',
      data: {
        labels: items.map(item => item.name),
        datasets: [
          { label: '期末資產', data: items.map(item => item.simulation_summary.final_balance), backgroundColor: 'rgba(4,120,87,.55)' },
          { label: '最低資產', data: items.map(item => item.simulation_summary.min_balance), backgroundColor: 'rgba(15,63,145,.45)' }
        ]
      },
      options: chartOptions('金額 TWD')
    })
  });
}

function renderCostBreakdown(data) {
  if (!data) {
    $('costBreakdown').className = 'cost-breakdown empty-state';
    $('costBreakdown').textContent = '尚未執行模擬。';
    return;
  }
  const items = [
    ['一般每月支出', data.normal_monthly_expenses],
    ['一次性情境支出', data.one_time_scenario_expenses],
    ['週期性情境支出', data.recurring_scenario_expenses],
    ['被取代的支出', data.replaced_expenses],
    ['抵銷', -Number(data.offsets || 0)],
    ['每月淨增加或減少', data.net_monthly_change]
  ];
  $('costBreakdown').className = 'cost-breakdown';
  $('costBreakdown').innerHTML = items.map(([label, value]) => `
    <div><span>${label}</span><strong>${label.includes('淨') || label === '抵銷' ? T.formatDifference(value) : currency(value)}</strong></div>`).join('');
}

function renderTransparency(result) {
  const transparency = result.transparency || {};
  $('financialImpact').className = '';
  $('financialImpact').innerHTML = T.FinancialImpactSummary(transparency.financial_impact);
  $('aiActionTimeline').className = 'details-body';
  $('aiActionTimeline').innerHTML = T.AIActionTimeline(transparency.actions);
  $('variableExpenseAllocation').innerHTML = T.VariableExpenseAllocation(transparency.expense_allocation);
  $('expenseComparison').innerHTML = T.ExpenseComparisonTable(transparency.expense_comparison);
  $('allocationNotice').textContent = `比較月份：${transparency.comparison_period ? T.formatPeriod(transparency.comparison_period) : '依模擬年月'}。比例總計 100%；系統模擬假設與 AI 語意解析都不是已確認事實。`;
  renderCostBreakdown(transparency.cost_breakdown);
  const scenarioAssumptions = state.scenarios
    .filter(item => item.status === '使用者已確認')
    .flatMap(item => item.assumptions || []);
  renderAssumptions([...scenarioAssumptions, ...(transparency.assumptions || []).map((item, index) => ({
    key: `engine-${index}`,
    label: item.label,
    value: String(item.value ?? ''),
    suggested_value: String(item.value ?? ''),
    source: item.source,
    editable: item.editable
  }))]);
  const scenarioSources = state.scenarios.flatMap(item => item.sources || []);
  $('sourceList').className = 'details-body';
  $('sourceList').innerHTML = T.SourceList([...scenarioSources, ...(transparency.sources || []).map(item => ({ ...item, value: item.value || '' }))]);
  chartControllers.balance.render(result.simulation_curve, { markers: transparency.event_markers || [] });
  chartControllers.cashflow.render(result.simulation_curve);
  chartControllers.fsi.render(result.simulation_curve);
}

function renderSimulation(result) {
  state.lastSimulation = result;
  $('resultMessage').textContent = `後端已完成 ${result.simulation_curve.length} 個月份的基準與情境比較。所有影響值皆由財務引擎計算。`;
  renderTransparency(result);
}

function resetResults() {
  state.lastSimulation = null;
  $('resultMessage').textContent = '尚無模擬資料。財務影響只會使用後端引擎的基準與情境模擬結果。';
  $('financialImpact').className = 'empty-state';
  $('financialImpact').textContent = '請先確認情境並執行模擬。';
  $('aiActionTimeline').className = 'details-body empty-state';
  $('aiActionTimeline').textContent = '尚未執行模擬。';
  $('variableExpenseAllocation').innerHTML = '';
  $('expenseComparison').innerHTML = '';
  renderCostBreakdown(null);
  ['balance', 'cashflow', 'fsi'].forEach(key => chartControllers[key].render([]));
}

async function runSimulation(button = $('runBtn'), allowPending = false) {
  if (!state.profileMode) {
    toast('請先用 AI 建立並確認財務資料，或選擇手動填寫', 'error');
    $('onboarding').scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  if (!allowPending && pendingScenarios().length) {
    toast('尚有 AI 情境等待確認，請先加入模擬或取消', 'error');
    return;
  }
  setLoading(button, true);
  try {
    rebuildConfirmedEvents();
    const data = await api('/simulate', { method: 'POST', body: JSON.stringify(basePayload()) });
    renderSimulation(data.result);
    toast('模擬完成');
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setLoading(button, false);
    renderScenarioWorkspace();
  }
}

function renderCategories(items) {
  state.categories = items.map(item => ({
    category: item.category,
    baseline: item.amount,
    monthly_volatility: 0.08,
    annual_inflation_rate: Number($('inflationRate').value) || 0.02,
    income_elasticity: 0.1,
    seasonal_factors: [1, 1, 1, 1, 1, 1, 1.05, 1.05, 1, 1, 1.1, 1.15],
    minimum: null,
    maximum: null,
    enabled: true
  }));
  $('categoryList').classList.remove('empty');
  $('categoryList').innerHTML = state.categories.map((item, index) => `
    <div class="category-row">
      <label><input type="checkbox" ${item.enabled ? 'checked' : ''} data-category-index="${index}" data-field="enabled"> ${T.CATEGORY_LABELS[item.category] || item.category}</label>
      <input type="number" value="${item.baseline}" data-category-index="${index}" data-field="baseline" aria-label="${item.category} 每月金額" title="每月金額">
      <input type="number" value="${item.monthly_volatility}" step="0.01" data-category-index="${index}" data-field="monthly_volatility" aria-label="${item.category} 月波動" title="月波動">
      <input type="number" value="${item.annual_inflation_rate}" step="0.01" data-category-index="${index}" data-field="annual_inflation_rate" aria-label="${item.category} 年通膨" title="年通膨">
      <input type="number" value="${item.income_elasticity}" step="0.01" data-category-index="${index}" data-field="income_elasticity" aria-label="${item.category} 收入彈性" title="收入彈性">
      <input type="number" value="${item.minimum ?? ''}" data-category-index="${index}" data-field="minimum" aria-label="${item.category} 最小值" title="最小值">
      <input type="number" value="${item.maximum ?? ''}" data-category-index="${index}" data-field="maximum" aria-label="${item.category} 最大值" title="最大值">
      <input value="${item.seasonal_factors.join(',')}" data-category-index="${index}" data-field="seasonal_factors" aria-label="${item.category} 季節係數" title="12 個月份季節係數">
    </div>`).join('');
  $('categoryList').querySelectorAll('[data-category-index]').forEach(input => {
    const update = event => {
      const item = state.categories[Number(event.target.dataset.categoryIndex)];
      const field = event.target.dataset.field;
      if (field === 'enabled') item[field] = event.target.checked;
      else if (field === 'seasonal_factors') {
        const values = event.target.value.split(',').map(value => Number(value.trim())).filter(Number.isFinite);
        item[field] = values.length === 12 ? values : [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1];
      } else if (field === 'minimum' || field === 'maximum') item[field] = event.target.value === '' ? null : Number(event.target.value);
      else item[field] = Number(event.target.value);
      chartControllers.category.render(state.categories.filter(category => category.enabled));
    };
    input.addEventListener('input', update);
    input.addEventListener('change', update);
  });
  chartControllers.category.render(state.categories.filter(item => item.enabled));
}

async function sendScenarioMessage() {
  const text = $('scenarioText').value.trim();
  if (!text) return;
  appendChatMessage('user', text);
  $('scenarioText').value = '';
  const directReply = directReplyForInput(text);
  if (directReply) {
    appendChatMessage('assistant', directReply);
    $('scenarioText').focus();
    return;
  }
  const button = $('parseScenarioBtn');
  setLoading(button, true, '…');
  const loading = appendChatMessage('assistant', '正在理解你的計畫…', { loading: true });
  try {
    const data = await api('/ai/parse-scenario', {
      method: 'POST',
      body: JSON.stringify({
        text,
        months: Number($('months').value) || 60,
        reference_date: state.referenceDate,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Taipei',
        profile_draft_id: state.profileDraft?.status === 'confirmed' ? state.profileDraft.id : null
      })
    });
    loading.remove();
    if (data.clarification) {
      appendChatMessage('assistant', scenarioClarificationText(data.clarification));
      return;
    }
    if (!data.events.length && !data.expense_adjustments.length) {
      appendChatMessage('assistant', '我還找不到可模擬的財務變化。請補充計畫發生的時間，以及收入或支出大約會改變多少。');
      return;
    }
    const scenario = T.createScenarioModel(data, `scenario-${Date.now()}`);
    state.scenarios.push(scenario);
    state.activeScenarioId = scenario.id;
    appendChatMessage('assistant', `${data.summary} 我建立了 ${data.events.length} 個事件與 ${data.expense_adjustments.length} 個分類調整。請先檢查摘要、假設與估算，再決定是否加入模擬。`);
    renderScenarioWorkspace();
    $('scenarioReview').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    loading.remove();
    appendChatMessage('assistant', `目前無法整理這個情境：${error.message}。請稍後再試一次。`);
  } finally {
    setLoading(button, false);
    $('scenarioText').focus();
  }
}

document.querySelectorAll('#scenarioReview .review-grid input').forEach(input => {
  input.addEventListener('input', () => {
    const scenario = activeScenario();
    if (!scenario) return;
    readReviewForm(scenario);
    const card = document.querySelector(`[data-scenario-id="${CSS.escape(scenario.id)}"]`);
    if (card) {
      card.querySelector('h3').textContent = scenario.title;
      const badge = card.querySelector('.status-badge');
      badge.className = 'status-badge status-使用者已修改';
      badge.textContent = '使用者已修改';
    }
  });
});

$('parseScenarioBtn').addEventListener('click', sendScenarioMessage);
$('scenarioText').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendScenarioMessage();
  }
});

$('runBtn').addEventListener('click', event => runSimulation(event.currentTarget));
$('modifyScenarioBtn').addEventListener('click', () => $('reviewTitle').focus());
$('modifyAllocationBtn').addEventListener('click', () => {
  $('expenseAllocationPanel').open = true;
  renderDraftAllocationEditor();
  $('expenseAllocationPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

$('restoreScenarioBtn').addEventListener('click', () => {
  const scenario = activeScenario();
  if (!scenario) return;
  const restored = T.createScenarioModel({
    display: scenario.original.display,
    events: scenario.original.events,
    expense_adjustments: scenario.original.adjustments,
    confidence: scenario.confidence,
    warnings: scenario.warnings
  }, scenario.id);
  const index = state.scenarios.findIndex(item => item.id === scenario.id);
  state.scenarios[index] = restored;
  renderScenarioWorkspace();
  toast('已恢復 AI 建議值');
});

$('confirmScenarioBtn').addEventListener('click', event => {
  const scenario = activeScenario();
  if (!scenario) return toast('請先建立情境', 'error');
  readReviewForm(scenario, false);
  applyReviewToEvents(scenario);
  scenario.status = '使用者已確認';
  rebuildConfirmedEvents();
  appendChatMessage('assistant', `「${scenario.title}」已加入模擬。現在只會使用你確認過的事件與假設。`);
  renderScenarioWorkspace();
  runSimulation(event.currentTarget, true);
});

$('cancelScenarioBtn').addEventListener('click', () => {
  const scenario = activeScenario();
  if (!scenario) return;
  state.scenarios = state.scenarios.filter(item => item.id !== scenario.id);
  state.activeScenarioId = state.scenarios.at(-1)?.id || null;
  rebuildConfirmedEvents();
  renderScenarioWorkspace();
  toast('已取消情境');
});

$('clearScenarioBtn').addEventListener('click', () => {
  state.scenarios = [];
  state.activeScenarioId = null;
  state.events = [];
  $('chatLog').innerHTML = initialChatMarkup;
  $('scenarioText').value = '';
  renderScenarioWorkspace();
  resetResults();
  toast('已重新開始對話');
});

$('editAssumptionsBtn').addEventListener('click', () => {
  $('assumptionPanel').open = true;
  $('assumptionList').querySelector('input:not(:disabled)')?.focus();
});

$('restoreAssumptionsBtn').addEventListener('click', () => {
  const scenario = activeScenario();
  if (!scenario) return toast('目前沒有可恢復的情境假設', 'error');
  scenario.assumptions = T.restoreCanonicalAssumptions(
    scenario.original.display.assumptions
  );
  renderScenarioWorkspace();
  toast('已恢復建議假設');
});

$('rerunSimulationBtn').addEventListener('click', event => runSimulation(event.currentTarget));

$('categorizeBtn').addEventListener('click', async event => {
  setLoading(event.currentTarget, true);
  try {
    const data = await api('/ai/categorize-expenses', {
      method: 'POST',
      body: JSON.stringify({ total_variable_expense: Number($('variableExpense').value) || 0 })
    });
    renderCategories(data.categories);
    $('advancedMode').checked = true;
    toast('支出分類已產生，可在進階設定中編輯');
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setLoading(event.currentTarget, false);
  }
});

$('runMcBtn').addEventListener('click', async event => {
  setLoading(event.currentTarget, true);
  try {
    rebuildConfirmedEvents();
    const payload = {
      ...basePayload(),
      simulations: Number($('iterations').value) || 300,
      sample_paths: Number($('samplePaths').value) || 8
    };
    const data = await api('/monte-carlo', { method: 'POST', body: JSON.stringify(payload) });
    state.lastMonteCarlo = data;
    $('mcPercentiles').textContent = `${currency(data.percentiles.p5)} / ${currency(data.percentiles.p50)} / ${currency(data.percentiles.p95)}`;
    $('mcBankrupt').textContent = T.formatPercent(data.bankrupt_probability);
    $('mcFsi').textContent = data.avg_max_fsi;
    chartControllers.mc.render(data.sample_paths);
    if (state.lastSimulation?.transparency?.financial_impact) {
      const impact = state.lastSimulation.transparency.financial_impact;
      impact.negative_balance_probability = { before: null, after: data.probability_negative_balance, difference: null };
      impact.monte_carlo_risk_probability = { before: null, after: data.bankrupt_probability, difference: null };
      $('financialImpact').innerHTML = T.FinancialImpactSummary(impact);
    }
    toast('Monte Carlo 完成');
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setLoading(event.currentTarget, false);
  }
});

$('optimizeBtn').addEventListener('click', async event => {
  setLoading(event.currentTarget, true);
  try {
    const data = await api('/optimize', {
      method: 'POST',
      body: JSON.stringify({
        profile: buildProfile(),
        months: Number($('months').value) || 60,
        seed: Number($('seed').value) || 42,
        constraints: {
          bankruptcy_probability_below: Number($('limitBankrupt').value) || 0.1,
          minimum_emergency_months_above: Number($('limitEmergency').value) || 3,
          maximum_fsi_below: Number($('limitFsi').value) || 0.6,
          balance_must_not_be_negative: $('limitNoNegative').checked
        }
      })
    });
    state.lastOptimization = data;
    $('optimizeOutput').textContent = JSON.stringify(data, null, 2);
    const options = [data.best_scenario, ...(data.feasible_scenarios || [])].filter(Boolean).slice(0, 6);
    chartControllers.comparison.render(options);
    toast('最佳化完成');
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setLoading(event.currentTarget, false);
  }
});

$('reportBtn').addEventListener('click', async event => {
  if (!state.lastSimulation) return toast('請先執行模擬', 'error');
  setLoading(event.currentTarget, true);
  try {
    const data = await api('/ai/generate-report', {
      method: 'POST',
      body: JSON.stringify({
        simulation_result: state.lastSimulation,
        monte_carlo_result: state.lastMonteCarlo,
        comparison_result: state.lastOptimization
      })
    });
    $('reportOutput').classList.remove('empty');
    $('reportOutput').innerHTML = `<h3>${T.escapeHtml(data.title)}</h3>${data.sections.map(section => `
      <article><h4>${T.escapeHtml(section.title)}</h4><p>${T.escapeHtml(section.body)}</p></article>`).join('')}`;
    toast('報告已生成');
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setLoading(event.currentTarget, false);
  }
});

$('startAiOnboardingBtn').addEventListener('click', () => {
  setProfileSetupMode('ai');
});

$('startManualProfileBtn').addEventListener('click', openManualProfile);
$('useManualFallbackBtn').addEventListener('click', openManualProfile);
$('sendOnboardingBtn').addEventListener('click', sendOnboardingMessage);
$('onboardingText').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendOnboardingMessage();
  }
});
$('openDraftReviewBtn').addEventListener('click', () => renderProfileDraft(true));

$('restartOnboardingBtn').addEventListener('click', () => {
  state.profileDraft = null;
  state.profileMode = null;
  $('runBtn').disabled = true;
  $('profile').hidden = true;
  $('profileDraftReview').hidden = true;
  $('onboardingChatLog').innerHTML = initialOnboardingChatMarkup;
  $('onboardingText').value = '';
  $('onboardingStatus').textContent = '開始建立';
  $('onboardingStatus').className = 'draft-status status-review';
  persistDraftLocally();
  renderProfileDraft();
  toast('已建立新的空白對話');
});

$('cancelProfileDraftBtn').addEventListener('click', () => {
  $('profileDraftReview').hidden = true;
  $('onboarding').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

$('draftReviewRows').addEventListener('input', event => {
  const key = event.target.dataset.draftField;
  if (!key || !state.profileDraft) return;
  P.updateField(state.profileDraft, key, event.target.value);
  const row = event.target.closest('[data-field-row]');
  row?.classList.add('is-estimated');
  const source = row?.querySelector('.source-tag');
  if (source) {
    source.textContent = '使用者修改';
    source.className = 'source-tag source-user_modified';
  }
  const confidence = row?.querySelector('.confidence-value');
  if (confidence) {
    confidence.textContent = '高';
    if (confidence.nextElementSibling) confidence.nextElementSibling.textContent = '100%';
  }
  const reason = row?.querySelector('td:last-child small');
  if (reason) reason.textContent = '使用者在審核畫面修改';
  const checkbox = row?.querySelector('[data-confirm-field]');
  if (checkbox) {
    checkbox.checked = false;
    const label = checkbox.closest('label');
    if (label) label.lastChild.textContent = ' 等待確認';
  }
  $('confirmProfileDraftBtn').disabled = true;
  persistDraftLocally();
});

$('draftReviewRows').addEventListener('change', event => {
  const key = event.target.dataset.draftField;
  if (!key || !state.profileDraft) return;
  P.updateField(state.profileDraft, key, event.target.value);
  renderProfileDraft();
});

$('draftReviewRows').addEventListener('change', event => {
  const key = event.target.dataset.confirmField;
  if (!key || !state.profileDraft) return;
  state.profileDraft[key].confirmed = event.target.checked;
  renderProfileDraft();
});

$('draftAllocationRows').addEventListener('change', event => {
  const index = event.target.dataset.allocationAmount;
  if (index === undefined || !state.profileDraft) return;
  P.redistributeAllocation(
    state.profileDraft,
    Number(index),
    event.target.value,
    $('keepAllocationTotal').checked
  );
  renderProfileDraft();
});

$('draftAllocationRows').addEventListener('change', event => {
  const index = event.target.dataset.confirmAllocation;
  if (index === undefined || !state.profileDraft) return;
  state.profileDraft.variable_expense_allocation[Number(index)].confirmed = event.target.checked;
  renderProfileDraft();
});

$('draftFuturePlans').addEventListener('change', event => {
  const index = event.target.dataset.confirmPlan;
  if (index === undefined || !state.profileDraft) return;
  state.profileDraft.future_plans[Number(index)].confirmed = event.target.checked;
  renderProfileDraft();
});

$('confirmAllEstimatesBtn').addEventListener('click', () => {
  if (!state.profileDraft) return;
  P.FIELD_GROUPS.flatMap(group => group.fields).forEach(([key]) => {
    if (state.profileDraft[key]?.value !== null) state.profileDraft[key].confirmed = true;
  });
  state.profileDraft.variable_expense_allocation.forEach(item => { item.confirmed = true; });
  state.profileDraft.future_plans.forEach(item => { item.confirmed = true; });
  renderProfileDraft();
  toast('所有目前顯示的估算已標記為確認');
});

$('saveProfileDraftBtn').addEventListener('click', async event => {
  const button = event.currentTarget;
  setLoading(button, true);
  try {
    await saveProfileDraft();
    toast('草稿已儲存，尚未套用到正式財務資料');
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setLoading(button, false);
  }
});

$('confirmProfileDraftBtn').addEventListener('click', async event => {
  if (!state.profileDraft) return;
  const button = event.currentTarget;
  setLoading(button, true);
  try {
    await saveProfileDraft();
    const data = await api(`/financial-profile-drafts/${state.profileDraft.id}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ draft: state.profileDraft, explicit_confirmation: true })
    });
    state.profileDraft = data.draft;
    applyConfirmedDraft(data.profile);
    renderProfileDraft();
    appendOnboardingMessage('assistant', '財務資料已由你明確確認並套用。接下來可以建立未來情境或直接執行模擬。');
    $('profileDraftReview').hidden = true;
    $('profile').scrollIntoView({ behavior: 'smooth', block: 'start' });
    toast('財務資料已確認並套用');
  } catch (error) {
    toast(error.message, 'error');
    renderProfileDraft();
  } finally {
    setLoading(button, false);
  }
});

setupCharts();
const savedDraft = sessionStorage.getItem('finsim-profile-draft');
if (savedDraft) {
  try {
    state.profileDraft = JSON.parse(savedDraft);
    setProfileSetupMode('ai', { scroll: false });
    renderProfileDraft();
    if (state.profileDraft.status === 'confirmed') {
      applyConfirmedDraft(profileFromConfirmedDraft(state.profileDraft));
    }
  } catch {
    sessionStorage.removeItem('finsim-profile-draft');
  }
}
$('runBtn').disabled = !state.profileMode;
renderScenarioWorkspace();
resetResults();
