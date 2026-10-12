/* Analysis results are backend values; the active request is a private copy. */
let vehicleContext=null, analysisController=null;
let sensitivityChart=null;
let sensitivityResult=null;
const difference = v => v == null ? '不適用' : v === 0 ? '無變化' : `${v>0?'+':''}${money(v)}`;
function updateAnalysisControls() {
  const busy=Boolean(analysisController);
  $('runSensitivity').disabled=!vehicleContext || busy;
  for(const id of ['runWhatIf','whatIfField','whatIfDirection','whatIfAmount']) $(id).disabled=!vehicleContext || busy;
}
function invalidateVehicleAnalysis() {
  vehicleContext=null;
  if(analysisController) { analysisController.abort(); analysisController=null; }
  for(const id of ['sensitivityResult','whatIfResult']) $(id).hidden=true;
  $('sensitivityStatus').textContent=''; $('whatIfStatus').textContent='';
  sensitivityResult=null;
  if(sensitivityChart) {sensitivityChart.destroy();sensitivityChart=null;}
  updateAnalysisControls();
}
function setVehicleAnalysisContext(request) {vehicleContext=structuredClone(request); updateAnalysisControls();}
async function analysisRequest(url, payload, statusId, renderResult) {
  if(analysisController || !vehicleContext) return;
  const controller=new AbortController(), stamp=revision;
  analysisController=controller; updateAnalysisControls(); $(statusId).textContent='計算中…';
  const timeout=setTimeout(()=>controller.abort(),30000);
  try {
    const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
    const result=await response.json();
    if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'請檢查購車與財務條件。');
    if(stamp!==revision) return;
    renderResult(result); $(statusId).textContent='完成';
  } catch(error) {
    if(stamp===revision) $(statusId).textContent=error.name==='AbortError'?'計算逾時，請再試一次。':error.message;
  } finally {
    clearTimeout(timeout);
    if(analysisController===controller) {analysisController=null;updateAnalysisControls();}
  }
}
function renderSensitivity(result) {
  sensitivityResult=result;
  $('sensitivityRows').replaceChildren();
  const displayValue=(factor,value)=>factor.key==='inflation_rate'?`${num(value*100)}%`:money(value);
  for(const f of result.factors) row('sensitivityRows',[f.label,displayValue(f,f.original_value),displayValue(f,f.low.value),f.low.status==='valid'?difference(f.low.ending_cash_change):'條件不適用',displayValue(f,f.high.value),f.high.status==='valid'?difference(f.high.ending_cash_change):'條件不適用']);
  const ranked=result.factors.filter(f=>f.impact_span != null);
  $('sensitivityLeader').textContent=ranked.length?`這次測試中，${ranked[0].label}的變化對五年後現金影響最大。`:'沒有完整可比較的變動範圍。';
  const select=$('sensitivityFactor');select.replaceChildren();
  result.factors.forEach(f=>{const option=document.createElement('option');option.value=f.key;option.textContent=f.label;select.append(option);});
  select.value=ranked[0]?.key || result.factors[0]?.key || '';
  renderSensitivityStories();
  $('sensitivityResult').hidden=false;
  $('sensitivityDetails').open=false;
  $('sensitivityChart').hidden=true;
  if(sensitivityChart) {sensitivityChart.destroy();sensitivityChart=null;}
}
function drawSensitivityChart() {
  if(!sensitivityResult) return;
  const ranked=sensitivityResult.factors.filter(f=>f.impact_span != null);
  if(sensitivityChart) sensitivityChart.destroy();
  $('sensitivityChart').hidden=!window.Chart || !ranked.length;
  if(window.Chart && ranked.length) sensitivityChart=new Chart($('sensitivityChart'),{type:'bar',data:{labels:ranked.map(f=>f.label),datasets:[
    {label:'較低值的影響',data:ranked.map(f=>[0,f.low.ending_cash_change]),backgroundColor:'#0284c7'},
    {label:'較高值的影響',data:ranked.map(f=>[0,f.high.ending_cash_change]),backgroundColor:'#d97706'}
  ]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{onClick:()=>{}}},scales:{x:{title:{display:true,text:'五年期末現金變化（NT$）'}}}}});
}
function sensitivityStory(base, factor, variant) {
  const unit=factor.key.startsWith('annual_')?'／年':factor.key==='purchase_price'?'':'／月';
  const inputValue=v=>factor.key==='inflation_rate'?`${num(v*100)}%`:money(v)+unit;
  const change=variant.value-factor.original_value;
  const titles={salary:'每月收入',monthly_fuel_or_energy:'每月油電費',monthly_parking:'每月停車費',annual_maintenance_budget:'每年維護預算',annual_insurance:'每年保險費',purchase_price:'車價'};
  const title=factor.key==='inflation_rate'?`支出年漲幅改成 ${inputValue(variant.value)}`:change===0?`${titles[factor.key] || factor.label}維持不變`:`${titles[factor.key] || factor.label}${change<0?'少':'多'} ${money(Math.abs(change))}`;
  const input=`${inputValue(factor.original_value)} → ${inputValue(variant.value)}`;
  if(variant.status!=='valid') return {title,input,effect:'這個變化無法評估',ending:'',facts:variant.reason || '金額或貸款條件不適用',status:'請調整金額；未產生財務結果',failed:true};
  const delta=variant.ending_cash_change;
  const checks=variant.constraints || [],failed=checks.filter(c=>!c.passed);
  const fmt=c=>c.key==='minimum_emergency_fund_months'?`${num(c.actual)} 個月（設定至少 ${num(c.required)} 個月）`:`${money(c.actual)}（設定至少 ${money(c.required)}）`;
  return {title,input,effect:delta===0?'五年後現金不變':`五年後${delta<0?'少':'多'}留下 ${money(Math.abs(delta))}`,
    ending:`目前 ${money(base.ending_cash)} → 調整後 ${money(variant.metrics.ending_cash)}`,
    facts:`五年內最低現金 ${money(variant.metrics.minimum_cash_balance)}；購車生效月結餘 ${money(variant.metrics.monthly_surplus)}`,
    status:failed.length?`未符合你設定的限制：${failed.map(c=>`${name(c.key)} ${fmt(c)}`).join('；')}`:checks.length?'符合你目前設定的財務限制':'尚無限制判定',failed:Boolean(failed.length)};
}
function appendStory(target, story) {
  const article=document.createElement('article');article.className='what-if-story';
  for(const [tag,text,className] of [['h3',story.title,''],['p',story.input,''],['p',story.effect,'story-effect'],['p',story.ending,''],['p',story.facts,''],['p',story.status,'story-status']]) {
    if(!text) continue;
    const element=document.createElement(tag);element.textContent=text;element.className=className;
    if(className==='story-status') element.dataset.state=story.failed?'failed':'passed';
    article.append(element);
  }
  $(target).append(article);
}
function renderSensitivityStories() {
  $('sensitivityStories').replaceChildren();
  const factor=sensitivityResult?.factors.find(f=>f.key===$('sensitivityFactor').value);
  if(!factor) return;
  for(const direction of ['low','high']) appendStory('sensitivityStories',sensitivityStory(sensitivityResult.base_metrics,factor,factor[direction]));
}
$('runSensitivity').addEventListener('click',()=>analysisRequest('/decisions/vehicle/sensitivity',vehicleContext,'sensitivityStatus',renderSensitivity));
$('sensitivityFactor').addEventListener('change',renderSensitivityStories);
$('sensitivityDetails').addEventListener('toggle',()=>{if($('sensitivityDetails').open) drawSensitivityChart();});
$('whatIfForm').addEventListener('submit',event=>{
  event.preventDefault();
  if(!$('whatIfForm').reportValidity()) return;
  const amount=Number($('whatIfAmount').value);
  if(!Number.isFinite(amount) || amount<0) return;
  $('whatIfResult').hidden=true;
  analysisRequest('/decisions/vehicle/what-if',{request:vehicleContext,field:$('whatIfField').value,change:Number($('whatIfDirection').value)*amount},'whatIfStatus',result=>{
    $('whatIfResult').replaceChildren();appendStory('whatIfResult',sensitivityStory(result.base_metrics,result.factor,result.variant));$('whatIfResult').hidden=false;
  });
});
$('whatIfForm').addEventListener('input',()=>{$('whatIfResult').hidden=true;$('whatIfStatus').textContent='';});
$('whatIfField').addEventListener('change',()=>{
  $('whatIfAmount').value=({salary:5000,monthly_parking:1000,purchase_price:100000})[$('whatIfField').value];
  $('whatIfDirection').value=$('whatIfField').value==='salary'?'-1':'1';
});
$('addDebt').addEventListener('click',()=>{
  const container=document.createElement('div');container.className='debt-row';
  for(const [key,text,type,min,max] of [['name','債務名稱','text',null,null],['payment','每月還款（元）','number',0,20000000],['months','剩餘期數（月）','number',0,1200]]) {
    const label=document.createElement('label'),input=document.createElement('input');label.textContent=text;input.dataset.debt=key;input.type=type;input.required=true;
    if(type==='number') {input.min=min;input.max=max;input.step=key==='months'?'1':'any';} else input.maxLength=80;
    label.append(input);container.append(label);
  }
  const remove=document.createElement('button');remove.type='button';remove.textContent='移除';remove.addEventListener('click',()=>{container.remove();syncDebtMode();});container.append(remove);
  $('debtRows').append(container);syncDebtMode();container.querySelector('input').focus();
});
function syncDebtMode() {
  const hasDetails=Boolean($('debtRows').children.length);
  form.elements.required_monthly_debt.disabled=hasDetails;
  $('debtModeNote').textContent=hasDetails?'依明細扣款，總額不另計':'僅填總額時，五年內持續扣款';
  form.dispatchEvent(new Event('input',{bubbles:true}));
}
updateAnalysisControls();
