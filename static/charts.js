(function(root) {
  'use strict';
  const instances=new Map();
  function draw(canvas,summaryTarget,curve,startPeriod,events,profile,{mini=false,debts=[]}={}) {
    const m=root.ShellModel, data=m.chartData(curve,startPeriod,events,profile,debts), target=summaryTarget;
    target.replaceChildren();
    for(const [key,label] of mini?[['netWorth','淨資產']]:[['cash','現金'],['netWorth','淨資產']]) {
      const s=data.summary[key];
      if(s)target.append(root.FutureWalletShell.element('p',`${label}：期初值 ${m.money(s.initial)}（${s.initialPeriod}月底），期末值 ${m.money(s.final)}；最低點 ${m.money(s.minimum)}，發生於 ${s.minimumPeriod}。`));
    }
    instances.get(canvas)?.destroy();
    if(!root.Chart){target.prepend(root.FutureWalletShell.element('p','圖表元件載入失敗，可先查看下方文字摘要；重新整理可重試。'));return;}
    const colors=root.getComputedStyle(root.document.documentElement),markers=new Set(data.markers.map(marker=>marker.index));
    const dataset=(key,label,color)=>({label,data:data[key],borderColor:colors.getPropertyValue(color).trim(),
      backgroundColor:colors.getPropertyValue(color).trim(),borderWidth:2,pointRadius:data.labels.map((_,i)=>markers.has(i)?3:0),
      pointHoverRadius:5,tension:0,borderDash:key==='cash'?[5,3]:[]});
    const chart=new root.Chart(canvas,{type:'line',data:{labels:data.labels,datasets:mini?
      [dataset('netWorth','淨資產','--accent')]:[dataset('cash','現金','--navy'),dataset('netWorth','淨資產','--accent')]},
      options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{display:!mini},tooltip:{callbacks:{label:item=>`${item.dataset.label}：${m.money(item.parsed.y)}`,
          afterBody:items=>data.markers.filter(marker=>marker.index===items[0]?.dataIndex).map(marker=>`事件：${marker.name}`)}}},
        scales:{x:{grid:{display:false},ticks:{maxTicksLimit:mini?4:6,maxRotation:0}},
          y:{ticks:{maxTicksLimit:4,callback:value=>new Intl.NumberFormat('zh-TW',{notation:'compact'}).format(value)}}}}});
    instances.set(canvas,chart);
    canvas.setAttribute('aria-describedby',target.id);
  }
  function destroyAll(){for(const chart of instances.values())chart.destroy();instances.clear();}
  root.addEventListener('pagehide',destroyAll);
  root.WalletCharts={draw,destroyAll};
})(globalThis);
