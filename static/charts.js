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

  // A dashed vertical line and a short label at each major event, so the sudden step is read at the month it happens.
  // `marks` is [{index, text, color}]; labels stack downwards instead of overlapping.
  function eventMarks(marks,font) {
    return {id:'eventMarks',afterDatasetsDraw(chart) {
      const {ctx,chartArea:area,scales:{x}}=chart;let row=0;
      ctx.save();ctx.font=`600 ${font.size}px ${font.family}`;ctx.textBaseline='top';
      for(const mark of marks){
        const px=x.getPixelForValue(mark.index);if(px<area.left||px>area.right)continue;
        ctx.strokeStyle=mark.color;ctx.lineWidth=1.5;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(px,area.top);ctx.lineTo(px,area.bottom);ctx.stroke();ctx.setLineDash([]);
        const right=px+ctx.measureText(mark.text).width+10>area.right;
        ctx.fillStyle=mark.color;ctx.textAlign=right?'right':'left';ctx.fillText(mark.text,right?px-6:px+6,area.top+4+row++*(font.size+4));
      }
      ctx.restore();
    }};
  }
  // The segment that ends on an event month is drawn thick: that month is where the step happens.
  const stepSegment=(marks,width)=>({borderWidth:context=>marks.some(mark=>mark.index===context.p1DataIndex)?width:undefined});

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
      const color=line.color||colors.getPropertyValue(token).trim()||'#4b5b57';
      // A line that brings its own colour is drawn bold; `dash` lets a reference line stay dashed.
      return {label:line.name,data:line.values,borderColor:color,backgroundColor:color,borderWidth:line.color||line.kind!=='baseline'?2.5:1.5,borderDash:line.color?(line.dash||[]):dash,pointRadius:0,pointHoverRadius:5,tension:0,
        segment:stepSegment(line.marks||[],6),marks:(line.marks||[]).map(mark=>({...mark,color}))};
    });
    const marks=datasets.flatMap(dataset=>dataset.marks);
    if(zeroLine)datasets.push({label:'_零',data:chart.labels.map(()=>0),borderColor:colors.getPropertyValue('--danger').trim()||'#dc2626',borderWidth:1,borderDash:[1,3],pointRadius:0,pointHoverRadius:0,tension:0});
    // baseOptions already sets the page font and hides datasets whose label starts with "_".
    finish(canvas,target,new root.Chart(canvas,{type:'line',data:{labels:chart.labels,datasets},options:baseOptions(m,{markers:[]},{legend:true}),plugins:[eventMarks(marks,chartFont())]}));
  }

  // One cash chart with every path: the plan with and without its events, the random range, and the zero line.
  // `window` is how many months to show; a short window keeps an event from being flattened by decades of growth.
  function drawTrajectories(canvas,summaryTarget,{plan,baseline=null,bands=null},startPeriod,events,profile,{debts=[],window:months=0,from=0}={}) {
    const m=root.ShellModel,r=root.ResultsModel,target=summaryTarget;
    const planData=r.splitData(plan,startPeriod,events,profile,debts),baseData=baseline?r.splitData(baseline,startPeriod,events,profile,debts):null;
    const bandData=bands?.cash?r.bandData(bands,startPeriod,events,profile,debts,'cash'):null;
    const end=months?from+months+1:undefined,cut=values=>values.slice(from,end);
    const lines=[['有這個事件',planData.summary.cash]];
    if(baseData)lines.unshift(['沒有這個事件',baseData.summary.cash]);
    const text=lines.map(([label,s])=>`${label}：現金最低 ${m.money(s.minimum)}，發生於 ${s.minimumPeriod}；期末 ${m.money(s.final)}。`);
    if(bandData)text.push(`隨機模擬到 ${bandData.summary.period}，一般情況現金約 ${m.money(bandData.summary.p50)}；9 成的模擬落在 ${m.money(bandData.summary.p5)} 到 ${m.money(bandData.summary.p95)} 之間。`);
    target.replaceChildren(...text.map(line=>root.FutureWalletShell.element('p',line)));
    if(!prepare(canvas,target))return;
    const labels=cut(planData.labels),shift=planData.markers.map(marker=>({...marker,index:marker.index-from})).filter(marker=>marker.index>=0&&marker.index<labels.length);
    const markers=new Set(shift.map(marker=>marker.index));
    // The size of the step each event makes in cash, from the month before it to the month it lands.
    const marks=shift.map(marker=>{const step=planData.cash[marker.index+from]-planData.cash[marker.index+from-1];return {index:marker.index,color:'#b45309',text:`${marker.name} ${step<0?'−':'+'}${m.money(Math.abs(step))}`};});
    const accent=root.getComputedStyle(root.document.documentElement).getPropertyValue('--accent').trim()||'#047857';
    const rgb=/^#([0-9a-f]{6})$/i.test(accent)?[1,3,5].map(i=>parseInt(accent.slice(i,i+2),16)).join(','):'4,120,87';
    const line=(label,values,color,width,extra={})=>({label,data:cut(values),borderColor:color,backgroundColor:color,borderWidth:width,pointRadius:0,pointHoverRadius:4,tension:0,fill:false,...extra});
    // Chart.js draws the lowest `order` last (on top): the plan sits above everything, the random range underneath.
    const datasets=[];
    if(bandData){
      const edge=(label,values,fill,alpha,order)=>line(label,values,`rgba(${rgb},.3)`,1,{fill,backgroundColor:`rgba(${rgb},${alpha})`,pointHoverRadius:0,order});
      datasets.push(edge('順利情況（隨機模擬）',bandData.series.p95,'+1',.14,6),edge('較差情況（隨機模擬）',bandData.series.p5,false,0,7),
        line('一般情況（隨機模擬）',bandData.series.p50,`rgba(${rgb},.9)`,1.5,{borderDash:[6,4],order:5}));
    }
    if(baseData)datasets.push(line('沒有這個事件',baseData.cash,'#0e7490',2.5,{order:2}));
    // Cash under zero is shaded red: that is the stretch where the plan runs out of money.
    datasets.push(line('有這個事件',planData.cash,'#b45309',3.5,{order:1,pointRadius:labels.map((_,i)=>markers.has(i)?4:0),segment:stepSegment(shift,7),
      fill:{target:{value:0},above:'rgba(0,0,0,0)',below:'rgba(180,35,24,.28)'}}));
    datasets.push(line('現金 0',planData.labels.map(()=>0),'#b42318',2,{borderDash:[2,3],pointHoverRadius:0,order:3}));
    const options=baseOptions(m,{...planData,markers:shift},{legend:true});
    finish(canvas,target,new root.Chart(canvas,{type:'line',data:{labels,datasets},options,plugins:[eventMarks(marks,chartFont())]}));
  }

  function destroyAll(){for(const chart of instances.values())chart.destroy();instances.clear();}
  root.addEventListener('pagehide',destroyAll);
  root.WalletCharts={draw,drawBands,drawTrajectories,drawCashflow,drawComposition,drawCurrentAllocation,drawCompare,destroyAll};
})(globalThis);
