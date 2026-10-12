const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const script=fs.readFileSync('static/vehicle-catalog.js','utf8');
const html=fs.readFileSync('static/vehicle.html','utf8');
const fixture={id:'car-a',brand:'Toyota',model:'Corolla Cross',trim:'汽油豪華',price_twd:809000,efficiency_km_l:14.3,source_url:'https://www.toyota.com.tw/showroom/COROLLA_CROSS/',source_period:'2026-10',checked_on:'2026-10-11'};
class Element {
  constructor(){this.dataset={};this.value='';this.events={};this.children=[];this.small={};this.parentElement={querySelector:()=>this.small};}
  addEventListener(type,fn){this.events[type]=fn;}
  append(item){this.children.push(item);}
  checkValidity(){return Number(this.value)>=0;}
  dispatchEvent(event){this.events[event.type]?.({target:this});}
}
async function setup(presetFetch) {
  const elements={};
  const $=id=>elements[id] ||= new Element();
  const form=new Element();form.elements={purchase_price:new Element(),monthly_fuel_or_energy:new Element(),annual_insurance:{value:'20000'}};
  $('annualDistance').value='15000';$('fuelPrice').value='30';
  const calls=[];
  const context={document:{getElementById:$,createElement:()=>new Element()},window:{},form,money:v=>`NT$${v}`,num:v=>String(v),AbortController,Event,setTimeout,clearTimeout,
    fetch:async(url,options)=>{calls.push({url,options});if(url.endsWith('/catalog')) return {ok:true,json:async()=>[fixture]};return presetFetch?.(options) || {ok:true,json:async()=>({purchase_price:809000,monthly_fuel_or_energy:2622.38,annual_distance_km:15000,fuel_price_twd_l:30})};}};
  vm.runInNewContext(script,context);
  await new Promise(setImmediate);
  return {$,form,calls};
}
test('catalog select and explicit preset preserve unrelated budgets',async()=>{
  const {$,form,calls}=await setup();
  assert.equal($('vehicleModel').children.length,1);
  $('vehicleModel').value=fixture.id;$('vehicleModel').events.change();
  assert.equal($('chooseCustomVehicle').hidden,true);
  assert.equal($('customVehicleFields').hidden,true);
  assert.equal($('vehiclePreview').hidden,false);
  assert.equal($('previewPrice').textContent,'NT$809000');
  assert.equal($('previewEfficiency').textContent,'14.3 km/L');
  assert.equal(form.elements.purchase_price.value,'');
  assert.equal($('applyVehiclePreset').disabled,false);
  await $('applyVehiclePreset').events.click();
  assert.equal(form.elements.purchase_price.value,809000);
  assert.equal(form.elements.monthly_fuel_or_energy.value,2622.38);
  assert.equal(form.elements.monthly_fuel_or_energy.dataset.source,'derived');
  assert.equal(form.elements.annual_insurance.value,'20000');
  assert.equal($('vehicleModel').dataset.appliedId,fixture.id);
  assert.equal(JSON.parse(calls[1].options.body).annual_distance_km,15000);
  $('vehicleModel').value='';form.events.input({target:$('vehicleModel')});$('vehicleModel').events.change();
  assert.equal($('vehicleModel').dataset.appliedId,undefined);
  assert.equal(form.elements.purchase_price.value,809000);
  assert.equal($('annualDistance').disabled,true);
  assert.equal($('chooseCustomVehicle').hidden,false);
  assert.equal($('customVehicleFields').hidden,false);
  assert.equal($('vehiclePreview').hidden,true);
});
test('changed input cancels stale preset and never overwrites user values',async()=>{
  let finish;
  const {$,form}=await setup(()=>new Promise(resolve=>{finish=resolve;}));
  $('vehicleModel').value=fixture.id;$('vehicleModel').events.change();
  const pending=$('applyVehiclePreset').events.click();
  form.events.input({target:$('annualDistance')});
  form.elements.purchase_price.value=700000;
  finish({ok:true,json:async()=>({purchase_price:809000,monthly_fuel_or_energy:3000})});
  await pending;
  assert.equal(form.elements.purchase_price.value,700000);
  assert.equal($('vehicleModel').dataset.appliedId,undefined);
  assert.equal($('applyVehiclePreset').disabled,false);
});
test('catalog errors leave manual entry available and DOM targets exist',async()=>{
  assert.doesNotThrow(()=>new vm.Script(script));
  for(const match of script.matchAll(/getElementById\('([^']+)'\)/g)) assert.ok(html.includes(`id="${match[1]}"`));
  const {$}=await setup(async()=>({ok:false,json:async()=>({detail:'測試失敗'})}));
  $('vehicleModel').value=fixture.id;$('vehicleModel').events.change();
  await $('applyVehiclePreset').events.click();
  assert.equal($('catalogStatus').textContent,'測試失敗');
  assert.equal($('applyVehiclePreset').disabled,false);
});

test('external chart loading cannot block catalog scripts',()=>{
  assert.match(html,/<script async src="https:\/\/cdn\.jsdelivr\.net\/npm\/chart\.js/);
  assert.doesNotMatch(html,/<script defer src="https:\/\/cdn\.jsdelivr\.net\/npm\/chart\.js/);
  assert.match(script,/cache:'no-store'/);
});
