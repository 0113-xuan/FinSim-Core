(function(root){
  'use strict';
  function create({form,profile,isAlive}){
    const S=root.FutureWalletShell,M=root.OccupationModel,$=id=>root.document.getElementById(id);
    const select=form.elements.occupation,salary=form.elements.new_salary;
    let items=null,loading=false,version=0,controller,state={occupation:M.initialOccupation(profile),reference:null};
    const active=()=>form.elements.type.value==='salary_change';
    function cancel(){version++;controller?.abort();}
    function fillOptions(){
      select.replaceChildren(...M.occupationOptions(items,state.occupation).map(item=>{
        const option=S.element('option',item.label);option.value=item.value;return option;
      }));select.value=state.occupation;
    }
    function render(reference){
      $('salaryReferenceStatus').textContent=M.referenceText(reference);
      $('salaryReferenceDetails').replaceChildren();
      $('applySalaryReference').disabled=!M.canApply(reference);
      if(reference?.available){
        for(const text of [reference.note,`統計對象：${reference.source.population}；資料期間：${reference.source.period_label}。`,
          reference.median==null?'此期間未提供同行業「一半員工低於此數」的中間薪資。':`中間薪資（一半員工低於此數）NT$${Number(reference.median).toLocaleString('zh-TW')}。`])
          $('salaryReferenceDetails').append(S.element('p',text));
        const source=S.element('a',reference.source.name);source.href=reference.source.url;source.target='_blank';source.rel='noopener noreferrer';
        $('salaryReferenceDetails').append(source,S.element('small',`下載日期 ${reference.source.downloaded_date}；${reference.source.license}。`));
      }
    }
    async function refresh(){
      cancel();if(items)state=M.chooseOccupation(state,select.value);render(null);
      if(!active()||!items||!isAlive())return;
      if(!state.occupation)return;
      const current=version;controller=new AbortController();const requestController=controller;
      const timeout=root.setTimeout(()=>requestController.abort(),15000);
      $('salaryReferenceStatus').textContent='正在讀取官方薪資快照…';
      try{
        const response=await root.fetch(`/salary-reference?${new URLSearchParams({occupation:state.occupation})}`,{signal:requestController.signal});
        if(!response.ok)throw new Error('讀取失敗');
        const data=await response.json();if(current!==version||!isAlive()||!active())return;
        state=M.receiveReference(state,data);render(state.reference);
      }catch(_){if(current===version&&isAlive())$('salaryReferenceStatus').textContent='薪資參考載入未完成；可自行填寫新實領月薪，或按「重新載入薪資參考」重試。';}
      finally{root.clearTimeout(timeout);}
    }
    async function load(){
      if(loading)return;loading=true;
      const requestController=new AbortController();const timeout=root.setTimeout(()=>requestController.abort(),15000);
      try{
        const response=await root.fetch('/occupations',{signal:requestController.signal});if(!response.ok)throw new Error('讀取失敗');
        const data=await response.json();if(!isAlive())return;items=data;fillOptions();sync();await refresh();
      }catch(_){if(isAlive())$('salaryReferenceStatus').textContent='行業清單載入未完成；可自行填寫新實領月薪，或按「重新載入薪資參考」重試。';}
      finally{root.clearTimeout(timeout);loading=false;}
    }
    function sync(){
      const visible=active();$('salaryReferenceSection').hidden=!visible;select.disabled=!visible||!items;
      if(!visible)cancel();
      const note=M.publicLoanNote(profile?.occupation);$('publicSectorLoanNote').textContent=note;
      $('publicSectorLoanNote').hidden=!(note&&form.elements.type.value==='vehicle_purchase'&&form.elements.payment_method.value==='financed');
    }
    function reset(details){
      cancel();state={occupation:M.initialOccupation(profile,details),reference:null};
      if(items)fillOptions();render(null);sync();if(active())refresh();
    }
    select.addEventListener('change',refresh);
    $('applySalaryReference').addEventListener('click',()=>{
      if(form.elements.type.value!=='salary_change'||salary.disabled)return;
      state=M.applyReference({...state,new_salary:salary.value});salary.value=state.new_salary;
      salary.dispatchEvent(new Event('input',{bubbles:true}));salary.focus();
      S.status('已帶入官方稅前參考值，請依實際實領金額調整後再儲存。');
    });
    $('retrySalaryReference').addEventListener('click',()=>items?refresh():load());
    root.addEventListener('pagehide',cancel,{once:true});
    load();
    return {sync,reset,refresh,details:()=>state.occupation?{occupation:state.occupation}:{}};
  }
  root.SalaryReferenceForm={create};
})(globalThis);
