(function(root) {
  'use strict';

  function periodIndex(period) {
    if (typeof period !== 'string' || !/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(period)) {
      throw new Error('月份須為 YYYY-MM');
    }
    const [year, month] = period.split('-').map(Number);
    if (year < 1) throw new Error('年份須大於零');
    return year * 12 + month - 1;
  }

  function periodToMonth(startPeriod, period) {
    return periodIndex(period) - periodIndex(startPeriod) + 1;
  }

  function monthToPeriod(startPeriod, month) {
    if (!Number.isInteger(month) || month < 1) throw new Error('模擬月份須為正整數');
    const index = periodIndex(startPeriod) + month - 1;
    const year = Math.floor(index / 12);
    if (year > 9999) throw new Error('月份超過支援範圍');
    return `${String(year).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}`;
  }

  function number(value, label) {
    if (value == null || String(value).trim() === '' || !Number.isFinite(Number(value))) {
      throw new Error(`${label}須填寫有效數字`);
    }
    return Number(value);
  }

  // Return { request, warnings }; only request is sent to the calculation APIs.
  function buildSimulationRequest({profile, debts = [], events = [], startPeriod, months}) {
    periodIndex(startPeriod);
    if (!Number.isInteger(months) || months < 1 || months > 360) throw new Error('模擬期間須為 1–360 個月');
    if (!profile) throw new Error('請先儲存財務資料');
    const request = {profile: {
      salary: number(profile.monthly_income, '每月實領收入'),
      balance: number(profile.cash_balance, '可動用現金'),
      fixed_expense: number(profile.fixed_expense, '每月固定支出'),
      variable_expense: number(profile.variable_expense, '每月變動支出'),
      investment_value: number(profile.investment_value, '投資目前市值'),
      monthly_investment: number(profile.monthly_investment, '每月投資金額'),
      target_emergency_months: number(profile.emergency_target_months, '預備金目標月數')
    }, months, events: []};
    if (profile.raise_rate != null && profile.raise_rate !== '') {
      request.profile.raise_rate = number(profile.raise_rate, '年調薪率');
    }
    const warnings = [];
    for (const [index, debt] of debts.entries()) {
      const name = debt.name || `貸款 ${index + 1}`;
      const remaining = number(debt.remaining_months, `${name}剩餘期數`);
      if (!Number.isInteger(remaining) || remaining < 0) throw new Error(`${name}剩餘期數須為非負整數`);
      if (remaining === 0) { warnings.push(`略過「${name}」：貸款剩餘期數為 0。`); continue; }
      if (remaining > months) warnings.push(`截斷「${name}」：還款期間超過模擬期間，計算至第 ${months} 個月。`);
      request.events.push({type: 'range', name, start_month: 1, end_month: Math.min(remaining, months), monthly_amount: -number(debt.monthly_payment, `${name}每月還款`)});
    }
    for (const [index, event] of events.entries()) {
      const name = event.name || `事件 ${index + 1}`;
      if (!['one_time', 'range', 'salary_change'].includes(event.type)) {
        warnings.push(`略過「${name}」：${event.type === 'vehicle_purchase' ? '本次尚不支援購車事件' : '不支援的事件類型'}。`);
        continue;
      }
      try {
        const start = periodToMonth(startPeriod, event.start_period);
        if (start < 1 || start > months) {
          warnings.push(`略過「${name}」：開始月份${start < 1 ? '早於模擬起始月' : '晚於模擬期間'}。`);
          continue;
        }
        if (event.type === 'one_time') {
          request.events.push({type: 'one_time', name, month: start, amount: number(event.amount, `${name}金額`)});
        } else if (event.type === 'salary_change') {
          request.events.push({type: 'salary_change', name, start_month: start, new_salary: number(event.new_salary, `${name}新月薪`)});
        } else {
          let end = event.end_period ? periodToMonth(startPeriod, event.end_period) : months;
          if (end < start) throw new Error('結束月份早於開始月份');
          if (end > months) {
            warnings.push(`截斷「${name}」：結束月份超過模擬期間，計算至第 ${months} 個月。`);
            end = months;
          }
          request.events.push({type: 'range', name, start_month: start, end_month: end, monthly_amount: number(event.monthly_amount, `${name}每月金額`)});
        }
      } catch (error) {
        warnings.push(`略過「${name}」：${error.message}。`);
      }
    }
    return {request, warnings};
  }

  const api = {buildSimulationRequest, periodToMonth, monthToPeriod};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlannerModel = api;
})(globalThis);
