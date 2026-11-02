(function(root) {
  'use strict';
  const instances=new Map();
  const compact=value=>new Intl.NumberFormat('zh-TW',{notation:'compact'}).format(value);
  function prepare(canvas,target) {
    instances.get(canvas)?.destroy();instances.delete(canvas);
    if(root.Chart)return true;
    target.prepend(root.FutureWalletShell.element('p','圖表元件載入失敗，可先查看下方文字摘要；重新整理可重試。'));
    return false;
  }
  function finish(canvas,target,chart){instances.set(canvas,chart);canvas.setAttribute('aria-describedby',target.id);}
  function baseOptions(m,data,{mini=false,legend=!mini}={}) {
    return {responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:legend,labels:{boxWidth:22,boxHeight:2,filter:item=>!item.text.startsWith('_')}},
        tooltip:{filter:item=>!item.dataset.label.startsWith('_'),callbacks:{label:item=>`${item.dataset.label}：${m.money(item.parsed.y)}`,
          afterBody:items=>data.markers.filter(marker=>marker.index===items[0]?.dataIndex).map(marker=>`事件：${marker.name}`)}}},
      scales:{x:{grid:{display:false},ticks:{maxTicksLimit:mini?4:6,maxRotation:0}},
        y:{ticks:{maxTicksLimit:4,callback:compact}}}};
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
    const colors=root.getComputedStyle(root.document.documentElement),markers=new Set(data.markers.map(marker=>marker.index));
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
    const colors=root.getComputedStyle(root.document.documentElement),accent=colors.getPropertyValue('--accent').trim();
    const markers=new Set(data.markers.map(marker=>marker.index));
    const rgb=/^#([0-9a-f]{6})$/i.test(accent)?[1,3,5].map(i=>parseInt(accent.slice(i,i+2),16)).join(','):'4,120,87';
    const tint=alpha=>`rgba(${rgb},${alpha/100})`;
    const edge=(label,values,fill,alpha)=>({label,data:values,borderColor:tint(35),borderWidth:1,pointRadius:0,
      pointHoverRadius:3,tension:0,fill,backgroundColor:tint(alpha)});
    const s=data.series;
    const datasets=[
      // Outer band fills P95 down to P5; the inner P75–P25 band on top makes the middle half darker.
      edge('第 95 百分位數',s.p95,'+4',14),
      edge('第 75 百分位數',s.p75,'+2',22),
      {label:'中位數',data:s.p50,borderColor:accent,backgroundColor:accent,borderWidth:2.5,tension:0,
        pointRadius:pointRadius(data,markers),pointHoverRadius:5,fill:false},
      edge('第 25 百分位數',s.p25,false,0),
      edge('第 5 百分位數',s.p5,false,0)];
    const options=baseOptions(m,data,{legend:false});
    finish(canvas,target,new root.Chart(canvas,{type:'line',data:{labels:data.labels,datasets},options}));
  }

  function destroyAll(){for(const chart of instances.values())chart.destroy();instances.clear();}
  root.addEventListener('pagehide',destroyAll);
  root.WalletCharts={draw,drawBands,destroyAll};
})(globalThis);
