(function(root) {
  'use strict';
  function create({form,isAlive}) {
    const S=root.FutureWalletShell,M=root.VehicleFeesModel,$=id=>root.document.getElementById(id),field=key=>form.elements.namedItem(key);
    let legacy=false,taxCustom=false,taxSaved=false,refs=[],rows=[],dirty=new Set(),savedItems,latest=null,ready=false,pending=false,version=0,controller,timer;
    const el=S.element;
    function link(source){const a=el('a',source.name);a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';return a;}
    function spec(car) {
      const hasSpec=!!car;
      if(car){field('displacement_cc').value=car.displacement_cc;field('fuel_type').value=car.fuel_type;}
      field('displacement_cc').readOnly=hasSpec;
      field('fuel_type').dataset.catalog=hasSpec?'true':'false';sync();
      $('vehicleSpecSource').replaceChildren();
      if(car)$('vehicleSpecSource').append(el('span','原廠規格：'),link({name:`${car.displacement_cc} cc`,url:car.spec_source}));
      else $('vehicleSpecSource').textContent='自訂車款請填排氣量；純電車可填 0。';
      refresh();
    }
    function sync(){
      const vehicle=field('type').value==='vehicle_purchase';$('vehicleFeesSection').hidden=!vehicle;
      $('vehicleFeesFields').disabled=!vehicle;
      field('fuel_type').disabled=!vehicle||field('fuel_type').dataset.catalog==='true';
      field('displacement_cc').required=vehicle&&!legacy;
    }
    // The total is shown both on the form and inside the insurance dialog.
    function setTotal(text){$('insuranceTotal').textContent=text;$('insuranceDialogTotal').textContent=text;}
    function summarize(){
      $('insuranceSummary').textContent=legacy||!refs.length?'':`已選：${rows.filter(row=>row.selected).map(row=>refs.find(ref=>ref.id===row.id)?.name).filter(Boolean).join('、')||'無'}`;
    }
    function sum(){
      if(legacy)return;
      try{const result=M.insuranceSelection(rows);field('annual_insurance').value=result.annual_insurance;setTotal(`保險合計：${M.money(result.annual_insurance)}／年`);}
      catch(error){field('annual_insurance').value='';setTotal(error.message);}
      summarize();
    }
    function renderInsurance(){
      $('insuranceItems').hidden=legacy;$('legacyInsuranceHint').hidden=!legacy;
      field('annual_insurance').readOnly=!legacy;
      $('openInsuranceDialog').disabled=legacy||!refs.length;summarize();
      const container=$('insuranceItems');container.replaceChildren();
      if(legacy){setTotal('保留原本的保險預算；可重新選擇保險項目。');return;}
      if(!refs.length){setTotal('填寫車價與排氣量後載入保險參考資料。');return;}
      const body=el('fieldset',null,'insurance-body');body.append(el('legend','車體損失險（三擇一，也可不保）'));
      const noneLabel=el('label',null,'insurance-choice'),none=el('input');none.type='radio';none.name='body_coverage';none.value='none';none.checked=!rows.some(row=>row.id.startsWith('body_')&&row.selected);
      noneLabel.append(none,el('span','不保車體損失險'));body.append(noneLabel);
      none.addEventListener('change',()=>{
        rows.filter(r=>r.id.startsWith('body_')).forEach(r=>{r.selected=false;const input=container.querySelector(`[data-insurance-amount="${r.id}"]`);input.disabled=true;input.required=false;});sum();
      });
      for(const ref of refs){
        const row=rows.find(r=>r.id===ref.id),article=el('div',null,'insurance-row'),label=el('label',null,'insurance-choice'),choice=el('input');
        choice.type=ref.id.startsWith('body_')?'radio':'checkbox';choice.name=ref.id.startsWith('body_')?'body_coverage':`coverage_${ref.id}`;choice.value=ref.id;choice.checked=row.selected;choice.disabled=ref.required;
        const title=el('span',ref.name+(ref.required?'（依法必保）':''));label.append(choice,title);
        const description=el('small',ref.description),range=el('small',ref.low===ref.high?`參考估算：${M.money(ref.default)}／年`:`參考範圍：${M.money(ref.low)}–${M.money(ref.high)}／年`);
        const amountLabel=el('label','年保費（元）'),amount=el('input');amount.type='number';amount.min='0';amount.max='20000000';amount.step='0.01';amount.value=row.amount;amount.dataset.insuranceAmount=ref.id;amount.disabled=!row.selected;amount.required=row.selected;
        amountLabel.append(amount);article.append(label,description,range,amountLabel,link(ref.source));
        amount.addEventListener('input',()=>{row.amount=amount.value;dirty.add(row.id);sum();});
        choice.addEventListener('change',()=>{
          if(ref.required)return;
          if(ref.id.startsWith('body_'))rows.filter(r=>r.id.startsWith('body_')).forEach(r=>r.selected=r.id===ref.id);
          else row.selected=choice.checked;
          // Keep the focused choice in place while updating input availability.
          for(const item of rows){const input=container.querySelector(`[data-insurance-amount="${item.id}"]`);if(input){input.disabled=!item.selected;input.required=item.selected;}}
          sum();
        });
        if(ref.id.startsWith('body_'))body.append(article);else container.append(article);
      }
      container.append(body);sum();
    }
    function taxStatus(){
      $('taxCustomStatus').textContent=taxCustom?'已改為自訂金額':'';
      $('restoreOfficialTax').hidden=!taxCustom;$('restoreOfficialTax').disabled=latest?.tax.total==null;
    }
    function renderTax(tax){
      if(taxSaved){taxCustom=tax.total==null||Number(field('annual_tax').value)!==tax.total;taxSaved=false;}
      const target=$('officialTax');target.replaceChildren();
      for(const[key,title]of [['license_tax','使用牌照稅'],['road_fee','公路養管費']]){
        const row=el('p',`${title}：${M.money(tax[key])}／年`),small=el('small');small.append(link(tax.sources[key]));row.append(small);target.append(row);
      }
      target.append(el('p',`官方合計：${M.money(tax.total)}／年`));
      for(const note of tax.notes)target.append(el('small',note));
      if(!taxCustom)field('annual_tax').value=tax.total??'';taxStatus();
    }
    async function refresh(){
      root.clearTimeout(timer);controller?.abort();const current=++version;ready=false;pending=false;
      if(field('type').value!=='vehicle_purchase')return;
      const cc=field('displacement_cc').value,price=field('purchase_price').value;
      if(!cc.trim()||!price.trim()||!field('displacement_cc').checkValidity()||!field('purchase_price').checkValidity()){
        $('feesStatus').textContent='請先填寫有效的車價與排氣量。';return;
      }
      controller=new AbortController();const requestController=controller;pending=true;$('feesStatus').textContent='正在載入官方稅費與保險參考資料…';
      const timeout=root.setTimeout(()=>requestController.abort(),15000);
      try{
        const params=new URLSearchParams({displacement_cc:cc,fuel_type:field('fuel_type').value,purchase_price:price});
        const response=await root.fetch(`/planner/vehicle-fees?${params}`,{signal:controller.signal});
        if(!response.ok)throw new Error('稅費參數不正確或資料暫時無法取得');
        const data=await response.json();if(current!==version||!isAlive())return;
        latest=data;refs=data.insurance;
        const previous=new Map(rows.map(row=>[row.id,row]));
        rows=M.restoreInsurance(savedItems,refs).map(row=>{
          const old=previous.get(row.id);return old?{...row,selected:old.selected,amount:dirty.has(row.id)?old.amount:row.amount}:row;
        });
        renderTax(data.tax);renderInsurance();ready=true;$('feesStatus').textContent='已載入資料；保險金額仍可依實際報價修改。';
      }catch(error){if(current===version&&isAlive())$('feesStatus').textContent='資料載入未完成，請確認車價、排氣量後按「重新載入稅費與保險」。';}
      finally{root.clearTimeout(timeout);if(current===version)pending=false;}
    }
    function reset(details=null){
      controller?.abort();root.clearTimeout(timer);version++;legacy=!!details&&!Array.isArray(details.insurance_items);taxCustom=details?.annual_tax!=null;taxSaved=taxCustom;
      refs=[];rows=[];savedItems=details?.insurance_items;dirty=new Set(savedItems?.map(item=>item.id)||[]);latest=null;ready=false;pending=false;
      field('displacement_cc').value=details?.displacement_cc??'';field('fuel_type').value=details?.fuel_type||'gasoline';
      field('displacement_cc').readOnly=false;field('fuel_type').dataset.catalog='false';
      $('officialTax').replaceChildren();$('vehicleSpecSource').textContent='自訂車款請填排氣量；純電車可填 0。';
      taxStatus();renderInsurance();sync();
    }
    function details(){
      if(!legacy&&(pending||!ready))throw new Error('請先載入稅費與保險參考資料，再儲存購車事件');
      const result={};
      if(field('displacement_cc').value.trim()){result.displacement_cc=Number(field('displacement_cc').value);result.fuel_type=field('fuel_type').value;}
      if(!legacy){
        if(field('annual_tax').value.trim()==='')throw new Error('查無官方費額，請手動填寫年度稅費合計');
        Object.assign(result,M.insuranceSelection(rows));
      }
      return result;
    }
    for(const name of ['displacement_cc','fuel_type','purchase_price'])field(name).addEventListener('input',()=>{
      ready=false;version++;controller?.abort();root.clearTimeout(timer);timer=root.setTimeout(refresh,250);
    });
    field('annual_tax').addEventListener('input',()=>{taxCustom=true;taxSaved=false;taxStatus();});
    $('restoreOfficialTax').addEventListener('click',()=>{if(latest?.tax.total!=null){taxCustom=false;field('annual_tax').value=latest.tax.total;taxStatus();}});
    $('adoptInsuranceItems').addEventListener('click',()=>{legacy=false;savedItems=undefined;dirty.clear();rows=M.restoreInsurance(undefined,refs);renderInsurance();sync();refresh();});
    $('retryVehicleFees').addEventListener('click',refresh);
    const dialog=$('insuranceDialog'),opener=$('openInsuranceDialog');
    const selectionValid=()=>{try{M.insuranceSelection(rows);return true;}catch(error){setTotal(error.message);return false;}};
    opener.addEventListener('click',()=>{
      if(dialog.open||!refs.length)return;
      dialog.showModal();root.document.body.classList.add('plan-dialog-open');dialog.scrollTop=0;
    });
    $('closeInsuranceDialog').addEventListener('click',()=>{if(selectionValid())dialog.close();});
    // An invalid selection keeps the dialog open so the error stays next to the field.
    dialog.addEventListener('cancel',event=>{if(!selectionValid())event.preventDefault();});
    dialog.addEventListener('close',()=>{root.document.body.classList.remove('plan-dialog-open');if(isAlive())opener.focus();});
    root.addEventListener('pagehide',()=>{version++;controller?.abort();root.clearTimeout(timer);},{once:true});
    return {reset,spec,sync,refresh,details};
  }
  root.VehicleFeesForm={create};
})(globalThis);
