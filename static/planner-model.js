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
    const warnings = [], vehicles = [];
    // Debts stay liabilities: payments are deducted monthly and what is still owed reduces net worth.
    const existingDebts = [];
    for (const [index, debt] of debts.entries()) {
      const name = debt.name || `貸款 ${index + 1}`;
      const remaining = number(debt.remaining_months, `${name}剩餘期數`);
      if (!Number.isInteger(remaining) || remaining < 0) throw new Error(`${name}剩餘期數須為非負整數`);
      if (remaining === 0) { warnings.push(`略過「${name}」：貸款剩餘期數為 0。`); continue; }
      existingDebts.push({name, monthly_payment: number(debt.monthly_payment, `${name}每月還款`), remaining_months: remaining});
    }
    if (existingDebts.length) request.profile.existing_debts = existingDebts;
    for (const [index, event] of events.entries()) {
      const name = event.name || `事件 ${index + 1}`;
      if (!['one_time', 'range', 'salary_change', 'vehicle_purchase'].includes(event.type)) {
        warnings.push(`略過「${name}」：不支援的事件類型。`);
        continue;
      }
      try {
        const start = periodToMonth(startPeriod, event.start_period);
        if (start < 1 || start > months) {
          warnings.push(`略過「${name}」：開始月份${start < 1 ? '早於模擬起始月' : '晚於模擬期間'}。`);
          continue;
        }
        if (event.type === 'vehicle_purchase') {
          vehicles.push({name, purchase_period:event.start_period, details:structuredClone(event.details || {})});
        } else if (event.type === 'one_time') {
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
    return {request, warnings, vehicles};
  }

  const ownershipFields = ['annual_insurance','annual_tax','annual_maintenance_budget','monthly_fuel_or_energy','monthly_parking'];
  function vehicleDetails(values) {
    const details = {purchase_price:number(values.purchase_price, '車價'), payment_method:values.payment_method};
    if (values.vehicle_catalog_id) details.vehicle_catalog_id = values.vehicle_catalog_id;
    if (details.payment_method === 'financed') {
      details.down_payment = number(values.down_payment, '頭期款');
      details.loan_term_months = number(values.loan_term_months, '貸款期數');
      details.annual_interest_rate = number(values.annual_interest_rate, '年利率') / 100;
      if (!Number.isInteger(details.loan_term_months) || details.loan_term_months < 1) throw new Error('貸款期數須為正整數');
      if (details.down_payment < 0 || details.down_payment >= details.purchase_price) throw new Error('頭期款須為非負數且小於車價');
    } else if (details.payment_method !== 'cash') throw new Error('請選擇付款方式');
    if (details.purchase_price <= 0) throw new Error('車價須大於零');
    for (const key of ownershipFields) {
      if (values[key] != null && String(values[key]).trim() !== '') details[key] = number(values[key], '持有成本');
    }
    if (values.annual_depreciation_rate != null && String(values.annual_depreciation_rate).trim() !== '') {
      details.annual_depreciation_rate = number(values.annual_depreciation_rate, '折舊率') / 100;
      if (details.annual_depreciation_rate < 0 || details.annual_depreciation_rate > 1) throw new Error('折舊率須介於 0% 到 100%');
    }
    return details;
  }
  function vehicleAnalysisReason(startPeriod, purchasePeriod) {
    try {
      // The existing vehicle API treats start_period as the preceding base month.
      const month = periodToMonth(startPeriod, purchasePeriod) - 1;
      return month >= 1 && month <= 58 ? '' : '購車分析的購買月份須落在基準月後第 1 至 58 個月。';
    } catch (_) { return '購買月份格式無效，無法執行購車分析。'; }
  }
  function buildVehicleDecisionRequest({profile, debts = [], event, startPeriod}) {
    const reason = vehicleAnalysisReason(startPeriod, event.start_period);
    if (reason) throw new Error(reason);
    const payload = {scenario_type:'vehicle_purchase'};
    for (const [key,value] of Object.entries(event.details || {})) {
      if (['vehicle_catalog_id','annual_depreciation_rate','displacement_cc','fuel_type','insurance_items','has_parking_space','parking_lot_id'].includes(key) || value == null || value === '') continue;
      payload[key] = ['payment_method','loan_term_months'].includes(key) ? value : {value,source:'user_provided'};
    }
    const financial = {salary:number(profile.monthly_income,'每月實領收入'),
      fixed_expense:number(profile.fixed_expense,'固定支出'), variable_expense:number(profile.variable_expense,'變動支出'),
      balance:number(profile.cash_balance,'可動用現金'), required_monthly_debt:0,
      existing_debts:debts.map(debt=>({name:debt.name, monthly_payment:number(debt.monthly_payment,'每月還款'), remaining_months:number(debt.remaining_months,'剩餘期數')}))};
    if (profile.raise_rate != null && profile.raise_rate !== '') financial.raise_rate = number(profile.raise_rate,'年調薪率');
    const request = {profile:financial, start_period:startPeriod, scenario:{scenario_id:'planner-vehicle',
      scenario_type:'vehicle_purchase', horizon_months:60, target_period:event.start_period, payload}};
    if (event.details?.vehicle_catalog_id) request.vehicle_catalog_id = event.details.vehicle_catalog_id;
    return request;
  }

  function groupVehicleCatalog(catalog) {
    const brands = [...new Set(catalog.map(car=>car.brand))].sort((a,b)=>a.localeCompare(b,'en'));
    return brands.map(brand=>({brand, vehicles:catalog.filter(car=>car.brand===brand)
      .slice().sort((a,b)=>a.price_twd-b.price_twd || a.id.localeCompare(b.id,'en'))
      .map(car=>({...car, label:`${car.model} ${car.trim} · NT$${car.price_twd.toLocaleString('zh-TW')}`}))}));
  }
  // Amounts are typed as positive numbers; the income/expense choice sets the sign that is stored.
  function signedAmount(value, direction) {
    const amount = number(value, '金額');
    if (amount < 0) throw new Error('金額請填 0 以上的數字，收入或支出用上方選項決定');
    return direction === 'expense' && amount !== 0 ? -amount : amount;
  }
  function splitAmount(stored) {
    const amount = Number(stored);
    return {value: Math.abs(amount), direction: amount < 0 ? 'expense' : 'income'};
  }
  const api = {signedAmount, splitAmount, buildSimulationRequest, periodToMonth, monthToPeriod, ownershipFields, vehicleDetails, vehicleAnalysisReason, buildVehicleDecisionRequest, groupVehicleCatalog};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlannerModel = api;
})(globalThis);
