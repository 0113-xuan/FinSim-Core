/* Catalog presets only change price and fuel budget, after an explicit action. */
(() => {
  const select=document.getElementById('vehicleModel');
  const distance=document.getElementById('annualDistance');
  const fuel=document.getElementById('fuelPrice');
  const button=document.getElementById('applyVehiclePreset');
  const status=document.getElementById('catalogStatus');
  const description=document.getElementById('catalogDescription');
  const source=document.getElementById('catalogSource');
  const sourceLink=document.getElementById('catalogSourceLink');
  const sourceDate=document.getElementById('catalogSourceDate');
  let catalog=[],sequence=0,controller,applying=false;
  const selected=()=>catalog.find(item=>item.id===select.value);
  function cancel() {
    sequence++;
    controller?.abort();
    controller=null;
    button.disabled=!selected();
  }
  function describe() {
    const vehicle=selected();
    document.getElementById('vehiclePreview').hidden=!vehicle;
    document.getElementById('distancePresets').disabled=!vehicle;
    document.getElementById('chooseCustomVehicle').hidden=Boolean(vehicle);
    document.getElementById('customVehicleFields').hidden=Boolean(vehicle);
    button.disabled=!vehicle;
    distance.disabled=fuel.disabled=!vehicle;
    source.hidden=!vehicle;
    if(!vehicle) {
      description.textContent='自訂車款：保留目前金額，可自行修改車價與油電預算。';
      return;
    }
    description.textContent=`官方參考車價 ${money(vehicle.price_twd)}；測試油耗 ${vehicle.efficiency_km_l} km/L。保險、維修、停車費另行設定。`;
    document.getElementById('previewPrice').textContent=money(vehicle.price_twd);
    document.getElementById('previewModel').textContent=`${vehicle.brand} ${vehicle.model} ${vehicle.trim}`;
    document.getElementById('previewEfficiency').textContent=`${vehicle.efficiency_km_l} km/L`;
    document.getElementById('previewVersion').textContent=vehicle.source_period;
    document.getElementById('previewChecked').textContent=`核對 ${vehicle.checked_on}，非即時報價`;
    sourceLink.href=vehicle.source_url;
    sourceDate.textContent=`資料版本 ${vehicle.source_period} · 核對 ${vehicle.checked_on} · 非即時報價`;
  }
  form.addEventListener('input',event=>{
    if(applying || event.target.id==='reviewed') return;
    const wasPending=Boolean(controller);
    cancel();
    if(wasPending) status.textContent='資料已修改，本次帶入已取消。';
    if(['vehicleModel','annualDistance','fuelPrice'].includes(event.target.id)) {
      delete select.dataset.appliedId;
      status.textContent='條件已修改，按「帶入車價與油費」更新金額。';
    }
  });
  select.addEventListener('change',()=>{delete select.dataset.appliedId;describe();});
  document.getElementById('distancePresets').addEventListener('change',event=>{
    if(event.target.name!=='distancePreset') return;
    distance.value=event.target.value;
    distance.dispatchEvent(new Event('input',{bubbles:true}));
  });
  distance.addEventListener('input',()=>document.getElementById('distancePresets').querySelectorAll('input').forEach(input=>{input.checked=input.value===distance.value;}));
  document.getElementById('chooseCustomVehicle').addEventListener('click',()=>{
    select.value='';
    select.dispatchEvent(new Event('input',{bubbles:true}));
    select.dispatchEvent(new Event('change',{bubbles:true}));
    document.getElementById('customVehicleName').focus();
    status.textContent='已切換自訂車款';
  });
  button.addEventListener('click',async()=>{
    const vehicle=selected();
    if(!vehicle) return;
    if(!distance.value || !fuel.value || !distance.checkValidity() || !fuel.checkValidity()) {
      status.textContent='請填寫有效的年里程與每公升油價，零也可以。';return;
    }
    if(!form.elements.monthly_fuel_or_energy) {status.textContent='費用欄位尚未載入，請稍後再試。';return;}
    cancel();
    const current=sequence;
    const requestController=new AbortController();controller=requestController;
    const timeout=setTimeout(()=>requestController.abort(),10000);
    button.disabled=true;status.textContent='計算車款油費中…';
    try {
      const response=await fetch('/decisions/vehicle/preset',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({vehicle_id:vehicle.id,annual_distance_km:Number(distance.value),fuel_price_twd_l:Number(fuel.value)})});
      const result=await response.json();
      if(current!==sequence) return;
      if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'請檢查里程與油價。');
      const price=form.elements.purchase_price,energy=form.elements.monthly_fuel_or_energy;
      price.value=result.purchase_price;price.dataset.source='backend_normalized';
      price.dataset.evidence=`${vehicle.brand} ${vehicle.model} ${vehicle.trim} 官方參考售價，版本 ${vehicle.source_period}；核對 ${vehicle.checked_on}`;
      price.parentElement.querySelector('small').textContent='官方資料帶入，可修改';
      energy.value=result.monthly_fuel_or_energy;energy.dataset.source='derived';
      energy.dataset.evidence=`年里程 ${result.annual_distance_km} ÷ 官方測試油耗 ${vehicle.efficiency_km_l} km/L × 油價 ${result.fuel_price_twd_l} ÷ 12`;
      energy.parentElement.querySelector('small').textContent=`年里程 ${num(result.annual_distance_km)} ÷ ${vehicle.efficiency_km_l} km/L × NT$${num(result.fuel_price_twd_l)} ÷ 12`;
      applying=true;
      try {form.dispatchEvent(new Event('input',{bubbles:true}));} finally {applying=false;}
      select.dataset.appliedId=vehicle.id;
      status.textContent=`已帶入車價與每月油費 ${money(result.monthly_fuel_or_energy)}；實際道路油耗可能不同。`;
    } catch(error) {
      if(current===sequence) status.textContent=error.name==='AbortError'?'帶入逾時，請重試或自行輸入金額。':error.message;
    } finally {
      clearTimeout(timeout);
      if(current===sequence) {controller=null;button.disabled=!selected();}
    }
  });
  distance.disabled=fuel.disabled=true;
  const loadController=new AbortController(),loadTimeout=setTimeout(()=>loadController.abort(),10000);
  window.vehicleCatalogReady=fetch('/decisions/vehicle/catalog',{signal:loadController.signal,cache:'no-store'}).then(response=>{
    if(!response.ok) throw new Error('車款清單載入失敗');return response.json();
  }).then(items=>{
    catalog=items;
    for(const item of items) {
      const option=document.createElement('option');option.value=item.id;
      option.textContent=`${item.brand} ${item.model} ${item.trim} · ${money(item.price_twd)}`;
      select.append(option);
    }
    describe();
    status.textContent=`已載入 ${items.length} 款車型`;
    return items;
  }).catch(()=>{description.textContent='車款清單暫時無法載入，仍可自行輸入車價與油電預算。';return [];})
    .finally(()=>clearTimeout(loadTimeout));
})();
