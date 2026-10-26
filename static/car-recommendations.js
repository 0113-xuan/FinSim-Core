(function(root) {
  'use strict';
  const labels={ice:'汽油',hev:'油電',bev:'純電',sedan:'轎車',hatchback:'掀背車',suv:'SUV',mpv:'多人座',match:'符合',mismatch:'不符合',insufficient_data:'資料不足',annual_insurance:'保險／年',annual_tax:'稅費／年',annual_maintenance_budget:'保養／年',monthly_fuel_or_energy:'每月油電費',monthly_parking:'每月停車',inflation_rate:'年度通膨',raise_rate:'年度調薪',fuel_price:'油價／公升',minimum_emergency_fund_months:'最低預備金（月）',minimum_cash_balance:'最低現金',minimum_monthly_surplus:'最低每月結餘'};
  const money=value=>value===null||value===undefined?'資料不足':`NT$${Math.round(value).toLocaleString('zh-TW')}`;
  function groups(data) {
    if(!data||!Array.isArray(data.ranked)||!Array.isArray(data.incomplete)||!Array.isArray(data.excluded)) throw new Error('推薦資料格式不正確');
    return {ranked:data.ranked,incomplete:data.incomplete,excluded:data.excluded};
  }
  async function request(needs,{transport=fetch,signal}={}) {
    if(needs.status!=='confirmed') throw new Error('請先確認需求');
    const response=await transport('/decisions/vehicle/recommendations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(needs),signal});
    if(!response.ok) throw new Error(response.status===422?'需求資料未通過驗證，請返回檢查。':'推薦暫時無法完成，請稍後重試。');
    const data=await response.json();groups(data);return data;
  }
  function render(container,data) {
    const document=container.ownerDocument;
    const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    const line=(list,label,value)=>{list.append(el('dt',label),el('dd',value));};
    const detail=(parent,title)=>{const d=el('details');d.append(el('summary',title));parent.append(d);return d;};
    const {ranked,incomplete,excluded}=groups(data);container.replaceChildren();
    container.append(el('h3',ranked.length?`${ranked.length} 款可比較，每月負擔一眼看懂`:'目前沒有可完整排名的車款'));
    container.append(el('p','依五年車輛現金支出排序，不代表適合程度或一定買得起。','hint'));
    if(!ranked.length) container.append(el('p','可調整預算、座位或排除條件；資料不足請先補齊。','result-notice'));
    for(const message of data.missing_inputs) container.append(el('p',message,'result-notice'));
    const grid=el('div',undefined,'recommendation-grid');container.append(grid);
    for(const item of ranked) {
      const car=item.vehicle,card=el('article',undefined,'recommendation-card');
      card.append(el('span',`#${item.rank} · ${labels[car.body_type]} · ${labels[car.powertrain]} · ${car.seats} 人`,'result-meta'),el('h4',`${car.brand} ${car.model}`),el('p',car.trim));
      card.append(el('p','每月車輛支出（含車貸）','result-caption'),el('strong',money(item.costs.monthly_vehicle_outflow),'result-money'),el('p',`購車生效月；不含頭期款／現金車價`,'hint'));
      const list=el('dl');line(list,'參考售價',money(car.price_twd));line(list,'五年現金支出',money(item.five_year_cash_outflow));line(list,'首次付款',money(item.costs.one_time_payment));
      if(item.costs.remaining_loan_months) line(list,`五年後仍有 ${item.costs.remaining_loan_months} 期`,`${money(item.remaining_loan_payments)}（含利息）`);
      card.append(list);
      const f=item.affordability;
      card.append(el('p',f?(f.passed?'通過系統財務限制':'未通過系統財務限制'):'未提供財務資料：尚未評估負擔能力',`affordability ${f?(f.passed?'passed':'failed'):''}`));
      if(f) {
        const finance=el('dl');line(finance,'購車後每月結餘',money(f.metrics.monthly_surplus));line(finance,'五年末現金',money(f.metrics.ending_cash));line(finance,'不買車五年末現金',money(f.baseline.ending_cash));line(finance,'最低現金',money(f.metrics.minimum_cash_balance));line(finance,'最低預備金',f.metrics.minimum_emergency_fund_months===null?'不適用':`${f.metrics.minimum_emergency_fund_months.toFixed(1)} 個月`);card.append(finance);
        const checks=detail(card,'財務限制明細');for(const c of f.constraints) checks.append(el('p',`${labels[c.key]}：${c.passed?'通過':'未通過'} · 實際 ${c.actual===null?'不適用':c.actual.toLocaleString('zh-TW',{maximumFractionDigits:2})} / 門檻 ${c.required}`));
      }
      const cost=detail(card,'支出結構');const breakdown=el('dl');line(breakdown,'首次付款',money(item.costs.one_time_payment));line(breakdown,'五年車貸付款',money(item.costs.loan_payments_total));for(const c of item.costs.items) line(breakdown,`${labels[c.key]||c.key}（五年）`,money(c.period_total));cost.append(breakdown,el('p',item.energy_formula,'hint'),el('p','月度金額取分後累加，與直接乘年費可能有分位捨入差；引擎回傳總額為準。','hint'));
      const preferences=detail(card,'偏好符合情形');if(!item.preferences.length)preferences.append(el('p','未指定偏好'));for(const p of item.preferences)preferences.append(el('p',`${p.label}：${labels[p.status]}${p.note?'；'+p.note:''}`));
      const source=detail(card,'車款來源與限制');source.append(el('p',`查詢日 ${car.checked_on} · 官方參考數據`),el('p',car.model_year_note));
      for(const [key,url] of Object.entries(car.sources)) {if(!url)continue;const a=el('a',{price:'官方價格',specifications:'官方規格',efficiency:'官方油耗／電耗'}[key]);a.href=url;a.target='_blank';a.rel='noopener noreferrer';source.append(a,el('br'));}
      source.append(el('p',`${car.efficiency===null?'電耗未知':car.efficiency+' '+car.efficiency_unit}`),el('p',car.limitations.join('；')),el('p',item.ranking_reason));grid.append(card);
    }
    for(const [title,items] of [['資料不足，暫不排名',incomplete],['不符合硬性條件',excluded]]) {
      if(!items.length)continue;const d=detail(container,`${title}（${items.length}）`);
      for(const item of items) {
        const car=item.vehicle;
        d.append(el('p',`${car.brand} ${car.model} ${car.trim} · ${money(car.price_twd)} · ${car.seats??'未知'} 人：${item.reasons.join('；')}`));
        if(item.preferences)for(const p of item.preferences)d.append(el('p',`${p.label}：${labels[p.status]}`));
        const a=el('a',`官方資料 · 查詢日 ${car.checked_on}`);a.href=car.source_url;a.target='_blank';a.rel='noopener noreferrer';d.append(a,el('p',car.model_year_note));
      }
    }
    const assumptions=detail(container,'比較使用的規劃假設');
    for(const a of data.assumptions)assumptions.append(el('p',`${labels[a.key]||a.key}：${a.value} ${a.unit} · ${a.source==='user_provided'?'使用者輸入':'系統假設'} · ${a.description}`));
    const scope=detail(container,'比較口徑與模型限制');scope.append(el('p',`${data.purchase_period} 購車起算 60 個月；年度預算按月提列，通膨沿用財務引擎。`));
    for(const text of data.limitations)scope.append(el('p',text));
  }
  const api={money,groups,request,render};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.CarRecommendations=api;
})(typeof globalThis!=='undefined'?globalThis:this);
