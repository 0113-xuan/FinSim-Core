(function(root) {
  'use strict';
  const planner = typeof module !== 'undefined' && module.exports ? require('./planner-model.js') : root.PlannerModel;
  // Every amount is shown to the nearest 100 with no decimals; `+ 0` turns a rounded -0 into 0.
  const wholeDollars = new Intl.NumberFormat('zh-TW', {style:'currency',currency:'TWD',maximumFractionDigits:0});
  const money = value => value == null ? '不適用' : wholeDollars.format(Math.round(Number(value) / 100) * 100 + 0);
  // Whole percent; a real but tiny chance is said as such instead of rounding down to a reassuring 0%.
  const wholePercent = probability => probability > 0 && probability < 0.005 ? '不到 1%' : `${Math.round(probability * 100)}%`;
  function errorText(error) {
    const auth={invalid_credentials:'電子郵件或密碼不正確，請確認後再試',email_not_confirmed:'請先到信箱點確認連結後再登入',
      email_exists:'這個電子郵件已註冊，請改用登入',weak_password:'密碼強度不足，請使用較長且不易猜測的密碼',
      over_request_rate_limit:'嘗試次數過多，請稍候再試',over_email_send_rate_limit:'確認信寄送次數過多，請稍候再試'};
    if(auth[error?.code])return auth[error.code];
    const message=String(error?.message||error||'');
    return /[\u4e00-\u9fff]/.test(message)?message:'連線或資料操作失敗，請確認網路或重新登入後再試';
  }
  function financialSummary(profile, debts=[]) {
    const cash=Number(profile.cash_balance), investment=Number(profile.investment_value);
    const debtTotal=debts.reduce((total,debt)=>total+Number(debt.monthly_payment)*Number(debt.remaining_months),0);
    return {cash,investment,assets:cash+investment,debtTotal,netWorth:cash+investment-debtTotal};
  }
  // One month of a simulated plan. Assets stay cash plus investment, as in `financialSummary`, so a down payment shows as less assets;
  // the car's value only enters net worth.
  function snapshotAt(row, current) {
    const cash=Number(row.balance), investment=Number(row.investment_value), vehicle=Number(row.asset_value||0);
    const newLoan=Number(row.loan_balance||0), existingDebt=Number(row.existing_debt_balance||0);
    const assets=cash+investment, debtTotal=newLoan+existingDebt, netWorth=assets+vehicle-debtTotal;
    return {cash,investment,vehicle,newLoan,existingDebt,assets,debtTotal,netWorth,
      assetsChange:assets-current.assets,debtChange:debtTotal-current.debtTotal,netWorthChange:netWorth-current.netWorth};
  }
  function routeFor(page, session, profile) {
    if (!session?.user) return page === 'login' ? null : '/login.html';
    if (!profile) return page === 'onboarding' ? null : '/onboarding.html';
    return page === 'login' ? '/dashboard.html' : null;
  }
  function sortEvents(events) {
    return [...events].sort((a,b)=>String(a.start_period).localeCompare(String(b.start_period)) || String(a.created_at||'').localeCompare(String(b.created_at||'')) || String(a.id||'').localeCompare(String(b.id||'')));
  }
  const eventNames={one_time:'一次性收支',range:'期間每月收支',salary_change:'換工作',vehicle_purchase:'購車'};
  function eventSummary(event) {
    if (event.type==='one_time') return money(event.amount);
    if (event.type==='range') return `每月 ${money(event.monthly_amount)}，至 ${event.end_period||'模擬結束'}`;
    if (event.type==='salary_change') return `新月薪 ${money(event.new_salary)}`;
    if (event.type==='vehicle_purchase') {
      const d=event.details||{};
      const fees=[['annual_insurance','保險'],['annual_tax','稅費']].filter(([key])=>d[key]!=null)
        .map(([key,label])=>`${label} NT$${Number(d[key]).toLocaleString('zh-TW')}／年`);
      return `車價 ${money(d.purchase_price)}，${d.payment_method==='financed'?`貸款 ${d.loan_term_months} 期`:'現金購買'}${fees.length?'，'+fees.join('、'):''}`;
    }
    return '不支援的事件類型';
  }
  function chartData(curve,startPeriod,events=[],profile=null,debts=[]) {
    const labels=curve.map(row=>planner.monthToPeriod(startPeriod,row.month));
    const cash=curve.map(row=>Number(row.balance)), netWorth=curve.map(row=>Number(row.net_worth));
    if(profile) {
      // The initial position is the preceding month-end; month 1 is the first projected month-end.
      const [year,month]=startPeriod.split('-').map(Number), previous=year*12+month-2;
      labels.unshift(`${String(Math.floor(previous/12)).padStart(4,'0')}-${String(previous%12+1).padStart(2,'0')}`);
      cash.unshift(Number(profile.cash_balance)); netWorth.unshift(financialSummary(profile,debts).netWorth);
    }
    const markers=sortEvents(events).flatMap(event=>{
      const index=labels.indexOf(event.start_period);
      return index<0 || (profile && index===0) ? [] : [{index,period:event.start_period,name:event.name}];
    });
    const summarize=values=>{
      if(!values.length)return null;
      const minimum=Math.min(...values), index=values.indexOf(minimum);
      return {initial:values[0],final:values.at(-1),minimum,minimumPeriod:labels[index],initialPeriod:labels[0]};
    };
    return {labels,cash,netWorth,markers,summary:{cash:summarize(cash),netWorth:summarize(netWorth)}};
  }
  const api={money,wholePercent,errorText,financialSummary,snapshotAt,routeFor,sortEvents,eventNames,eventSummary,chartData};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ShellModel=api;
})(globalThis);
