(function(root) {
  'use strict';
  const S=root.FutureWalletShell,M=root.ShellModel,$=id=>root.document.getElementById(id);
  const numeric=(form,key)=>{
    const text=form.elements.namedItem(key).value.trim();
    if(!text||!Number.isFinite(Number(text)))throw new Error('請填寫有效數字');return Number(text);
  };
  function submit(form,ctx,action){form.addEventListener('submit',event=>{event.preventDefault();if(form.reportValidity())ctx.perform(()=>action(event));});}
  async function login(ctx){
    const form=$('loginForm');
    submit(form,ctx,async event=>{
      const signup=event.submitter?.value==='signup';
      const credentials={email:form.elements.email.value.trim(),password:form.elements.password.value};
      const data=await S.checked(signup?ctx.client.auth.signUp(credentials):ctx.client.auth.signInWithPassword(credentials));
      form.elements.password.value='';
      if(!ctx.alive)return;
      if(data.session){
        const profile=await S.createStore(ctx.client,data.session.user.id).profile();
        if(ctx.alive)root.location.replace(M.routeFor('login',data.session,profile));
      }else if(signup)S.status('請到信箱點確認連結後再登入。');
      else throw new Error('未取得登入狀態，請重新登入');
    });
  }
  async function finances(ctx){
    const form=$('financeForm'),pending=[];
    const L=root.LocationModel,city=form.elements.city,district=form.elements.district;
    let regions=[];
    function options(select,values,empty,selected=''){
      select.replaceChildren();for(const value of ['',...values]){const option=S.element('option',value||empty);option.value=value;select.append(option);}select.value=selected;
    }
    function syncDistrict(selected=''){options(district,L.districtsForCity(regions,city.value),'選擇行政區（選填）',selected);district.disabled=!city.value;}
    city.disabled=district.disabled=true;
    async function loadRegions(){try{
      const response=await root.fetch('/regions');if(!response.ok)throw new Error('無法讀取行政區');regions=await response.json();if(!ctx.alive)return;
      options(city,regions.map(r=>r.city),'選擇縣市（選填）',ctx.profile?.city||'');city.disabled=false;syncDistrict(ctx.profile?.district||'');
    }catch(_){if(ctx.alive)$('locationStatus').textContent='所在地清單載入未完成；其他財務資料仍可儲存，重新整理可重試。';}}
    loadRegions();
    city.addEventListener('change',()=>syncDistrict());
    if(ctx.page==='profile')$('accountEmail').textContent=`登入帳號：${ctx.session.user.email||'未提供電子郵件'}`;
    if(ctx.profile)for(const[key,value]of Object.entries(ctx.profile)){if(['city','district'].includes(key))continue;const input=form.elements.namedItem(key);if(input)input.value=value??'';}
    function renderDebts(){
      const list=$('debtList');list.replaceChildren();
      const rows=[...ctx.debts,...pending];
      if(!rows.length)list.append(S.element('li','目前沒有貸款'));
      for(const debt of rows){
        const li=S.element('li'),line=S.element('div',null,'event-head');
        line.append(S.element('span',`${debt.name}｜每月 ${M.money(debt.monthly_payment)}｜剩餘 ${debt.remaining_months} 期`,'event-copy'));
        const button=S.element('button','刪除');button.type='button';button.setAttribute('aria-label',`刪除${debt.name}`);
        button.addEventListener('click',()=>ctx.perform(async()=>{
          if(pending.includes(debt))pending.splice(pending.indexOf(debt),1);
          else{await ctx.store.removeDebt(debt.id);if(!ctx.alive)return;ctx.debts=ctx.debts.filter(item=>item.id!==debt.id);}
          renderDebts();S.status('貸款已移除。');
        }));line.append(button);li.append(line);list.append(li);
      }
    }
    $('addDebt').addEventListener('click',()=>ctx.perform(async()=>{
      const name=form.elements.debt_name.value.trim();if(!name)throw new Error('請填寫貸款名稱');
      const debt={name,monthly_payment:numeric(form,'monthly_payment'),remaining_months:numeric(form,'remaining_months')};
      if(debt.monthly_payment<0||debt.monthly_payment>10000000||!Number.isInteger(debt.remaining_months)||debt.remaining_months<0||debt.remaining_months>1200)throw new Error('請填寫非負還款金額與整數剩餘期數');
      if(ctx.page==='onboarding'){pending.push(debt);S.status('貸款已加入待儲存清單，請完成下方財務資料儲存。');}
      else{const saved=await ctx.store.addDebt(debt);if(!ctx.alive)return;ctx.debts.push(saved);S.status('貸款已新增。');}
      for(const key of ['debt_name','monthly_payment','remaining_months'])form.elements.namedItem(key).value='';renderDebts();
    }));
    submit(form,ctx,async()=>{
      if(['debt_name','monthly_payment','remaining_months'].some(key=>form.elements.namedItem(key).value.trim()))throw new Error('貸款資料尚未加入清單，請先按「新增貸款」或清空貸款輸入欄位');
      const values={};
      for(const key of ['monthly_income','fixed_expense','variable_expense','cash_balance','investment_value','monthly_investment','emergency_target_months'])values[key]=numeric(form,key);
      values.raise_rate=form.elements.raise_rate.value.trim()===''?null:numeric(form,'raise_rate');
      // Failed optional reference loading must not erase a previously saved location.
      if(regions.length)Object.assign(values,L.locationValues(regions,city.value,district.value));
      const profile=await ctx.store.saveProfile(values);if(!ctx.alive)return;ctx.profile=profile;
      while(pending.length){
        try{const saved=await ctx.store.addDebt(pending[0]);if(!ctx.alive)return;ctx.debts.push(saved);pending.shift();}
        catch(error){renderDebts();throw new Error(`財務資料已儲存，但部分貸款尚未儲存：${error.message}。可再次儲存剩餘貸款`);}
      }
      if(ctx.page==='onboarding')root.location.assign('/dashboard.html');
      else{renderDebts();S.status(ctx.store.locationSupported?'財務資料已儲存，儀表板會使用新的數字重新計算。':'其他財務資料已儲存；所在地尚未儲存，請管理者先新增欄位。');}
    });
    renderDebts();
  }
  async function dashboard(ctx){
    const summary=M.financialSummary(ctx.profile,ctx.debts);
    $('currentNetWorth').textContent=M.money(summary.netWorth);$('currentAssets').textContent=M.money(summary.assets);$('currentDebt').textContent=M.money(summary.debtTotal);
    $('assetBreakdown').textContent=`現金 ${M.money(summary.cash)}；投資市值 ${M.money(summary.investment)}。`;
    if(!ctx.debts.length)$('currentDebtList').append(S.element('p','目前沒有貸款'));
    for(const debt of ctx.debts)$('currentDebtList').append(S.element('p',`${debt.name}：每月 ${M.money(debt.monthly_payment)}，剩餘 ${debt.remaining_months} 期，剩餘應還 ${M.money(Number(debt.monthly_payment)*Number(debt.remaining_months))}。`));
    const cards=$('planCards'),entries=[];
    for(const plan of ctx.plans){
      const card=S.element('article',null,'plan-card'),heading=S.element('h3'),link=S.element('a',plan.name);link.href=`/plan.html?id=${encodeURIComponent(plan.id)}`;heading.append(link);card.append(heading);
      const info=S.element('p','正在讀取事件與計算走勢…');card.append(info);cards.append(card);entries.push({plan,card,info});
    }
    const create=S.element('button',null,'plan-card new-plan-card');create.id='new-plan';create.type='button';
    create.append(S.element('strong','新增計畫'),S.element('span','從購車、換工作或自訂收支開始。'));
    create.addEventListener('click',()=>ctx.openPlanDialog(create));cards.append(create);
    for(const {plan,card,info}of entries){
      if(!ctx.alive)return;
      try{
        const events=await ctx.store.events(plan.id);if(!ctx.alive)return;
        info.textContent=`${events.length} 個事件｜未來 240 個月`;
        const built=await S.prepareSimulation(ctx,events,240);
        const response=await ctx.calculation(post=>post('/simulate',{...built.request,seed:42}));if(!ctx.alive)return;
        const result=response.result,frame=S.element('div',null,'chart-frame mini'),canvas=S.element('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',`${plan.name}淨資產走勢`);frame.append(canvas);card.append(frame);
        const text=S.element('div',null,'chart-summary');text.id=`chart-${plan.id}`;card.append(text);
        root.WalletCharts.draw(canvas,text,result.simulation_curve,built.startPeriod,events,ctx.profile,{mini:true,debts:ctx.debts});
        card.append(S.element('p',`期末淨資產：${M.money(result.summary.final_net_worth)}`));
        card.append(S.element('p',`第一次現金小於 0：${result.summary.first_negative_cash_month==null?'未出現':root.PlannerModel.monthToPeriod(built.startPeriod,result.summary.first_negative_cash_month)}`));
        for(const warning of built.warnings)card.append(S.element('p',warning));
        if(built.converted)card.append(S.element('p',built.converted.note));
      }catch(error){if(ctx.alive){info.textContent=`走勢計算未完成：${error.message}。重新整理可重試。`;info.setAttribute('role','alert');}}
    }
  }
  async function boot(){
    const page=root.document.body.dataset.page,ctx=await S.init(page);if(!ctx)return;
    try{
      if(page==='login')await login(ctx);
      else if(page==='onboarding'||page==='profile')await finances(ctx);
      else if(page==='dashboard')await dashboard(ctx);
      else if(page==='plan')await root.PlanPage.start(ctx);
    }catch(error){if(ctx.alive)S.showError(error);}
  }
  root.addEventListener('pageshow',event=>{if(event.persisted)root.location.reload();});
  boot();
})(globalThis);
