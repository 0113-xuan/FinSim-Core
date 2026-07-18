(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.FinSimTransparency = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const CATEGORY_LABELS = {
    food: '餐飲',
    transportation: '交通',
    shopping: '購物',
    entertainment: '娛樂',
    medical: '醫療',
    education: '教育',
    travel: '旅遊',
    other: '其他'
  };

  const SOURCE_LABELS = new Set([
    '使用者輸入',
    '使用者財務資料',
    '歷史支出資料',
    'AI 推估',
    '系統預設',
    '財務引擎計算',
    '使用者修改',
    '外部資料'
  ]);

  const DEFAULT_ALLOCATION = {
    food: 30,
    transportation: 17,
    shopping: 13,
    entertainment: 11,
    medical: 7,
    education: 7,
    travel: 7,
    other: 8
  };

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const formatCurrency = value => value == null
    ? '尚未計算'
    : `NT$${Number(value).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;

  const formatPercent = (value, fractionIsRatio = true) => {
    if (value == null) return '尚未計算';
    const number = Number(value) * (fractionIsRatio ? 100 : 1);
    return `${number.toFixed(1)}%`;
  };

  const formatMonths = value => value == null ? '尚未設定' : `${Number(value)} 個月`;
  const formatConfidence = value => value == null ? '尚未提供' : `${Math.round(Number(value) * 100)}%`;

  const formatDifference = (value, options = {}) => {
    if (value == null) return '尚未計算';
    const number = Number(value);
    if (Math.abs(number) < 0.005) return '無變化';
    const formatted = options.percent
      ? `${Math.abs(number * 100).toFixed(1)}%`
      : formatCurrency(Math.abs(number));
    return `${number > 0 ? '+' : '-'}${formatted}`;
  };

  const sourceLabel = value => SOURCE_LABELS.has(value) ? value : '系統預設';

  function normalizePercentages(input) {
    const values = Object.fromEntries(
      Object.keys(DEFAULT_ALLOCATION).map(key => [key, Math.max(0, Number(input?.[key] ?? 0))])
    );
    const total = Object.values(values).reduce((sum, value) => sum + value, 0);
    if (total <= 0) return { ...DEFAULT_ALLOCATION };
    const normalized = Object.fromEntries(
      Object.entries(values).map(([key, value]) => [key, Math.round(value / total * 10000) / 100])
    );
    const remainder = Math.round((100 - Object.values(normalized).reduce((sum, value) => sum + value, 0)) * 100) / 100;
    const largest = Object.keys(normalized).reduce((best, key) => normalized[key] > normalized[best] ? key : best, 'food');
    normalized[largest] = Math.round((normalized[largest] + remainder) * 100) / 100;
    return normalized;
  }

  function allocationFromTotal(total, ratios = DEFAULT_ALLOCATION, source = '系統預設') {
    const normalized = normalizePercentages(ratios);
    return Object.entries(normalized).map(([category, percentage]) => ({
      category,
      label: CATEGORY_LABELS[category],
      monthly_amount: Math.round(Number(total || 0) * percentage) / 100,
      percentage,
      source,
      scenario_changed: false
    }));
  }

  function createScenarioModel(parsed, id) {
    const display = parsed.display || {};
    const events = Array.isArray(parsed.events) ? structuredClone(parsed.events) : [];
    const adjustments = Array.isArray(parsed.expense_adjustments)
      ? structuredClone(parsed.expense_adjustments)
      : [];
    const starts = [...events, ...adjustments]
      .map(item => Number(item.start_month || item.month))
      .filter(Number.isFinite);
    const oneTime = events.reduce((sum, event) => {
      const value = event.type === 'one_time' ? event.amount : event.one_time_amount;
      return sum + Math.max(0, -Number(value || 0));
    }, 0);
    const recurring = events.reduce((sum, event) => (
      sum
      + Math.max(0, -Number(event.monthly_amount || 0))
      + Math.max(0, Number(event.category_monthly_adjustment || 0))
    ), 0) + adjustments.reduce((sum, item) => sum + Math.max(0, Number(item.monthly_amount || 0)), 0);
    return {
      id: id || display.id || `scenario-${Date.now()}`,
      title: display.title || events[0]?.name || 'AI 建立的財務情境',
      scenario_type: display.scenario_type || events[0]?.type || '生活事件',
      start_month: Number(display.start_month || Math.min(...starts, 1)),
      duration_months: Number(display.duration_months || 1),
      one_time_cost: Number(display.one_time_cost ?? oneTime),
      recurring_monthly_cost: Number(display.recurring_monthly_cost ?? recurring),
      low_estimate: Number(display.low_estimate ?? oneTime + recurring),
      expected_estimate: Number(display.expected_estimate ?? oneTime + recurring),
      high_estimate: Number(display.high_estimate ?? oneTime + recurring),
      confidence: Number(display.confidence ?? parsed.confidence ?? 0.5),
      status: display.status || '等待確認',
      assumptions: structuredClone(display.assumptions || []),
      sources: structuredClone(display.sources || []),
      events,
      expense_adjustments: adjustments,
      original: structuredClone({ display, events, adjustments }),
      warnings: [...(parsed.warnings || [])]
    };
  }

  function scenarioEvents(scenario, simulationMonths) {
    const events = structuredClone(scenario.events || []);
    const adjustments = (scenario.expense_adjustments || []).map(item => ({
      type: 'life_event',
      name: `支出調整：${CATEGORY_LABELS[item.category] || item.category}`,
      start_month: item.start_month,
      end_month: item.end_month || simulationMonths,
      monthly_amount: 0,
      category_monthly_adjustment: Number(item.monthly_amount || 0),
      variable_expense_multiplier: Number(item.multiplier || 1),
      target_expense_category: item.category,
      expense_role: item.expense_role || 'additional',
      source: 'ai',
      display_source: item.source || 'AI 推估',
      reason: item.reason || 'AI 建議的分類支出調整'
    }));
    return [...events, ...adjustments];
  }

  function scenarioContext(scenario) {
    return {
      id: scenario.id,
      title: scenario.title,
      scenario_type: scenario.scenario_type,
      start_month: Number(scenario.start_month),
      duration_months: Number(scenario.duration_months),
      one_time_cost: Number(scenario.one_time_cost),
      recurring_monthly_cost: Number(scenario.recurring_monthly_cost),
      low_estimate: Number(scenario.low_estimate),
      expected_estimate: Number(scenario.expected_estimate),
      high_estimate: Number(scenario.high_estimate),
      confidence: Number(scenario.confidence),
      status: scenario.status,
      assumptions: scenario.assumptions,
      sources: scenario.sources
    };
  }

  function ScenarioStatusBadge(status) {
    const statusClass = String(status || '').replace(/\s+/g, '');
    return `<span class="status-badge status-${escapeHtml(statusClass)}">${escapeHtml(status)}</span>`;
  }

  function ConfidenceIndicator(confidence) {
    const percentage = Math.max(0, Math.min(100, Math.round(Number(confidence || 0) * 100)));
    return `
      <div class="confidence" aria-label="信心程度 ${percentage}%">
        <span>信心程度</span>
        <div class="confidence-track"><i style="width:${percentage}%"></i></div>
        <strong>${percentage}%</strong>
      </div>`;
  }

  function ScenarioSummaryCard(scenario) {
    return `
      <article class="scenario-summary-card" data-scenario-id="${escapeHtml(scenario.id)}">
        <div class="scenario-card-head">
          <div><h3>${escapeHtml(scenario.title)}</h3><p>${escapeHtml(scenario.scenario_type)}</p></div>
          ${ScenarioStatusBadge(scenario.status)}
        </div>
        <dl class="summary-fields">
          <div><dt>開始</dt><dd>第 ${Number(scenario.start_month)} 個月</dd></div>
          <div><dt>期間</dt><dd>${formatMonths(scenario.duration_months)}</dd></div>
          <div><dt>一次性成本</dt><dd>${formatCurrency(scenario.one_time_cost)}</dd></div>
          <div><dt>每月週期成本</dt><dd>${formatCurrency(scenario.recurring_monthly_cost)}</dd></div>
          <div><dt>低 / 預期 / 高</dt><dd>${formatCurrency(scenario.low_estimate)} / ${formatCurrency(scenario.expected_estimate)} / ${formatCurrency(scenario.high_estimate)}</dd></div>
        </dl>
        ${ConfidenceIndicator(scenario.confidence)}
      </article>`;
  }

  function AIActionTimeline(actions) {
    return `<ol class="action-timeline">${(actions || []).map((action, index) => `
      <li><span>${index + 1}</span><p>${escapeHtml(action)}</p></li>`).join('')}</ol>`;
  }

  function AssumptionList(items) {
    if (!items?.length) return '<p class="empty">尚無額外假設。</p>';
    return `<div class="assumption-list">${items.map((item, index) => `
      <label class="assumption-row">
        <span>${escapeHtml(item.label)}</span>
        <input data-assumption-index="${index}" value="${escapeHtml(item.value)}" ${item.editable === false ? 'disabled' : ''}>
        <small>${sourceLabel(item.source)}${item.editable === false ? ' · 不可修改' : ' · 可修改'}</small>
      </label>`).join('')}</div>`;
  }

  function SourceList(items) {
    if (!items?.length) return '<p class="empty">尚無資料來源。</p>';
    return `<div class="source-list">${items.map(item => `
      <div>
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.value ?? '')}</span>
        <small>${sourceLabel(item.source)}${item.estimated ? ' · 估算值' : ''}</small>
      </div>`).join('')}</div>`;
  }

  function VariableExpenseAllocation(items) {
    if (!items?.length) return '<p class="empty">尚無支出分配資料。</p>';
    return `<div class="table-scroll"><table>
      <thead><tr><th>分類</th><th>每月金額</th><th>比例</th><th>分配來源</th><th>情境變更</th></tr></thead>
      <tbody>${items.map(item => `
        <tr>
          <th>${escapeHtml(item.label || CATEGORY_LABELS[item.category] || item.category)}</th>
          <td>${formatCurrency(item.monthly_amount)}</td>
          <td>${Number(item.percentage || 0).toFixed(2)}%</td>
          <td>${sourceLabel(item.source)}</td>
          <td>${item.scenario_changed ? '有變更' : '無變化'}</td>
        </tr>`).join('')}</tbody>
    </table></div>`;
  }

  function ExpenseComparisonTable(items) {
    if (!items?.length) return '<p class="empty">尚無比較資料。</p>';
    return `<div class="table-scroll"><table>
      <thead><tr><th>分類</th><th>原始支出</th><th>情境後支出</th><th>變化</th><th>變化原因</th><th>資料來源</th></tr></thead>
      <tbody>${items.map(item => `
        <tr>
          <th>${escapeHtml(item.label || CATEGORY_LABELS[item.category] || item.category)}</th>
          <td>${formatCurrency(item.original_amount)}</td>
          <td>${formatCurrency(item.adjusted_amount)}</td>
          <td class="${Number(item.difference) > 0 ? 'difference-up' : Number(item.difference) < 0 ? 'difference-down' : ''}">${formatDifference(item.difference)}</td>
          <td>${escapeHtml(item.reason || '無情境調整')}</td>
          <td>${sourceLabel(item.source)}</td>
        </tr>`).join('')}</tbody>
    </table></div>`;
  }

  function FinancialImpactSummary(impact) {
    const definitions = [
      ['final_assets', '期末資產', 'currency'],
      ['lowest_asset_balance', '期間最低資產', 'currency'],
      ['monthly_cash_flow', '每月現金流', 'currency'],
      ['emergency_fund_coverage', '緊急備用金覆蓋', 'months'],
      ['debt_to_income_ratio', '負債收入比', 'percent'],
      ['fsi', '最高 FSI', 'number'],
      ['negative_balance_probability', '負資產機率', 'percent'],
      ['monte_carlo_risk_probability', 'Monte Carlo 風險機率', 'percent'],
      ['first_high_risk_month', '首次高風險月份', 'month']
    ];
    const display = (value, type) => {
      if (value == null) return '尚未計算';
      if (type === 'currency') return formatCurrency(value);
      if (type === 'months') return `${Number(value).toFixed(1)} 月`;
      if (type === 'percent') return formatPercent(value);
      if (type === 'month') return `第 ${value} 個月`;
      return Number(value).toFixed(3);
    };
    const displayDifference = (value, type) => {
      if (type === 'month') return '比較月份';
      if (value == null) return '尚未計算';
      if (Math.abs(Number(value)) < 0.005) return '無變化';
      if (type === 'currency') return formatDifference(value);
      if (type === 'percent') return formatDifference(value, { percent: true });
      const sign = Number(value) > 0 ? '+' : '-';
      const absolute = Math.abs(Number(value));
      if (type === 'months') return `${sign}${absolute.toFixed(1)} 月`;
      return `${sign}${absolute.toFixed(3)}`;
    };
    return `<div class="impact-grid">${definitions.map(([key, label, type]) => {
      const item = impact?.[key] || {};
      return `
        <article>
          <span>${label}</span>
          <div><small>原始</small><strong>${display(item.before, type)}</strong></div>
          <div><small>情境後</small><strong>${display(item.after, type)}</strong></div>
          <em>${displayDifference(item.difference, type)}</em>
        </article>`;
    }).join('')}</div>`;
  }

  return {
    CATEGORY_LABELS,
    DEFAULT_ALLOCATION,
    escapeHtml,
    formatCurrency,
    formatPercent,
    formatMonths,
    formatConfidence,
    formatDifference,
    sourceLabel,
    normalizePercentages,
    allocationFromTotal,
    createScenarioModel,
    scenarioEvents,
    scenarioContext,
    ScenarioSummaryCard,
    ScenarioStatusBadge,
    AIActionTimeline,
    AssumptionList,
    SourceList,
    VariableExpenseAllocation,
    ExpenseComparisonTable,
    FinancialImpactSummary,
    ConfidenceIndicator
  };
});
