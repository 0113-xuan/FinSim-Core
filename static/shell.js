(function(root) {
  'use strict';
  const textModel=typeof module!=='undefined'&&module.exports?require('./shell-model.js'):root.ShellModel;
  const fields = {
    profiles: 'user_id,monthly_income,cash_balance,fixed_expense,variable_expense,investment_value,monthly_investment,raise_rate,emergency_target_months,updated_at',
    debts: 'id,user_id,name,monthly_payment,remaining_months,created_at',
    plans: 'id,user_id,name,kind,created_at,updated_at',
    plan_events: 'id,plan_id,user_id,type,name,start_period,end_period,amount,monthly_amount,new_salary,details,created_at'
  };
  async function checked(query) {
    const {data, error} = await query;
    if (error) throw new Error(textModel.errorText(error));
    return data;
  }
  function createStore(client, userId) {
    const owned = table => client.from(table).select(fields[table]).eq('user_id', userId);
    const remove = async query => {
      const rows = await checked(query.select('id'));
      if (!rows?.length) throw new Error('資料已不存在或無法刪除，請重新載入');
    };
    return {
      profile: () => checked(owned('profiles').maybeSingle()),
      debts: () => checked(owned('debts').order('created_at')),
      plans: () => checked(owned('plans').order('created_at')),
      plan: id => checked(owned('plans').eq('id', id).maybeSingle()),
      events: planId => checked(owned('plan_events').eq('plan_id', planId).order('start_period')),
      saveProfile: values => checked(client.from('profiles').upsert({...values, user_id:userId, updated_at:new Date().toISOString()}, {onConflict:'user_id'}).select(fields.profiles).single()),
      addDebt: values => checked(client.from('debts').insert({...values, user_id:userId}).select(fields.debts).single()),
      removeDebt: id => remove(client.from('debts').delete().eq('user_id', userId).eq('id', id)),
      addPlan: values => checked(client.from('plans').insert({...values, user_id:userId}).select(fields.plans).single()),
      updatePlan: (id, values) => checked(client.from('plans').update({name:values.name, user_id:userId, updated_at:new Date().toISOString()}).eq('user_id', userId).eq('id', id).select(fields.plans).single()),
      removePlan: id => remove(client.from('plans').delete().eq('user_id', userId).eq('id', id)),
      addEvent: (planId, values) => checked(client.from('plan_events').insert({...values, plan_id:planId, user_id:userId}).select(fields.plan_events).single()),
      updateEvent: (planId, id, values) => checked(client.from('plan_events').update({...values, plan_id:planId, user_id:userId}).eq('user_id', userId).eq('plan_id', planId).eq('id', id).select(fields.plan_events).single()),
      removeEvent: (planId, id) => remove(client.from('plan_events').delete().eq('user_id', userId).eq('plan_id', planId).eq('id', id))
    };
  }
  function taipeiPeriod(date = new Date()) {
    const parts = new Intl.DateTimeFormat('en', {timeZone:'Asia/Taipei', year:'numeric', month:'2-digit'}).formatToParts(date);
    return `${parts.find(p => p.type === 'year').value}-${parts.find(p => p.type === 'month').value}`;
  }

  function element(tag,text,className) {
    const node=root.document.createElement(tag);
    if(text!=null)node.textContent=text;
    if(className)node.className=className;
    return node;
  }
  function showError(error) {
    const target=root.document.getElementById('pageError');
    target.textContent=`操作未完成：${textModel.errorText(error)}。請修正後重試；也可以重新整理頁面。`;
    target.hidden=false;
  }
  function status(text) { root.document.getElementById('pageStatus').textContent=text; }
  function renderNavigation(ctx) {
    const nav=root.document.getElementById('sideNav');nav.replaceChildren();
    const add=(text,href,selected=false)=>{
      const link=element('a',text);link.href=href;if(selected)link.setAttribute('aria-current','page');nav.append(link);
    };
    add('儀表板','/dashboard.html',ctx.page==='dashboard');
    add('目前財務狀況','/profile.html',ctx.page==='profile');
    nav.append(element('h2','計畫'));
    for(const plan of ctx.plans)add(plan.name,`/plan.html?id=${encodeURIComponent(plan.id)}`,ctx.page==='plan'&&ctx.planId===plan.id);
    add('新增計畫','/dashboard.html#new-plan');
  }
  async function init(page) {
    const ctx={page,planId:new URLSearchParams(root.location.search).get('id'),profile:null,debts:[],plans:[],
      session:null,store:null,alive:true,busy:false,controllers:new Set()};
    ctx.perform=async action=>{
      if(ctx.busy||!ctx.alive)return;
      ctx.busy=true;root.document.getElementById('pageError').hidden=true;
      const controls=[...root.document.querySelectorAll('#pageContent fieldset,#pageContent button')].map(node=>[node,node.disabled]);
      controls.forEach(([node])=>node.disabled=true);
      try{await action();}catch(error){if(ctx.alive)showError(error);}
      finally{if(ctx.alive){controls.forEach(([node,disabled])=>{if(node.isConnected)node.disabled=disabled;});ctx.busy=false;}}
    };
    ctx.calculation=async action=>{
      const controller=new AbortController();ctx.controllers.add(controller);
      const timeout=root.setTimeout(()=>controller.abort(),30000);
      const post=async(url,payload)=>{
        const response=await root.fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
        let data;try{data=await response.json();}catch(_){/* Gateway errors need not contain JSON. */}
        if(!response.ok){const detail=data?.detail;throw new Error(typeof detail==='string'?detail:Array.isArray(detail)?detail.map(e=>e.msg).join('；'):`計算失敗（HTTP ${response.status}）`);}
        if(!data)throw new Error('計算回應無法讀取');return data;
      };
      try{return await action(post);}catch(error){controller.abort();if(error.name==='AbortError')throw new Error('計算逾時或已取消，請重試');throw error;}
      finally{root.clearTimeout(timeout);ctx.controllers.delete(controller);}
    };
    const dispose=()=>{
      ctx.alive=false;ctx.controllers.forEach(c=>c.abort());
      root.document.getElementById('pageContent').replaceChildren();
      root.document.getElementById('sideNav')?.replaceChildren();
      root.document.getElementById('pageTitle').textContent='FutureWallet';
    };
    root.addEventListener('pagehide',dispose,{once:true});
    let observedSession,authVersion=0;
    try {
      const response=await root.fetch('/config/public',{cache:'no-store'});
      if(!response.ok)throw new Error('無法讀取登入設定');
      const config=await response.json();
      if(!config.configured)throw new Error('尚未設定 Supabase，請聯絡管理者完成登入設定');
      if(!root.supabase?.createClient)throw new Error('登入元件載入失敗，請重新整理');
      ctx.client=root.supabase.createClient(config.supabase_url,config.supabase_anon_key);
      ctx.client.auth.onAuthStateChange((_,session)=>{
        if(!ctx.alive)return;
        observedSession=session;authVersion++;
        if(ctx.session&&ctx.session.user.id!==session?.user?.id){dispose();root.location.replace('/login.html');}
      });
      const before=authVersion, data=await checked(ctx.client.auth.getSession());
      ctx.session=authVersion!==before?observedSession:data.session;
      if(ctx.session){
        ctx.store=createStore(ctx.client,ctx.session.user.id);
        ctx.profile=await ctx.store.profile();
        if(!ctx.alive)return null;
        if(observedSession!==undefined&&observedSession?.user?.id!==ctx.session.user.id){dispose();root.location.replace('/login.html');return null;}
      }
      const redirect=root.ShellModel.routeFor(page,ctx.session,ctx.profile);
      if(redirect){root.location.replace(redirect);return null;}
      if(ctx.session){
        [ctx.debts,ctx.plans]=await Promise.all([ctx.store.debts(),ctx.store.plans()]);
        if(!ctx.alive)return null;
        renderNavigation(ctx);
        for(const button of root.document.querySelectorAll('[data-sign-out]'))button.addEventListener('click',()=>ctx.perform(async()=>{
          await checked(ctx.client.auth.signOut());dispose();root.location.replace('/login.html');
        }));
      }
      root.document.getElementById('pageContent').hidden=false;
      status('');
      if(page==='login')return ctx;
      const menu=root.document.getElementById('menuToggle'),drawer=root.document.getElementById('shellSidebar'),scrim=root.document.getElementById('drawerScrim');
      let previousFocus;
      function close(){drawer.classList.remove('is-open');menu.setAttribute('aria-expanded','false');scrim.hidden=true;drawer.inert=root.matchMedia('(max-width:760px)').matches;previousFocus?.focus();}
      function open(){previousFocus=root.document.activeElement;drawer.inert=false;drawer.classList.add('is-open');menu.setAttribute('aria-expanded','true');scrim.hidden=false;root.document.getElementById('closeMenu').focus();}
      menu.addEventListener('click',open);scrim.addEventListener('click',close);root.document.getElementById('closeMenu').addEventListener('click',close);
      drawer.addEventListener('keydown',event=>{
        if(event.key==='Escape')close();
        if(event.key==='Tab'&&drawer.classList.contains('is-open')){
          const focusable=[...drawer.querySelectorAll('a,button')].filter(n=>!n.disabled&&n.offsetParent!==null),first=focusable[0],last=focusable.at(-1);
          if(event.shiftKey&&root.document.activeElement===first){event.preventDefault();last.focus();}
          else if(!event.shiftKey&&root.document.activeElement===last){event.preventDefault();first.focus();}
        }
      });
      const media=root.matchMedia('(max-width:760px)');
      const sync=()=>{drawer.inert=media.matches&&!drawer.classList.contains('is-open');if(!media.matches){drawer.classList.remove('is-open');scrim.hidden=true;menu.setAttribute('aria-expanded','false');}};
      media.addEventListener('change',sync);sync();
      return ctx;
    }catch(error){if(ctx.alive){showError(error);status('頁面尚未載入。');}return null;}
  }
  async function prepareSimulation(ctx,events,months,startPeriod=taipeiPeriod()) {
    const built=root.PlannerModel.buildSimulationRequest({profile:ctx.profile,debts:ctx.debts,events,startPeriod,months});
    let converted=null;
    if(built.vehicles.length){
      converted=await ctx.calculation(post=>post('/planner/vehicle-events',{start_period:startPeriod,months,inflation_rate:built.request.profile.inflation_rate??null,vehicles:built.vehicles}));
      if(!ctx.alive)throw new Error('登入狀態已變更');
      built.request.events.push(...converted.events);built.request.loans=[...(built.request.loans||[]),...converted.loans];
      built.request.assets=[...(built.request.assets||[]),...converted.assets];
    }
    return {...built,converted,startPeriod};
  }
  const api={createStore,taipeiPeriod,element,showError,status,renderNavigation,init,prepareSimulation,checked};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FutureWalletShell=api;
})(globalThis);
