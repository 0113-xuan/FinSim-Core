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
    '使用者提供',
    '使用者財務資料',
    '歷史支出資料',
    'AI 語意判讀',
    'AI 語意解析',
    '系統預設',
    '系統假設值',
    '系統模擬假設',
    '財務引擎計算',
    '系統計算',
    '使用者修改',
    '外部資料',
    '外部資料估算',
    '來源未標示'
  ]);

  const SOURCE_LABEL_MAP = {
    manual: '使用者提供',
    user_provided: '使用者提供',
    '使用者輸入': '使用者提供',
    ai: 'AI 語意解析',
    ai_interpretation: 'AI 語意解析',
    ai_extracted: 'AI 語意解析',
    ai_estimated: 'AI 語意解析',
    'AI 語意判讀': 'AI 語意解析',
    system_assumption: '系統模擬假設',
    system_default: '系統模擬假設',
    '系統預設': '系統模擬假設',
    '系統假設值': '系統模擬假設',
    system: '系統計算',
    derived: '系統計算',
    backend_normalized: '系統計算',
    external_estimate: '外部資料估算',
    external_research: '外部資料估算'
  };

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
  const formatPeriod = value => {
    const match = /^(\d{4})-(\d{2})$/.exec(String(value || ''));
    return match ? `${match[1]}年${Number(match[2])}月` : '時間尚未確認';
  };
  const periodForMonth = (referenceDate, monthIndex) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(referenceDate || ''));
    if (!match || Number(monthIndex) < 1) return null;
    const absolute = Number(match[1]) * 12 + Number(match[2]) - 1 + Number(monthIndex);
    return `${Math.floor(absolute / 12)}-${String(absolute % 12 + 1).padStart(2, '0')}`;
  };
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

  const sourceLabel = value => SOURCE_LABEL_MAP[value]
    || (SOURCE_LABELS.has(value) ? value : '來源未標示');

  const itemSourceLabel = item => {
    const displaySource = typeof item?.display_source === 'string'
      ? item.display_source.trim()
      : '';
    return displaySource || sourceLabel(item?.source);
  };

  const restoreCanonicalAssumptions = originalItems => structuredClone(originalItems || []);

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
      start_period: display.start_period || events.find(item => item.start_period)?.start_period || null,
      end_period: display.end_period || null,
      original_target_date_text: display.original_target_date_text || null,
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
      start_period: item.start_period || null,
      end_month: item.end_month || simulationMonths,
      end_period: item.end_period || null,
      monthly_amount: 0,
      category_monthly_adjustment: Number(item.monthly_amount || 0),
      variable_expense_multiplier: Number(item.multiplier || 1),
      target_expense_category: item.category,
      expense_role: item.expense_role || 'additional',
      source: item.source || 'unknown',
      display_source: item.display_source || sourceLabel(item.source),
      reason: item.reason || '分類支出調整'
    }));
    return [...events, ...adjustments];
  }

  function scenarioContext(scenario) {
    return {
      id: scenario.id,
      title: scenario.title,
      scenario_type: scenario.scenario_type,
      start_month: Number(scenario.start_month),
      start_period: scenario.start_period,
      end_period: scenario.end_period,
      original_target_date_text: scenario.original_target_date_text,
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
          <div><dt>開始</dt><dd>${formatPeriod(scenario.start_period)}</dd></div>
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
        <small>${escapeHtml(itemSourceLabel(item))}${item.editable === false ? ' · 不可修改' : ' · 可修改'}</small>
      </label>`).join('')}</div>`;
  }

  function SourceList(items) {
    if (!items?.length) return '<p class="empty">尚無資料來源。</p>';
    return `<div class="source-list">${items.map(item => `
      <div>
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.value ?? '')}</span>
        <small>${escapeHtml(itemSourceLabel(item))}${item.estimated ? ' · 估算值' : ''}</small>
      </div>`).join('')}</div>`;
  }

  function ClarificationCandidateList(items) {
    return (items || []).map(item => (
      `${item.label}：每月 ${formatCurrency(item.monthly_amount)}`
      + `（${itemSourceLabel(item)}）；${Number(item.comparison_months || 60)} 個月合計 `
      + `${formatCurrency(item.derived_total)}（${item.derived_display_source || sourceLabel(item.derived_source)}）`
    )).join(' ');
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
          <td>${escapeHtml(itemSourceLabel(item))}</td>
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
          <td>${escapeHtml(itemSourceLabel(item))}</td>
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
      if (type === 'month') return typeof value === 'string' ? formatPeriod(value) : '依模擬年月';
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

  function ScenarioComparisonResult(response) {
    const baseline = response?.baseline?.option || {};
    const scenarioResult = response?.scenarios?.[0];
    const scenario = scenarioResult?.option || {};
    const request = scenario.scenario_request || {};
    const build = scenarioResult?.build || {};
    const delta = response?.deltas?.[0];
    const factRows = items => (items || []).map(item => `<tr>
      <td>${escapeHtml(item.field || '')}</td><td>${item.value == null ? '—' : formatCurrency(item.value)}</td>
      <td>${escapeHtml(item.display_source || sourceLabel(item.source))}</td><td>${escapeHtml(item.reason || '')}</td>
    </tr>`).join('');
    if (response?.baseline_only) {
      return `<section class="scenario-comparison"><h3>基準</h3><p>${escapeHtml(baseline.label || '目前財務狀況')}</p><p>此結果未加入任何情境事件、貸款或隱藏假設。</p></section>`;
    }
    if (!scenarioResult || !delta) return '<p>尚無可顯示的情境比較。</p>';
    const oneTime = (build.events || []).filter(item => item.type === 'one_time');
    const monthly = (build.events || []).filter(item => item.type === 'range');
    const metric = (label, value, period = false) => `<li><span>${label}</span><strong>${period ? formatPeriod(value) : formatCurrency(value)}</strong></li>`;
    return `<section class="scenario-comparison">
      <div><h3>基準</h3><p>${escapeHtml(baseline.label || '目前財務狀況')}</p></div>
      <div><h3>情境</h3><p>${escapeHtml(scenario.label || '')} · ${escapeHtml(request.scenario_type || '')} · ${formatPeriod(request.target_period)}</p></div>
      <h4>一次性變動</h4><ul>${oneTime.map(item => metric(item.name, Math.abs(Number(item.amount || 0)))).join('') || '<li>無</li>'}</ul>
      <h4>每月變動</h4><ul>${monthly.map(item => metric(item.name, Math.abs(Number(item.amount || 0)))).join('') || '<li>無</li>'}</ul>
      <h4>後端比較結果</h4><ul>
        ${metric('期末現金差額', delta.final_cash_difference)}
        ${metric('平均每月現金流差額', delta.average_monthly_cash_flow_difference)}
        ${metric('最低現金餘額', delta.minimum_cash_balance)}
        ${metric('最低餘額月份', delta.minimum_balance_period, true)}
        ${delta.first_deficit_period ? metric('首次赤字月份', delta.first_deficit_period, true) : '<li><span>首次赤字月份</span><strong>無赤字</strong></li>'}
        ${metric('新增債務', delta.total_new_debt)}${metric('總利息', delta.total_interest)}
        ${metric('一次性成本合計', delta.one_time_cost_total)}${metric('持續性成本合計', delta.recurring_cost_total)}
      </ul>
      <h4>假設與來源</h4><div class="table-wrap"><table><thead><tr><th>欄位</th><th>值</th><th>來源</th><th>理由</th></tr></thead><tbody>${factRows([...(build.assumptions || []), ...(build.derived_values || [])])}</tbody></table></div>
      ${(build.missing_fields || []).length ? `<p class="warning">待釐清：${escapeHtml(build.missing_fields.join(', '))}</p>` : ''}
      ${(build.warnings || []).map(item => `<p class="warning">${escapeHtml(item)}</p>`).join('')}
    </section>`;
  }

  function buildScenarioComparisonPayload(typedRequest, confirmedProfile, startPeriod, horizonMonths, baselineLoans = []) {
    if (!typedRequest || !confirmedProfile) return null;
    return {
      confirmed_profile: confirmedProfile,
      baseline_loans: baselineLoans,
      start_period: startPeriod,
      horizon_months: Number(horizonMonths),
      options: [
        { option_id: 'baseline', label: '目前財務狀況', is_baseline: true, scenario_request: null },
        { option_id: typedRequest.scenario_id, label: typedRequest.scenario_id, is_baseline: false, scenario_request: typedRequest }
      ]
    };
  }

  async function runTypedScenarioComparison({ parsed, confirmedProfile, baselineLoans = [], startPeriod, horizonMonths, request, render }) {
    if (!parsed?.typed_scenario_request) return { status: 'not_executable' };
    if (!confirmedProfile) return { status: 'missing_profile' };
    const payload = buildScenarioComparisonPayload(
      parsed.typed_scenario_request, confirmedProfile, startPeriod, horizonMonths, baselineLoans
    );
    const response = await request('/scenarios/compare', {
      method: 'POST', body: JSON.stringify(payload)
    });
    render(response);
    return { status: 'rendered', payload, response };
  }

  return {
    CATEGORY_LABELS,
    DEFAULT_ALLOCATION,
    escapeHtml,
    formatCurrency,
    formatPercent,
    formatMonths,
    formatPeriod,
    periodForMonth,
    formatConfidence,
    formatDifference,
    sourceLabel,
    itemSourceLabel,
    restoreCanonicalAssumptions,
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
    ClarificationCandidateList,
    VariableExpenseAllocation,
    ExpenseComparisonTable,
    FinancialImpactSummary,
    ScenarioComparisonResult,
    buildScenarioComparisonPayload,
    runTypedScenarioComparison,
    ConfidenceIndicator
  };
});
