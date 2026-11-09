(function(root) {
  'use strict';
  // Scenario comparison: each scenario is a set of saved plan events. Every scenario (plus an optional
  // do-nothing baseline) goes through the same /simulate and /monte-carlo endpoints with the same seed.
  async function start(ctx) {
    const S=root.FutureWalletShell,M=root.ShellModel,C=root.CompareModel,model=root.PlannerModel,$=id=>root.document.getElementById(id);
    const rows=await Promise.all(ctx.plans.map(plan=>ctx.store.events(plan.id)));if(!ctx.alive)return;
    const options=C.eventOptions(ctx.plans,Object.fromEntries(ctx.plans.map((plan,index)=>[plan.id,rows[index]])));
    if(!options.length){$('compareEmpty').hidden=false;return;}
    $('compareWorkspace').hidden=false;
    $('compareStart').value=S.taipeiPeriod();
    let scenarios=C.defaultScenarios(options);
    const byId=new Map(options.map(option=>[option.id,option]));

    function runStatus(text,working=false){
      const node=$('compareStatus');node.textContent=text;
      if(working)node.dataset.state='working';else delete node.dataset.state;
    }
    function invalidate(){
      const hadResults=!$('compareResults').hidden;
      $('compareResults').hidden=true;$('compareWarnings').replaceChildren();
      $('compareError').hidden=true;$('compareError').textContent='';
      runStatus(hadResults?'情境或輸入已變更，上一次的結果已清除，請重新執行比較。':'');
    }
    function renderScenarios(focusIndex=null){
      const list=$('scenarioList');list.replaceChildren();
      scenarios.forEach((scenario,index)=>{
        const card=S.element('fieldset',null,'scenario-card'),legend=S.element('legend',`情境 ${index+1}`);
        const nameLabel=S.element('label','情境名稱（選填，留空會用事件名稱）'),name=S.element('input');
        name.maxLength=80;name.value=scenario.name;name.placeholder=C.scenarioName({...scenario,name:''},index,byId);
        name.addEventListener('input',()=>{scenario.name=name.value;invalidate();});nameLabel.append(name);
        const group=S.element('div',null,'scenario-events');group.setAttribute('role','group');group.setAttribute('aria-label',`情境 ${index+1} 的事件`);
        for(const option of options){
          const label=S.element('label',null,'scenario-event'),box=S.element('input');box.type='checkbox';box.value=option.id;box.checked=scenario.eventIds.includes(option.id);
          const copy=S.element('span');copy.append(S.element('strong',option.title),S.element('small',option.detail));
          box.addEventListener('change',()=>{
            scenario.eventIds=options.map(item=>item.id).filter(id=>id===option.id?box.checked:scenario.eventIds.includes(id));
            name.placeholder=C.scenarioName({...scenario,name:''},index,byId);invalidate();
          });
          label.append(box,copy);group.append(label);
        }
        card.append(legend,nameLabel,group);
        if(scenarios.length>1){
          const remove=S.element('button','移除這個情境');remove.type='button';remove.setAttribute('aria-label',`移除情境 ${index+1}`);
          remove.addEventListener('click',()=>{if(ctx.busy)return;scenarios.splice(index,1);renderScenarios(Math.min(index,scenarios.length-1));invalidate();});card.append(remove);
        }
        list.append(card);
      });
      const full=scenarios.length>=C.MAX_SCENARIOS;
      $('addScenario').disabled=full;$('scenarioLimit').textContent=full?`最多 ${C.MAX_SCENARIOS} 個情境。`:'';
      if(focusIndex!=null)list.children[focusIndex]?.querySelector('input[type="checkbox"]')?.focus();
    }
    $('addScenario').addEventListener('click',()=>{
      if(ctx.busy||scenarios.length>=C.MAX_SCENARIOS)return;
      scenarios.push({name:'',eventIds:[]});renderScenarios(scenarios.length-1);invalidate();
    });
    $('compareForm').addEventListener('input',invalidate);

    // Table cells carry a data-label so the narrow layout can still say which scenario a number belongs to.
    function cell(parent,names,index,value){
      const td=S.element('td');td.dataset.label=names[index];
      if(value==null||value==='—'){td.className='na';td.textContent='—';parent.append(td);return;}
      const main=typeof value==='object'?value:{text:value};
      td.append(S.element('strong',main.text));
      if(main.mark)td.append(S.element('small',main.mark,'best-mark'));
      if(main.note)td.append(S.element('small',main.note));
      parent.append(td);
    }
    function metricTable(caption,corner,names,body){
      const table=S.element('table',null,'metric-table compare-table'),head=S.element('tr');
      table.append(S.element('caption',caption));
      for(const text of [corner,...names]){const th=S.element('th',text);th.scope='col';head.append(th);}
      const thead=S.element('thead');thead.append(head);table.append(thead);
      const tbody=S.element('tbody');
      for(const [label,cells] of body){
        const tr=S.element('tr'),th=S.element('th',label);th.scope='row';tr.append(th);
        cells.forEach((value,index)=>cell(tr,names,index,value));tbody.append(tr);
      }
      table.append(tbody);return table;
    }
    function renderResults(runs,startPeriod,months){
      const summaries=runs.map(run=>C.summarize(run,startPeriod,months));
      const view=C.conclusion(summaries,startPeriod,months),lead=view.leaders,names=summaries.map(row=>row.name);
      $('compareConclusion').dataset.tone=view.tone;
      $('compareHeadline').textContent=view.headline;
      $('compareLines').replaceChildren(...view.lines.map(line=>S.element('p',line)));
      $('compareCaveat').textContent=view.caveat;
      // A "best" mark only means something when the scenarios actually differ on that measure.
      const mark=(set,text)=>index=>set.size<summaries.length&&set.has(index)?text:undefined;
      const worthMark=mark(lead.netWorth,'最高'),cashMark=mark(lead.minimumCash,'最高'),riskMark=mark(lead.shortfall,'最低');
      const baselineIndex=runs.findIndex(run=>run.kind==='baseline');
      const body=[
        ['包含的事件',runs.map(run=>run.eventLabels.length?run.eventLabels.join('、'):'沒有事件')],
        ['期末淨資產：一般情況',summaries.map((row,index)=>({text:M.money(row.netWorth.p50),mark:worthMark(index)}))],
        ['期末淨資產：較差情況',summaries.map(row=>M.money(row.netWorth.p5))],
        ['期末淨資產：順利情況',summaries.map(row=>M.money(row.netWorth.p95))],
      ];
      if(baselineIndex>=0)body.push([`和「${C.BASELINE_NAME}」相比（一般情況淨資產）`,summaries.map((row,index)=>index===baselineIndex?'—':C.netWorthGap(row,summaries[baselineIndex]))]);
      body.push(
        ['最低現金（固定值）',summaries.map((row,index)=>({text:M.money(row.minimumCash),note:`發生在 ${row.minimumCashPeriod}`,mark:cashMark(index)}))],
        ['第一次現金小於 0（固定值）',summaries.map(row=>row.firstNegativePeriod||'未出現')],
        ['現金不足機率（隨機模擬）',summaries.map((row,index)=>({text:M.wholePercent(row.shortfall),mark:riskMark(index)}))],
      );
      $('compareTable').replaceChildren(metricTable('各情境期末數字',`${model.monthToPeriod(startPeriod,months)} 的結果`,names,body));
      const profile=ctx.profile,debts=ctx.debts;
      const net=C.chartSeries(runs,'netWorth',startPeriod,profile,debts),cash=C.chartSeries(runs,'cash',startPeriod,profile,debts);
      root.WalletCharts.drawCompare($('compareNetChart'),$('compareNetSummary'),net,C.chartSummary(net,'淨資產'));
      root.WalletCharts.drawCompare($('compareCashChart'),$('compareCashSummary'),cash,C.chartSummary(cash,'現金（較差情況）'),{zeroLine:true});
      const cars=C.vehicleRows(runs);
      $('compareVehicles').hidden=!cars.length;
      if(cars.length){
        const headers=['購車月份','一次支出','每月車貸','車貸總利息','期末車輛估值','期間經濟成本'],table=S.element('table',null,'metric-table compare-table');
        table.append(S.element('caption','每台車的成本'));const head=S.element('tr');
        for(const text of ['情境：車款',...headers]){const th=S.element('th',text);th.scope='col';head.append(th);}
        const thead=S.element('thead');thead.append(head);table.append(thead);const tbody=S.element('tbody');
        for(const car of cars){
          const tr=S.element('tr'),th=S.element('th',`${car.scenario}：${car.name}`);th.scope='row';tr.append(th);
          const values=[model.monthToPeriod(startPeriod,car.purchase_month),...[car.one_time_cash,car.monthly_loan_payment,car.total_loan_interest,car.ending_vehicle_value,car.economic_cost_in_horizon].map(M.money)];
          values.forEach((value,index)=>cell(tr,headers,index,value));
          tbody.append(tr);
        }
        table.append(tbody);$('compareVehicleTable').replaceChildren(table);
        $('compareVehicleNote').textContent=runs.find(run=>run.converted)?.converted.note||'';
      }
      const first=runs[0];
      $('compareAssumptionList').replaceChildren(...[{label:'比較方式',value:`每個情境都用相同的起始月份、期間，以及同一組 ${C.SIMULATIONS} 次歷史資料抽樣（種子 ${C.SEED}）；差異只來自事件，不是運氣。`},
        ...root.ResultsModel.assumptionRows({simulation:first.simulation,mc:first.mc,request:first.built.request,startPeriod,months,
          simulations:C.SIMULATIONS,seed:C.SEED,converted:runs.find(run=>run.converted)?.converted||null})]
        .flatMap(row=>[S.element('dt',row.label),S.element('dd',row.value)]));
      $('compareDataSources').replaceChildren(...first.mc.data_sources.map(source=>S.element('li',`資料來源：${source.publisher}「${source.name}」，${source.period_start} 至 ${source.period_end}`)));
      $('compareResults').hidden=false;
    }

    $('compareForm').addEventListener('submit',event=>{
      event.preventDefault();if(!$('compareForm').reportValidity())return;
      ctx.perform(async()=>{
        invalidate();
        const startPeriod=$('compareStart').value,months=Number($('compareMonths').value);
        const plan=C.resolveScenarios(scenarios,options,{baseline:$('includeBaseline').checked});
        if(plan.problems.length)throw new Error(plan.problems.join('；'));
        const runs=[];
        try{
          for(const [index,entry] of plan.entries.entries()){
            runStatus(`正在計算「${entry.name}」（${index+1}／${plan.entries.length}），請稍候…`,true);
            const built=await S.prepareSimulation(ctx,entry.events,months,startPeriod);if(!ctx.alive)return;
            const [simulation,mc]=await ctx.calculation(post=>Promise.all([
              post('/simulate',{...built.request,seed:C.SEED}),
              post('/monte-carlo',{...built.request,simulations:C.SIMULATIONS,seed:C.SEED,sample_paths:0})]));
            if(!ctx.alive)return;
            runs.push({...entry,built,converted:built.converted,simulation:simulation.result,mc});
            for(const warning of built.warnings)$('compareWarnings').append(S.element('li',`${entry.name}：${warning}`));
          }
          renderResults(runs,startPeriod,months);
          runStatus('比較完成，結果在下方。');
          return $('compareConclusionHeading');
        }catch(error){runStatus('');$('compareWarnings').replaceChildren();throw error;}
      },{scope:'comparePanel',errorId:'compareError'});
    });
    renderScenarios();
  }
  root.ComparePage={start};
})(globalThis);
