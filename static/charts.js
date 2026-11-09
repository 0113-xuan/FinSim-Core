(function(root) {
  'use strict';
  const instances=new Map();
  const compact=value=>new Intl.NumberFormat('zh-TW',{notation:'compact',maximumFractionDigits:0}).format(value);
  function prepare(canvas,target) {
    instances.get(canvas)?.destroy();instances.delete(canvas);
    if(root.Chart)return true;
    target.prepend(root.FutureWalletShell.element('p','圖表元件載入失敗，可先查看下方文字摘要；重新整理可重試。'));
    return false;
  }
  function finish(canvas,target,chart){instances.set(canvas,chart);canvas.setAttribute('aria-describedby',target.id);}
  // Chart.js defaults to 12px Helvetica; match the page's type so axis and legend text stay readable.
  const chartFont=()=>({family:root.getComputedStyle(root.document.body).fontFamily,size:14});
  function baseOptions(m,data,{mini=false,legend=!mini}={}) {
    const font=chartFont();
    return {responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:legend,labels:{font,boxWidth:22,boxHeight:2,filter:item=>!item.text.startsWith('_')}},
        tooltip:{titleFont:font,bodyFont:font,filter:item=>!item.dataset.label.startsWith('_'),callbacks:{label:item=>`${item.dataset.label}：${m.money(item.parsed.y)}`,
          afterBody:items=>data.markers.filter(marker=>marker.index===items[0]?.dataIndex).map(marker=>`事件：${marker.name}`)}}},
      scales:{x:{grid:{display:false},ticks:{font,maxTicksLimit:mini?4:6,maxRotation:0}},
        y:{ticks:{font,maxTicksLimit:4,callback:compact}}}};
  }
  const pointRadius=(data,markers)=>data.labels.map((_,i)=>markers.has(i)?3:0);
  function summaryLine(m,label,s) {
    return root.FutureWalletShell.element('p',`${label}：期初值 ${m.money(s.initial)}（${s.initialPeriod}月底），期末值 ${m.money(s.final)}；最低點 ${m.money(s.minimum)}，發生於 ${s.minimumPeriod}。`);
  }

  // Deterministic run: cash, investment and net worth (mini: net worth only, for dashboard cards).
  function draw(canvas,summaryTarget,curve,startPeriod,events,profile,{mini=false,debts=[]}={}) {
    const m=root.ShellModel,r=root.ResultsModel,data=r.splitData(curve,startPeriod,events,profile,debts),target=summaryTarget;
    const keys=mini?[['netWorth','淨資產']]:[['cash','現金'],...(data.hasInvestment?[['investment','投資市值']]:[]),['netWorth','淨資產']];
    target.replaceChildren(...keys.map(([key,label])=>summaryLine(m,label,data.summary[key])));
    if(!prepare(canvas,target))return;
    const colors=root.getComputedStyle(root.document.body),markers=new Set(data.markers.map(marker=>marker.index));
    const style={cash:['--navy',[5,3]],investment:['--investment',[2,3]],netWorth:['--accent',[]]};
    const datasets=keys.map(([key,label])=>{
      const color=colors.getPropertyValue(style[key][0]).trim();
      return {label,data:data[key],borderColor:color,backgroundColor:color,borderWidth:2,borderDash:style[key][1],
        pointRadius:key==='netWorth'?pointRadius(data,markers):0,pointHoverRadius:5,tension:0};
    });
    finish(canvas,target,new root.Chart(canvas,{type:'line',data:{labels:data.labels,datasets},options:baseOptions(m,data,{mini})}));
  }

  // Monte Carlo monthly percentiles: P5–P95 outer band, P25–P75 inner band, P50 line.
  function drawBands(canvas,summaryTarget,bands,startPeriod,events,profile,{debts=[]}={}) {
    const m=root.ShellModel,r=root.ResultsModel,data=r.bandData(bands,startPeriod,events,profile,debts),target=summaryTarget;
    target.replaceChildren(...r.bandSummaryText(data.summary).map(text=>root.FutureWalletShell.element('p',text)));
    if(!prepare(canvas,target))return;
    const colors=root.getComputedStyle(root.document.body),accent=colors.getPropertyValue('--accent').trim();
    const markers=new Set(data.markers.map(marker=>marker.index));
    const rgb=/^#([0-9a-f]{6})$/i.test(accent)?[1,3,5].map(i=>parseInt(accent.slice(i,i+2),16)).join(','):'4,120,87';
    const tint=alpha=>`rgba(${rgb},${alpha/100})`;
    const edge=(label,values,fill,alpha)=>({label,data:values,borderColor:tint(35),borderWidth:1,pointRadius:0,
      pointHoverRadius:3,tension:0,fill,backgroundColor:tint(alpha)});
    const s=data.series;
    const datasets=[
      // Outer band fills P95 down to P5; the inner P75–P25 band on top makes the middle half darker.
      edge('順利情況',s.p95,'+4',14),
      edge('最常見範圍上緣',s.p75,'+2',22),
      {label:'一般情況',data:s.p50,borderColor:accent,backgroundColor:accent,borderWidth:2.5,tension:0,
        pointRadius:pointRadius(data,markers),pointHoverRadius:5,fill:false},
      edge('最常見範圍下緣',s.p25,false,0),
      edge('較差情況',s.p5,false,0)];
    const options=baseOptions(m,data,{legend:false});
    finish(canvas,target,new root.Chart(canvas,{type:'line',data:{labels:data.labels,datasets},options}));
  }

  // Cash-flow comparison uses the real monthly rows returned by /simulate.
  function drawCashflow(canvas,summaryTarget,curve,startPeriod) {
    const m=root.ShellModel,target=summaryTarget;
    if(!Array.isArray(curve)||!curve.length)return;
    const labels=curve.map(row=>root.PlannerModel.monthToPeriod(startPeriod,row.month));
    const income=curve.map(row=>Number(row.income||0)),expense=curve.map(row=>Number(row.expense||0)),debt=curve.map(row=>Number(row.debt_payment||0));
    const totalIncome=income.reduce((a,b)=>a+b,0),totalExpense=expense.reduce((a,b)=>a+b,0),totalDebt=debt.reduce((a,b)=>a+b,0);
    target.replaceChildren(root.FutureWalletShell.element('p',`模擬期間累計收入 ${m.money(totalIncome)}；生活支出 ${m.money(totalExpense)}；貸款還款 ${m.money(totalDebt)}。圖表分開呈現生活支出與貸款還款，不含投資轉入及一次性事件對現金的額外影響。`));
    if(!prepare(canvas,target))return;
    const colors=root.getComputedStyle(root.document.body);
    const options=baseOptions(m,{markers:[]},{legend:true});
    options.plugins.tooltip.callbacks.label=item=>`${item.dataset.label}：${m.money(item.parsed.y)}`;
    options.scales.y.beginAtZero=true;
    finish(canvas,target,new root.Chart(canvas,{type:'bar',data:{labels,datasets:[
      {label:'收入',data:income,backgroundColor:colors.getPropertyValue('--accent').trim(),borderRadius:5},
      {label:'生活支出',data:expense,backgroundColor:colors.getPropertyValue('--navy').trim(),borderRadius:5},
      {label:'貸款還款',data:debt,backgroundColor:colors.getPropertyValue('--investment').trim(),borderRadius:5}
    ]},options}));
  }

  // End-of-period composition is derived from the last deterministic simulation row.
  function drawComposition(canvas,summaryTarget,curve) {
    const m=root.ShellModel,target=summaryTarget,last=curve?.at(-1);
    if(!last)return;
    const values=[['現金',Number(last.balance||0)],['投資',Number(last.investment_value||0)],['車輛與其他資產',Number(last.asset_value||0)]];
    const rows=values.filter(([,value])=>value>0);
    const total=rows.reduce((sum,row)=>sum+row[1],0);
    target.replaceChildren(root.FutureWalletShell.element('p',`期末資產合計 ${m.money(total)}。${rows.map(([label,value])=>`${label} ${m.money(value)}`).join('；')}。`));
    if(!prepare(canvas,target))return;
    const colors=root.getComputedStyle(root.document.body);
    const palette=['--accent','--navy','--investment'].map(key=>colors.getPropertyValue(key).trim()).filter(Boolean);
    const options={responsive:true,maintainAspectRatio:false,animation:false,cutout:'66%',plugins:{legend:{position:'bottom',labels:{font:chartFont(),usePointStyle:true,pointStyle:'circle'}},tooltip:{titleFont:chartFont(),bodyFont:chartFont(),callbacks:{label:item=>`${item.label}：${m.money(item.parsed)}（${total?Math.round(item.parsed/total*100):0}%）`}}}};
    finish(canvas,target,new root.Chart(canvas,{type:'doughnut',data:{labels:rows.map(row=>row[0]),datasets:[{data:rows.map(row=>row[1]),backgroundColor:rows.map((_,i)=>palette[i%palette.length]),borderWidth:0,hoverOffset:5}]},options}));
  }

  // Current profile allocation for the dashboard; uses saved account values only.
  function drawCurrentAllocation(canvas,summaryTarget,profile) {
    const m=root.ShellModel,target=summaryTarget;
    const rows=[['現金',Number(profile.cash_balance||0)],['投資',Number(profile.investment_value||0)]].filter(([,v])=>v>0);
    const total=rows.reduce((sum,row)=>sum+row[1],0);
    target.replaceChildren(root.FutureWalletShell.element('p',rows.length?`目前可計算資產 ${m.money(total)}；${rows.map(([label,value])=>`${label} ${m.money(value)}`).join('；')}。`:'目前尚無可呈現的現金或投資資料。'));
    if(!prepare(canvas,target))return;
    const colors=root.getComputedStyle(root.document.body),palette=['--accent','--navy'].map(key=>colors.getPropertyValue(key).trim());
    const options={responsive:true,maintainAspectRatio:false,animation:false,cutout:'68%',plugins:{legend:{position:'bottom',labels:{font:chartFont(),usePointStyle:true,pointStyle:'circle'}},tooltip:{titleFont:chartFont(),bodyFont:chartFont(),callbacks:{label:item=>`${item.label}：${m.money(item.parsed)}（${total?Math.round(item.parsed/total*100):0}%）`}}}};
    finish(canvas,target,new root.Chart(canvas,{type:'doughnut',data:{labels:rows.map(row=>row[0]),datasets:[{data:rows.map(row=>row[1]),backgroundColor:rows.map((_,i)=>palette[i]),borderWidth:0,hoverOffset:5}]},options}));
  }

  // Several scenarios on one chart: each line differs in colour AND dash so it can be told apart without colour.
  // `chart` is {labels, series:[{name,kind,values}]} from CompareModel.chartSeries.
  function drawCompare(canvas,summaryTarget,chart,summaryLines,{zeroLine=false}={}) {
    const m=root.ShellModel,target=summaryTarget;
    target.replaceChildren(...summaryLines.map(text=>root.FutureWalletShell.element('p',text)));
    if(!prepare(canvas,target))return;
    const colors=root.getComputedStyle(root.document.body);
    const palette=[['--accent',[]],['--navy',[8,4]],['--investment',[2,3]],['--series-four',[10,3,2,3]]];
    let next=0;
    const datasets=chart.series.map(line=>{
      // The do-nothing baseline is always the grey reference line.
      const [token,dash]=line.kind==='baseline'?['--muted',[4,4]]:palette[next++%palette.length];
      const color=colors.getPropertyValue(token).trim()||'#4b5b57';
      return {label:line.name,data:line.values,borderColor:color,backgroundColor:color,borderWidth:line.kind==='baseline'?1.5:2.5,borderDash:dash,pointRadius:0,pointHoverRadius:5,tension:0};
    });
    if(zeroLine)datasets.push({label:'_零',data:chart.labels.map(()=>0),borderColor:colors.getPropertyValue('--danger').trim()||'#dc2626',borderWidth:1,borderDash:[1,3],pointRadius:0,pointHoverRadius:0,tension:0});
    // baseOptions already sets the page font and hides datasets whose label starts with "_".
    finish(canvas,target,new root.Chart(canvas,{type:'line',data:{labels:chart.labels,datasets},options:baseOptions(m,{markers:[]},{legend:true})}));
  }

  function destroyAll(){for(const chart of instances.values())chart.destroy();instances.clear();}
  root.addEventListener('pagehide',destroyAll);
  root.WalletCharts={draw,drawBands,drawCashflow,drawComposition,drawCurrentAllocation,drawCompare,destroyAll};
})(globalThis);
