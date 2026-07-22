(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.FinSimProfileOnboarding = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const SOURCE_LABELS = {
    user_provided: '使用者提供',
    ai_extracted: 'AI 擷取',
    ai_estimated: 'AI 估算',
    historical_data: '歷史資料',
    system_default: '系統預設',
    external_research: '外部資料',
    user_modified: '使用者修改',
    backend_normalized: '系統計算'
  };

  const FIELD_GROUPS = [
    {
      key: 'assets',
      label: '資產',
      fields: [
        ['cash_and_deposits', '現金與存款', 'currency'],
        ['investments', '投資', 'currency'],
        ['other_assets', '其他資產', 'currency'],
        ['emergency_fund', '緊急預備金', 'currency']
      ]
    },
    {
      key: 'income',
      label: '收入',
      fields: [
        ['monthly_salary', '每月薪資', 'currency'],
        ['other_recurring_income', '其他固定收入', 'currency']
      ]
    },
    {
      key: 'expenses',
      label: '支出',
      fields: [
        ['fixed_expenses', '每月固定支出', 'currency'],
        ['total_variable_expenses', '每月變動支出', 'currency']
      ]
    },
    {
      key: 'debts',
      label: '債務',
      fields: [['monthly_debt_payments', '每月債務付款', 'currency']]
    },
    {
      key: 'preferences',
      label: '模擬偏好',
      fields: [
        ['simulation_months', '模擬期間（月）', 'number'],
        ['risk_preference', '風險偏好', 'text']
      ]
    }
  ];

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

  const escapeHtml = value => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  function sourceLabel(source) {
    return SOURCE_LABELS[source] || source || '尚未提供';
  }

  function confidenceLabel(confidence) {
    if (confidence >= 0.9) return '高';
    if (confidence >= 0.7) return '中';
    if (confidence > 0) return '低';
    return '未判定';
  }

  function isEstimated(field) {
    return ['ai_estimated', 'ai_extracted', 'system_default', 'backend_normalized'].includes(field?.source) && !field?.confirmed;
  }

  function frequencyLabel(frequency) {
    return ({ weekly: '每週', biweekly: '每兩週', monthly: '每月', quarterly: '每季', yearly: '每年' })[frequency] || frequency;
  }

  function completionForGroup(draft, group) {
    const complete = group.fields.filter(([key]) => draft?.[key]?.value !== null).length;
    return {
      complete,
      total: group.fields.length,
      percentage: Math.round(complete / group.fields.length * 100)
    };
  }

  function renderProgress(draft) {
    const groups = [
      ...FIELD_GROUPS,
      { key: 'allocation', label: '變動支出分配', fields: [] },
      { key: 'plans', label: '未來計畫', fields: [] }
    ];
    return groups.map(group => {
      let status;
      let hasData = false;
      if (group.key === 'allocation') {
        const items = draft.variable_expense_allocation || [];
        hasData = items.length > 0;
        status = { complete: items.filter(item => item.confirmed).length, total: 8, percentage: Math.round(items.filter(item => item.confirmed).length / 8 * 100) };
      } else if (group.key === 'plans') {
        const items = draft.future_plans || [];
        hasData = items.length > 0;
        status = { complete: items.filter(item => item.confirmed).length, total: Math.max(1, items.length), percentage: items.length ? Math.round(items.filter(item => item.confirmed).length / items.length * 100) : 0 };
      } else {
        hasData = group.fields.some(([key]) => draft?.[key]?.value !== null);
        status = completionForGroup(draft, group);
      }
      const state = status.percentage === 100
        ? '已完成'
        : status.percentage > 0
          ? '部分完成'
          : hasData ? '等待確認' : '尚未提供';
      return `
        <div class="draft-progress-row">
          <div><strong>${group.label}</strong><small>${state}</small></div>
          <div class="draft-progress-track"><span style="width:${status.percentage}%"></span></div>
          <b>${status.percentage}%</b>
        </div>`;
    }).join('');
  }

  function fieldRow(key, label, type, field) {
    const value = field?.value ?? '';
    const estimateClass = isEstimated(field) ? ' is-estimated' : '';
    return `
      <tr class="draft-field-row${estimateClass}" data-field-row="${key}">
        <th scope="row">${label}</th>
        <td>
          <input data-draft-field="${key}" type="${type === 'text' ? 'text' : 'number'}" min="0" value="${escapeHtml(value)}">
          ${field?.original_amount != null && field?.original_frequency
            ? `<small>原始：${escapeHtml(field.original_amount)}（${escapeHtml(frequencyLabel(field.original_frequency))}）</small>`
            : ''}
          ${field?.normalized_from ? `<small>換算：${escapeHtml(field.normalized_from)}</small>` : ''}
        </td>
        <td><span class="source-tag source-${field?.source || 'missing'}">${sourceLabel(field?.source)}</span></td>
        <td>
          <span class="confidence-value">${confidenceLabel(Number(field?.confidence || 0))}</span>
          <small>${Math.round(Number(field?.confidence || 0) * 100)}%</small>
        </td>
        <td>
          <label class="confirm-check">
            <input data-confirm-field="${key}" type="checkbox" ${field?.confirmed ? 'checked' : ''}>
            ${field?.confirmed ? '已確認' : '等待確認'}
          </label>
        </td>
        <td><small>${escapeHtml(field?.reason || '尚未提供')}</small></td>
      </tr>`;
  }

  function renderReview(draft) {
    const fieldGroups = FIELD_GROUPS.map(group => `
      <tbody>
        <tr class="draft-section-row"><th colspan="6">${group.label}</th></tr>
        ${group.fields.map(([key, label, type]) => fieldRow(key, label, type, draft[key])).join('')}
      </tbody>
    `).join('');
    const debts = (draft.debts || []).map(debt => `
      <tr class="draft-field-row is-estimated">
        <th scope="row">${escapeHtml(debt.name || '債務')}</th>
        <td>
          每月 NT$${Number(debt.monthly_payment?.value || 0).toLocaleString('zh-TW')}
          ${debt.remaining_months?.value != null ? `<small>剩餘 ${escapeHtml(debt.remaining_months.value)} 期</small>` : ''}
        </td>
        <td><span class="source-tag source-${debt.monthly_payment?.source || 'missing'}">${sourceLabel(debt.monthly_payment?.source)}</span></td>
        <td><span class="confidence-value">${confidenceLabel(Number(debt.monthly_payment?.confidence || 0))}</span></td>
        <td>等待確認</td>
        <td><small>${escapeHtml(debt.monthly_payment?.reason || '依使用者訊息擷取')}</small></td>
      </tr>`).join('');
    return fieldGroups + (debts ? `
      <tbody>
        <tr class="draft-section-row"><th colspan="6">債務明細</th></tr>
        ${debts}
      </tbody>` : '');
  }

  function renderAllocation(draft) {
    return (draft.variable_expense_allocation || []).map((item, index) => `
      <tr class="${!item.confirmed ? 'is-estimated' : ''}" data-allocation-index="${index}">
        <th scope="row">${CATEGORY_LABELS[item.category] || item.category}</th>
        <td><input data-allocation-amount="${index}" type="number" min="0" value="${item.amount}"></td>
        <td><strong>${Number(item.percentage).toFixed(1)}%</strong></td>
        <td><span class="source-tag source-${item.source}">${sourceLabel(item.source)}</span></td>
        <td><small>${escapeHtml(item.reason)}</small></td>
        <td><label class="confirm-check"><input data-confirm-allocation="${index}" type="checkbox" ${item.confirmed ? 'checked' : ''}> ${item.confirmed ? '已確認' : '提案'}</label></td>
      </tr>
    `).join('');
  }

  function updateField(draft, key, value) {
    const numeric = key !== 'risk_preference';
    draft[key] = {
      ...draft[key],
      value: numeric ? Math.max(0, Number(value) || 0) : String(value),
      source: 'user_modified',
      confidence: 1,
      confirmed: false,
      reason: '使用者在審核畫面修改'
    };
    draft.conflicts = [];
    draft.validation_errors = [];
    return draft;
  }

  function redistributeAllocation(draft, changedIndex, rawAmount, keepTotal) {
    const items = draft.variable_expense_allocation || [];
    if (!items.length) return draft;
    const total = Number(draft.total_variable_expenses.value || 0);
    const amount = Math.max(0, Number(rawAmount) || 0);
    items[changedIndex].amount = amount;
    items[changedIndex].source = 'user_modified';
    items[changedIndex].confirmed = false;
    items[changedIndex].reason = '使用者調整分類金額';

    if (keepTotal) {
      const others = items.filter((_, index) => index !== changedIndex);
      const remaining = Math.max(0, total - amount);
      const otherTotal = others.reduce((sum, item) => sum + Number(item.amount || 0), 0);
      let used = 0;
      others.forEach((item, index) => {
        const next = index === others.length - 1
          ? Math.max(0, total - amount - used)
          : Math.round(remaining * (otherTotal ? item.amount / otherTotal : 1 / others.length));
        item.amount = next;
        used += next;
      });
    } else {
      draft.total_variable_expenses = {
        ...draft.total_variable_expenses,
        value: items.reduce((sum, item) => sum + Number(item.amount || 0), 0),
        source: 'user_modified',
        confidence: 1,
        confirmed: false,
        reason: '依分類支出合計更新'
      };
    }
    const denominator = Number(draft.total_variable_expenses.value || 0);
    items.forEach(item => {
      item.percentage = denominator ? Math.round(item.amount / denominator * 10000) / 100 : 0;
    });
    if (items.length && denominator) {
      const percentageBeforeLast = items.slice(0, -1).reduce((sum, item) => sum + item.percentage, 0);
      items.at(-1).percentage = Math.round((100 - percentageBeforeLast) * 100) / 100;
    }
    return draft;
  }

  function clientValidation(draft) {
    const errors = [...(draft.validation_errors || [])].filter(error => !error.includes('變動支出分類合計'));
    const required = ['cash_and_deposits', 'monthly_salary', 'fixed_expenses', 'total_variable_expenses', 'simulation_months'];
    required.forEach(key => {
      if (draft[key]?.value === null || draft[key]?.value === '') errors.push('必要財務資料尚未完整。');
    });
    const total = Number(draft.total_variable_expenses?.value || 0);
    const allocation = (draft.variable_expense_allocation || []).reduce((sum, item) => sum + Number(item.amount || 0), 0);
    if (draft.variable_expense_allocation?.length && Math.abs(total - allocation) > 0.01) {
      errors.push(`變動支出分類合計 NT$${allocation.toLocaleString('zh-TW')}，必須等於總額 NT$${total.toLocaleString('zh-TW')}。`);
    }
    return [...new Set(errors)];
  }

  return {
    SOURCE_LABELS,
    FIELD_GROUPS,
    CATEGORY_LABELS,
    sourceLabel,
    confidenceLabel,
    isEstimated,
    renderProgress,
    renderReview,
    renderAllocation,
    updateField,
    redistributeAllocation,
    clientValidation
  };
});
