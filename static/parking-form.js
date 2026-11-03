(function(root){
  'use strict';
  function create({form,profile,isAlive}){
    const S=root.FutureWalletShell,M=root.LocationModel,$=id=>root.document.getElementById(id),field=key=>form.elements.namedItem(key);
    let lotId=null,nonOwnedAmount='',version=0,controller,cache=null;
    function selected(){for(const button of $('parkingLots').querySelectorAll('[data-parking-id]'))button.setAttribute('aria-pressed',String(button.dataset.parkingId===lotId));}
    function render(data){
      const target=$('parkingLots');target.replaceChildren();$('parkingSource').replaceChildren();
      const presentation=M.parkingPresentation(profile.district,data);
      $('parkingStatus').replaceChildren(...[presentation.coverage,presentation.message,presentation.summary].filter(Boolean).map(text=>S.element('span',text)));
      if(data.data_available&&data.source.is_sample)$('parkingStatus').prepend(S.element('strong','測試資料，非真實停車行情。'));
      if(data.data_available){
        for(const lot of M.sortParkingLots(data.lots)){
          const node=S.element(lot.monthly_rent_twd==null?'article':'button',null,'parking-lot');
          node.append(S.element('span',M.parkingLotText(lot)));
          if(lot.monthly_rent_twd!=null){
            node.type='button';node.dataset.parkingId=lot.id;node.setAttribute('aria-pressed',String(lotId===lot.id));
            if(lot.monthly_rent_text)node.append(S.element('small',`月租原文：${lot.monthly_rent_text}`));
            node.addEventListener('click',()=>{if($('parkingFields').disabled)return;lotId=lot.id;field('monthly_parking').value=lot.monthly_rent_twd;nonOwnedAmount=String(lot.monthly_rent_twd);selected();});
          }
          target.append(node);
        }
      }
      const source=S.element('a','交通部 TDX');source.href=data.source.url.replace('{city}',data.tdx_city||'Taipei');source.target='_blank';source.rel='noopener noreferrer';
      $('parkingSource').append(source,`（快照日期 ${data.source.snapshot_date}），實際價格以停車場公告為準。`);
    }
    async function refresh(){
      controller?.abort();const current=++version;
      $('parkingLots').replaceChildren();$('parkingSource').replaceChildren();
      $('parkingReference').hidden=field('has_parking_space').value==='true';
      if(field('type').value!=='vehicle_purchase'||$('parkingReference').hidden)return;
      if(!profile.city||!profile.district){
        $('parkingStatus').replaceChildren('到「',Object.assign(S.element('a','目前財務狀況'),{href:'/profile.html'}),'」填寫所在地，就能看到附近停車場行情');return;
      }
      if(cache){render(cache);return;}
      $('parkingStatus').textContent='正在讀取停車場快照…';controller=new AbortController();const requestController=controller;
      const timeout=root.setTimeout(()=>requestController.abort(),15000);
      try{
        const query=new URLSearchParams({city:profile.city,district:profile.district});
        const response=await root.fetch(`/planner/parking?${query}`,{signal:requestController.signal});if(!response.ok)throw new Error('讀取失敗');
        const data=await response.json();if(current!==version||!isAlive())return;cache=data;render(data);
      }catch(_){if(current===version&&isAlive())$('parkingStatus').textContent='停車場資料載入未完成，可自行填寫停車費，或按「重新載入停車場」重試。';}
      finally{root.clearTimeout(timeout);}
    }
    function sync(){
      const vehicle=field('type').value==='vehicle_purchase';$('vehicleParkingSection').hidden=!vehicle;$('parkingFields').disabled=!vehicle;
      $('parkingReference').hidden=field('has_parking_space').value==='true';
    }
    function reset(details=null){
      controller?.abort();version++;lotId=details?.parking_lot_id||null;nonOwnedAmount=field('monthly_parking').value;
      field('has_parking_space').value=details?.has_parking_space===true?'true':'false';sync();refresh();
    }
    field('has_parking_space').addEventListener('change',()=>{
      lotId=null;if(field('has_parking_space').value==='true'){nonOwnedAmount=field('monthly_parking').value;field('monthly_parking').value='0';}
      else field('monthly_parking').value=nonOwnedAmount;
      sync();refresh();
    });
    field('monthly_parking').addEventListener('input',()=>{lotId=null;if(field('has_parking_space').value==='false')nonOwnedAmount=field('monthly_parking').value;selected();});
    $('retryParking').addEventListener('click',()=>{cache=null;refresh();});
    root.addEventListener('pagehide',()=>{version++;controller?.abort();},{once:true});
    return {sync,reset,refresh,details:()=>({has_parking_space:field('has_parking_space').value==='true',...(lotId&&field('has_parking_space').value==='false'?{parking_lot_id:lotId}:{})})};
  }
  root.ParkingForm={create};
})(globalThis);
