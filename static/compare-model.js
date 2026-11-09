(function(root) {
  'use strict';
  // Pure logic for the scenario comparison page: which saved events form each scenario, how the
  // results are summarised and which scenario leads on each measure. No DOM access, so node tests can cover it.
  const node = typeof module !== 'undefined' && module.exports;
  const planner = node ? require('./planner-model.js') : root.PlannerModel;
  const shell = node ? require('./shell-model.js') : root.ShellModel;
  const results = node ? require('./results-model.js') : root.ResultsModel;

  const MAX_SCENARIOS = 4;
  const BASELINE_NAME = '不做任何事';
  // Every scenario is simulated with the same seed, so all of them see the same 300 historical draws.
  const SEED = 42;
  const SIMULATIONS = 300;
  // Amounts are shown to the nearest 100, so a smaller gap is not a real difference.
  const TIE_AMOUNT = 50;

  // One selectable row per saved event, in plan order; the checkbox value is the event id.
  // Life events are all named after their template ("購車"), so the plan name is what tells them apart.
  function eventOptions(plans, eventsByPlan) {
    return plans.flatMap(plan => {
      const events = shell.sortEvents(eventsByPlan[plan.id] || []);
      return events.map(event => ({
        id: event.id, planId: plan.id, planName: plan.name, event,
        title: events.length > 1 ? `${plan.name}：${event.name}` : plan.name,
        detail: `${shell.eventNames[event.type] || '事件'}｜${event.start_period}｜${shell.eventSummary(event)}`,
        label: `${shell.eventNames[event.type] || '事件'} ${event.start_period}`,
      }));
    });
  }

  // The starting point: one scenario per plan that has events, so "compare my plans" works without any setup.
  function defaultScenarios(options) {
    const groups = new Map();
    for (const option of options) {
      if (!groups.has(option.planId)) groups.set(option.planId, []);
      groups.get(option.planId).push(option.id);
    }
    return [...groups.values()].slice(0, MAX_SCENARIOS).map(ids => ({name: '', eventIds: ids}));
  }

  // A blank name falls back to the plan names joined with "＋" (換國產車＋換工作).
  function scenarioName(scenario, index, optionsById) {
    const typed = String(scenario.name || '').trim();
    if (typed) return typed;
    const names = [...new Set(scenario.eventIds.map(id => optionsById.get(id)?.title).filter(Boolean))];
    return names.length ? names.join('＋') : `情境 ${index + 1}`;
  }

  // Returns the runnable entries and a list of plain-language problems; an empty list means the run may start.
  function resolveScenarios(scenarios, options, {baseline = true} = {}) {
    const byId = new Map(options.map(option => [option.id, option]));
    const problems = [], entries = [], seen = new Map(), signatures = new Map();
    scenarios.forEach((scenario, index) => {
      const ids = scenario.eventIds.filter(id => byId.has(id));
      const name = scenarioName({...scenario, eventIds: ids}, index, byId);
      if (!ids.length) { problems.push(`「${name}」還沒有勾選事件`); return; }
      if (name.length > 80) problems.push(`「${name.slice(0, 12)}…」的名稱超過 80 字`);
      if (seen.has(name)) problems.push(`情境名稱重複：「${name}」，請改成不同名稱`);
      seen.set(name, index);
      const signature = [...ids].sort().join('|');
      if (signatures.has(signature)) problems.push(`「${signatures.get(signature)}」與「${name}」勾選的事件完全相同`);
      else signatures.set(signature, name);
      entries.push({name, kind: 'scenario', eventIds: ids, events: ids.map(id => byId.get(id).event), eventLabels: ids.map(id => byId.get(id).label)});
    });
    if (baseline && seen.has(BASELINE_NAME)) problems.push(`「${BASELINE_NAME}」已被系統用作基準名稱，請改用其他名稱`);
    if (!scenarios.length) problems.push('請至少建立一個情境');
    else if (!baseline && scenarios.length < 2) problems.push('要比較至少需要兩個情境；也可以勾選「加入不做任何事當基準」');
    if (baseline) entries.unshift({name: BASELINE_NAME, kind: 'baseline', eventIds: [], events: [], eventLabels: []});
    return {entries, problems};
  }

  // One row of numbers per run, all read from the API responses.
  function summarize({name, kind, simulation, mc, converted}, startPeriod, months) {
    const fixed = simulation.summary, net = mc.net_worth_percentiles;
    return {
      name, kind,
      netWorth: {p5: net.p5, p50: net.p50, p95: net.p95},
      realNetWorthP50: mc.real_net_worth_percentiles?.p50 ?? null,
      cashP50: mc.percentiles.p50,
      fixedFinalCash: fixed.final_balance,
      fixedFinalNetWorth: fixed.final_net_worth,
      minimumCash: fixed.minimum_cash_balance,
      minimumCashPeriod: planner.monthToPeriod(startPeriod, fixed.minimum_cash_month),
      firstNegativePeriod: fixed.first_negative_cash_month == null ? null : planner.monthToPeriod(startPeriod, fixed.first_negative_cash_month),
      shortfall: Number(mc.probability_cash_shortfall),
      vehicleCount: converted?.vehicles?.length || 0,
    };
  }

  const near = (a, b) => Math.abs(a - b) < TIE_AMOUNT;
  // Indices that lead on each measure; a tie within the rounding step lists every tied scenario.
  function leaders(rows) {
    const best = (value, better) => {
      const top = rows.map(value).reduce((a, b) => better(a, b) ? a : b);
      return new Set(rows.flatMap((row, index) => near(value(row), top) ? [index] : []));
    };
    const lowestShortfall = Math.min(...rows.map(row => row.shortfall));
    return {
      netWorth: best(row => row.netWorth.p50, (a, b) => a >= b),
      minimumCash: best(row => row.minimumCash, (a, b) => a >= b),
      shortfall: new Set(rows.flatMap((row, index) => Math.abs(row.shortfall - lowestShortfall) < 0.005 ? [index] : [])),
    };
  }

  const gapText = value => Math.abs(value) < TIE_AMOUNT ? '沒有差別' : value < 0 ? `少了 ${shell.money(-value)}` : `多了 ${shell.money(value)}`;
  const quoted = names => names.map(name => `「${name}」`).join('、');

  // The answer first, in neutral words: who leads on net worth, who is safest, and whether those differ.
  function conclusion(rows, startPeriod, months) {
    const endPeriod = planner.monthToPeriod(startPeriod, months), lead = leaders(rows);
    const names = set => [...set].map(index => rows[index].name);
    const topWorth = rows[[...lead.netWorth][0]].netWorth.p50;
    const lines = [];
    const headline = lead.netWorth.size === rows.length
      ? `${endPeriod} 的淨資產，一般情況下各情境差不多（相差不到 ${shell.money(TIE_AMOUNT * 2)}）。`
      : `${endPeriod} 的淨資產，一般情況下最高的是${quoted(names(lead.netWorth))}，約 ${shell.money(topWorth)}。`;
    const rest = rows.map((row, index) => ({row, index})).filter(({index}) => !lead.netWorth.has(index));
    if (rest.length) {
      const second = rest.reduce((a, b) => b.row.netWorth.p50 > a.row.netWorth.p50 ? b : a);
      lines.push(`第二高的是「${second.row.name}」，約少 ${shell.money(topWorth - second.row.netWorth.p50)}；最低的是「${rest.reduce((a, b) => b.row.netWorth.p50 < a.row.netWorth.p50 ? b : a).row.name}」。`);
    }
    const highestRisk = Math.max(...rows.map(row => row.shortfall));
    if (highestRisk === 0) lines.push('300 次隨機模擬中，所有情境的現金都沒有低於 0。');
    else {
      const lowest = rows[[...lead.shortfall][0]].shortfall;
      const risky = rows.filter(row => row.shortfall === highestRisk).map(row => row.name);
      const safest = lead.shortfall.size <= 2 ? `是${quoted(names(lead.shortfall))}` : `有 ${lead.shortfall.size} 個情境`;
      if (lead.shortfall.size === rows.length) lines.push(`所有情境的現金不足機率都約 ${shell.wholePercent(lowest)}。`);
      else lines.push(`現金不足機率最低的${safest}（${shell.wholePercent(lowest)}），最高的是${quoted(risky)}（${shell.wholePercent(highestRisk)}）。`);
      if (![...lead.netWorth].some(index => lead.shortfall.has(index)) && lead.shortfall.size < rows.length)
        lines.push('淨資產最高的情境，現金不足機率不是最低；要在兩者之間自己取捨。');
    }
    for (const row of rows.filter(item => item.firstNegativePeriod))
      lines.push(`固定值模擬中，「${row.name}」會在 ${row.firstNegativePeriod} 第一次現金低於 0。`);
    const tone = rows.some(row => row.firstNegativePeriod) ? 'alert' : highestRisk > 0 ? 'caution' : 'calm';
    return {tone, headline, lines, leaders: lead,
      caveat: `各情境用相同的起始月份、期間和同一組 ${SIMULATIONS} 次歷史資料抽樣，差異只來自事件。這不是預測，也不保證會發生。`};
  }

  // Net worth change against a reference row (the do-nothing baseline when it exists).
  const netWorthGap = (row, reference) => gapText(row.netWorth.p50 - reference.netWorth.p50);

  // Month-end series per scenario for the comparison charts, starting from today's position.
  // `measure` picks the Monte Carlo band: 'netWorth' (median) or 'cash' (the weaker 1-in-20 case).
  function chartSeries(runs, measure, startPeriod, profile, debts = []) {
    const first = runs[0].mc.monthly_bands;
    const labels = first.months.map(month => planner.monthToPeriod(startPeriod, month));
    const start = measure === 'netWorth' ? shell.financialSummary(profile, debts).netWorth : Number(profile.cash_balance);
    labels.unshift(results.previousPeriod(startPeriod));
    const pick = bands => measure === 'netWorth' ? bands.net_worth.p50 : bands.cash.p5;
    return {labels, series: runs.map(run => ({name: run.name, kind: run.kind, values: [start, ...pick(run.mc.monthly_bands).map(Number)]}))};
  }

  // Which line leads at the end and where each one bottoms out, for the text version of a chart.
  function chartSummary(chart, measureLabel) {
    const money = shell.money, last = chart.labels.length - 1;
    return chart.series.map(line => {
      const minimum = Math.min(...line.values), at = chart.labels[line.values.indexOf(minimum)];
      return `${line.name}：${measureLabel}從 ${money(line.values[0])} 變成 ${chart.labels[last]} 的 ${money(line.values[last])}；最低點 ${money(minimum)}，在 ${at}。`;
    });
  }

  // One row per car bought in any scenario, so different cars sit side by side.
  function vehicleRows(runs) {
    return runs.flatMap(run => (run.converted?.vehicles || []).map(car => ({scenario: run.name, ...car})));
  }

  const api = {MAX_SCENARIOS, BASELINE_NAME, SEED, SIMULATIONS, eventOptions, defaultScenarios, scenarioName, resolveScenarios,
    summarize, leaders, conclusion, netWorthGap, chartSeries, chartSummary, vehicleRows};
  if (node) module.exports = api; else root.CompareModel = api;
})(globalThis);
