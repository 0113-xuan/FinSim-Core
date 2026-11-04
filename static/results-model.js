(function(root) {
  'use strict';
  // Pure transforms for the plan page's results: percentile bands, the cash/investment split and
  // the assumptions panel. No DOM access, so node tests can cover them.
  const node = typeof module !== 'undefined' && module.exports;
  const planner = node ? require('./planner-model.js') : root.PlannerModel;
  const shell = node ? require('./shell-model.js') : root.ShellModel;
  const percent = value => `${new Intl.NumberFormat('zh-TW', {maximumFractionDigits:2}).format(value * 100)}%`;

  function previousPeriod(startPeriod) {
    const [year, month] = startPeriod.split('-').map(Number), index = year * 12 + month - 2;
    return `${String(Math.floor(index / 12)).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}`;
  }

  function markersFor(labels, events, skipFirst) {
    return shell.sortEvents(events).flatMap(event => {
      const index = labels.indexOf(event.start_period);
      return index < 0 || (skipFirst && index === 0) ? [] : [{index, period:event.start_period, name:event.name}];
    });
  }

  // Monte Carlo monthly percentiles; with a profile the starting month-end is prepended, where every
  // percentile equals today's net worth.
  function bandData(bands, startPeriod, events = [], profile = null, debts = []) {
    const labels = bands.months.map(month => planner.monthToPeriod(startPeriod, month));
    const series = {};
    for (const [point, values] of Object.entries(bands.net_worth)) series[point] = values.map(Number);
    if (profile) {
      labels.unshift(previousPeriod(startPeriod));
      const start = shell.financialSummary(profile, debts).netWorth;
      for (const values of Object.values(series)) values.unshift(start);
    }
    const last = labels.length - 1;
    return {labels, series, markers:markersFor(labels, events, !!profile),
      summary:{period:labels[last], p5:series.p5[last], p25:series.p25?.[last], p50:series.p50[last],
        p75:series.p75?.[last], p95:series.p95[last]}};
  }

  function bandSummaryText(summary) {
    const money = shell.money;
    const lines = [`到 ${summary.period}，一般情況下淨資產約 ${money(summary.p50)}；9 成的模擬落在 ${money(summary.p5)} 到 ${money(summary.p95)} 之間。`];
    if (summary.p25 != null && summary.p75 != null)
      lines.push(`最常見的 5 成落在 ${money(summary.p25)} 到 ${money(summary.p75)} 之間（圖中顏色較深的區間）。`);
    lines.push('每個月的範圍是分別整理的，不是某一次模擬的實際路徑。');
    return lines;
  }

  // Deterministic cash, investment and net worth, with the starting month-end when a profile is given.
  function splitData(curve, startPeriod, events = [], profile = null, debts = []) {
    const labels = curve.map(row => planner.monthToPeriod(startPeriod, row.month));
    const cash = curve.map(row => Number(row.balance));
    const investment = curve.map(row => Number(row.investment_value ?? 0));
    const netWorth = curve.map(row => Number(row.net_worth));
    if (profile) {
      labels.unshift(previousPeriod(startPeriod));
      cash.unshift(Number(profile.cash_balance));
      investment.unshift(Number(profile.investment_value ?? 0));
      netWorth.unshift(shell.financialSummary(profile, debts).netWorth);
    }
    const summarize = values => {
      const minimum = Math.min(...values), index = values.indexOf(minimum);
      return {initial:values[0], final:values.at(-1), minimum, minimumPeriod:labels[index], initialPeriod:labels[0]};
    };
    return {labels, cash, investment, netWorth, markers:markersFor(labels, events, !!profile),
      hasInvestment:investment.some(value => value !== 0),
      summary:{cash:summarize(cash), investment:summarize(investment), netWorth:summarize(netWorth)}};
  }

  // Rows for "這次模擬用了哪些假設"; every value comes from the API responses or the request.
  function assumptionRows({simulation, mc, request, startPeriod, months, simulations, seed, converted}) {
    const a = simulation.assumptions || {}, method = mc.sampling_method || {}, profile = request.profile || {};
    const history = method.history_start ? `${method.history_start} 至 ${method.history_end}` : '台灣歷史資料';
    const rows = [['模擬期間', `${startPeriod} 起共 ${months} 個月（至 ${planner.monthToPeriod(startPeriod, months)}）`]];
    if (a.annual_inflation_rate != null)
      rows.push(['確定性模擬的通膨率', `每年 ${percent(a.annual_inflation_rate)}（${a.inflation_source === 'user' ? '你設定的固定值' : `${history} 台灣 CPI 年化平均`}）`]);
    rows.push(['Monte Carlo 的通膨', (mc.sampled_parameters || []).includes('inflation_rate')
      ? `從 ${history} 的台灣 CPI 月資料抽樣，每次連續 ${method.block_months || 12} 個月一組，與同月台股報酬成對`
      : `固定為每年 ${percent(Number(profile.inflation_rate))}，不抽樣`]);
    rows.push(['調薪率', a.raise_source === 'user' ? `每年固定 ${percent(a.raise_rate)}` : '跟著通膨，每年調整一次']);
    if (a.annual_return_rate != null) {
      rows.push(['確定性模擬的投資報酬率', `每年 ${percent(a.annual_return_rate)}（${a.return_source === 'user' ? '你設定的固定值' : `${history} 台股報酬指數（含股利再投入）年化平均`}）`]);
      rows.push(['Monte Carlo 的投資報酬', `從 ${history} 的台股報酬指數月資料抽樣，每次連續 ${method.block_months || 12} 個月一組`]);
    } else {
      rows.push(['投資', '沒有設定投資市值或每月投資，報酬不影響結果']);
    }
    rows.push(['每月投資金額', `${shell.money(Number(profile.monthly_investment || 0))}，從現金轉入投資；現金不足時不會自動賣出`]);
    rows.push(['預備金目標', `${Number(profile.target_emergency_months ?? 6)} 個月的必要支出`]);
    rows.push(['Monte Carlo 試驗', `${simulations} 次，亂數種子 ${seed}；同樣的輸入會得到同樣的結果`]);
    if (converted?.note) rows.push(['購車成本', converted.note]);
    return rows.map(([label, value]) => ({label, value}));
  }

  const api = {bandData, bandSummaryText, splitData, assumptionRows, previousPeriod};
  if (node) module.exports = api; else root.ResultsModel = api;
})(globalThis);
