(function() {
  'use strict';
  const model=window.CarNeeds,$=id=>document.getElementById(id),form=$('needsForm');
  let state=model.createState(),busy=false;
  const numeric=new Set(Object.keys(model.numericRules));
  const extractionClient=model.createExtractionClient();
  document.querySelectorAll('[data-choice]').forEach(container=>{
    const key=container.dataset.choice,options=model.choices[key==='avoid_body_types'?'body_types':key];
    for(const [value,label] of Object.entries(options)) {
      const wrapper=document.createElement('label'),input=document.createElement('input');
      wrapper.className='choice';input.type='checkbox';input.name=key;input.value=value;
      wrapper.append(input,document.createTextNode(label));container.append(wrapper);
    }
  });
  function setConditional(id,visible) {
    $(id).hidden=!visible;
    $(id).querySelectorAll('input,select').forEach(input=>{input.disabled=!visible;});
  }
  function conditionals() {
    const a=state.answers;
    setConditional('chargingFields',model.hasElectric(a));
    setConditional('parkingBudgetField',model.hasParking(a));
    setConditional('financingFields',a.payment_method==='financed');
    $('financingFields').querySelectorAll('input').forEach(input=>{input.required=a.payment_method==='financed';});
    setConditional('financialFields',a.include_financial);
  }
  function syncInputs() {
    for(const input of form.querySelectorAll('input,select,textarea')) {
      if(!Object.hasOwn(state.answers,input.name)) continue;
      const value=state.answers[input.name];
      if(input.type==='checkbox') input.checked=Array.isArray(value)?value.includes(input.value):value;
      else input.value=value??'';
    }
    $('textCount').textContent=`${state.answers.free_text.length.toLocaleString()} / 1,000 字`;
    conditionals();
  }
  function clearErrors() {
    document.querySelectorAll('[data-error]').forEach(node=>{node.textContent='';});
    form.querySelectorAll('[aria-invalid]').forEach(node=>{
      node.removeAttribute('aria-invalid');
      const descriptions=(node.getAttribute('aria-describedby')||'').split(' ').filter(id=>id&&!id.startsWith('error-'));
      if(descriptions.length) node.setAttribute('aria-describedby',descriptions.join(' '));else node.removeAttribute('aria-describedby');
    });
    $('formError').hidden=true;
  }
  function showErrors(errors) {
    clearErrors();
    if(!Object.keys(errors).length) return false;
    for(const [key,message] of Object.entries(errors)) {
      const error=form.querySelector(`[data-error="${key}"]`);if(error) {error.textContent=message;error.id=`error-${key}`;}
      form.querySelectorAll(`[name="${key}"]`).forEach(input=>{input.setAttribute('aria-invalid','true');if(error) input.setAttribute('aria-describedby',`${input.getAttribute('aria-describedby')||''} ${error.id}`.trim());});
    }
    $('formError').textContent='請檢查標示的欄位，再繼續。';$('formError').hidden=false;
    form.querySelector('[aria-invalid="true"]')?.focus();return true;
  }
  function showStep(step,focus=true) {
    state.step=step;state.confirmed=false;clearErrors();
    form.hidden=false;$('reviewPanel').hidden=true;$('handoffPanel').hidden=true;
    document.querySelectorAll('[data-step]').forEach(panel=>{panel.hidden=Number(panel.dataset.step)!==step;});
    document.querySelectorAll('#stepList li').forEach((node,index)=>{if(index===step) node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');});
    $('stepProgress').value=step+1;$('stepProgress').textContent=`${step+1} / 3`;
    $('stepCaption').textContent=`步驟 ${step+1} / 3`;$('previousStep').hidden=step===0;
    $('nextStep').textContent=step===2?'檢查需求':'下一步';
    syncInputs();if(focus) $(`stepTitle${step}`).focus();
  }
  form.addEventListener('input',event=>{
    const input=event.target,key=input.name;
    if(!Object.hasOwn(state.answers,key)) return;
    let value;
    if(Array.isArray(state.answers[key])) value=Array.from(form.querySelectorAll(`[name="${key}"]:checked`)).map(item=>item.value);
    else if(input.type==='checkbox') value=input.checked;
    else if(numeric.has(key)) value=model.numberOrNull(input.value);
    else value=input.value||null;
    if(key==='free_text') value=input.value;
    const invalidatedAI=state.extraction?.schema_version==='2.0';
    state=model.update(state,key,value);clearErrors();conditionals();
    if(invalidatedAI) {$('aiCandidates').replaceChildren();$('aiUnclear').replaceChildren();$('aiStatus').textContent='問卷已修改，舊 AI 候選已失效；可重新分析或直接檢查需求。';}
    if(key==='free_text') {$('textCount').textContent=`${value.length.toLocaleString()} / 1,000 字`;$('extractionCandidates').replaceChildren();$('extractionStatus').textContent='';}
  });
  form.addEventListener('submit',event=>{
    event.preventDefault();
    if(busy)return;
    if(showErrors(model.validate(state.answers,state.step))) return;
    if(state.step<2) showStep(state.step+1);else review();
  });
  $('previousStep').addEventListener('click',()=>showStep(Math.max(0,state.step-1)));
  const ai=window.CarNeedsAI;
  const skipAI=document.createElement('button');skipAI.type='button';skipAI.textContent='略過這次 AI 分析';skipAI.hidden=true;
  $('aiStatus').after(skipAI);
  skipAI.addEventListener('click',()=>{
    state=model.update(state,'free_text',state.answers.free_text);
    $('aiCandidates').replaceChildren();$('aiUnclear').replaceChildren();skipAI.hidden=true;
    $('aiStatus').textContent='已略過 AI 分析；已接受的條件保留為手動答案，可返回修改。';
  });
  function renderAI() {
    const e=state.extraction;
    $('aiCandidates').replaceChildren();$('aiUnclear').replaceChildren();
    if(e?.schema_version!=='2.0')return;
    skipAI.hidden=false;
    for(const c of e.candidates) {
      const li=document.createElement('li'),title=document.createElement('strong'),evidence=document.createElement('p'),conflict=document.createElement('p'),actions=document.createElement('div');
      title.textContent=c.label;evidence.textContent=`原文：${c.evidence}`;
      if(c.conflict)conflict.textContent=c.conflict;
      const accepted=e.accepted_ids.includes(c.id),rejected=e.rejected_ids.includes(c.id);
      if(accepted||rejected)actions.textContent=accepted?'已接受':'已拒絕';
      else for(const [accept,label] of [[true,c.conflict?'接受並取代衝突答案':'接受'],[false,'拒絕']]) {
        const button=document.createElement('button');button.type='button';button.textContent=label;button.setAttribute('aria-label',`${label}：${c.label}`);
        button.addEventListener('click',()=>{try{state=ai.decide(state,c.id,accept,{resolveConflict:!!c.conflict});renderAI();}catch(error){$('aiStatus').textContent=error.message;}});actions.append(button);
      }
      li.append(title,evidence,conflict,actions);$('aiCandidates').append(li);
    }
    if(e.unclear.length) {
      const title=document.createElement('h4');title.textContent='尚無法確認，不會套用';$('aiUnclear').append(title);
      const reasons={uncertain:'語意或時間不明確，請補充',unsupported:'目前問卷不支援這項條件，請手動確認',injection:'此段包含指令，未作為需求執行',missing_information:'缺少必要資訊，未自行推測'};
      for(const item of e.unclear) {const p=document.createElement('p');p.textContent=`「${item.evidence}」：${reasons[item.reason]}`;$('aiUnclear').append(p);}
    }
    const processed=e.accepted_ids.length+e.rejected_ids.length;
    $('aiStatus').textContent=`${e.provider==='gemini'?'Gemini':'OpenAI'} 分析完成；${e.candidates.length} 項候選，已處理 ${processed} 項。${e.candidates.length>processed?'請逐項接受或拒絕。':e.candidates.length?'可以檢查需求。':'未找到可直接套用的條件。'}`;
  }
  $('analyzeAI').addEventListener('click',async()=>{
    if(busy)return;
    if(!state.answers.free_text.trim()){$('aiStatus').textContent='請先填寫補充需求，或直接檢查需求。';return;}
    if(state.extraction?.schema_version==='2.0')state=model.update(state,'free_text',state.answers.free_text);
    const revision=state.revision,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),25000);
    busy=true;$('nextStep').disabled=true;$('analyzeAI').disabled=true;$('previewExtraction').disabled=true;$('aiCandidates').replaceChildren();$('aiUnclear').replaceChildren();$('aiStatus').textContent='正在分析補充需求…';
    try {
      const result=await ai.request({schema_version:'2.0',text:state.answers.free_text,revision,related_answers:ai.context(state.answers)},{signal:controller.signal});
      if(revision!==state.revision){$('aiStatus').textContent='問卷已修改，已丟棄舊分析。';return;}
      state=ai.attach(state,result);renderAI();
    } catch(error){if(revision===state.revision)$('aiStatus').textContent=error.name==='AbortError'?'AI 分析逾時，需求仍保留。可重試或直接檢查需求。':error.message;}
    finally {clearTimeout(timer);busy=false;$('nextStep').disabled=false;$('analyzeAI').disabled=false;$('previewExtraction').disabled=false;}
  });
  $('previewExtraction').addEventListener('click',async()=>{
    if(busy) return;
    const text=state.answers.free_text;
    if(!text.trim()) {$('extractionStatus').textContent='先寫下補充需求，或直接檢查需求。';return;}
    if(state.extraction?.schema_version==='2.0') {state=model.update(state,'free_text',text);$('aiCandidates').replaceChildren();$('aiUnclear').replaceChildren();$('aiStatus').textContent='已改用本機示範；不使用上一份 AI 候選。';}
    const revision=state.revision;busy=true;$('previewExtraction').disabled=true;$('analyzeAI').disabled=true;
    try {
      const result=await extractionClient.extract({text,related_answers:{body_types:state.answers.body_types,ownership_years:state.answers.ownership_years},revision});
      if(revision!==state.revision) return;
      state.extraction=result;
      $('extractionStatus').textContent=result.candidates.length?'找到以下模擬候選，請逐項確認。':'這段文字沒有符合示範規則；原文會完整保留，不影響繼續。';
      $('extractionCandidates').replaceChildren();
      for(const candidate of result.candidates) {
        const li=document.createElement('li'),body=document.createElement('div'),evidence=document.createElement('small'),button=document.createElement('button');
        body.textContent=candidate.label;evidence.textContent=`原文：${candidate.evidence}`;body.append(evidence);
        button.type='button';button.textContent='套用';button.setAttribute('aria-label',`套用：${candidate.label}`);
        button.addEventListener('click',()=>{
          try {state=model.applyCandidate(state,candidate);button.disabled=true;button.textContent='已套用';$('extractionStatus').textContent='已套用這項需求，確認頁會顯示更新後的答案。';}
          catch(error) {$('extractionStatus').textContent=error.message;}
        });li.append(body,button);$('extractionCandidates').append(li);
      }
    } catch { $('extractionStatus').textContent='模擬擷取未完成，文字仍保留，可以直接繼續。'; }
    finally {busy=false;$('previewExtraction').disabled=false;$('analyzeAI').disabled=false;}
  });
  const display=(value,options)=>value===null||value===''?'未提供':Array.isArray(value)?(value.length?value.map(v=>options?.[v]||v).join('、'):'未指定'):options?.[value]||String(value);
  const amount=value=>value===null?'未提供':`NT$${value.toLocaleString('zh-TW',{maximumFractionDigits:2})}`;
  function reviewGroup(title,rows) {
    const section=document.createElement('div'),heading=document.createElement('h3'),list=document.createElement('dl');
    section.className='review-group';heading.textContent=title;
    for(const [label,value] of rows) {const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;list.append(dt,dd);}
    section.append(heading,list);$('reviewGroups').append(section);
  }
  function review() {
    if(!ai.complete(state)){$('aiStatus').textContent='請先逐項接受或拒絕 AI 候選，再檢查需求。';$('analyzeAI').focus();return;}
    for(let step=0;step<3;step++) {const errors=model.validate(state.answers,step);if(Object.keys(errors).length) {showStep(step);showErrors(errors);return;}}
    const a=state.answers,c=model.choices;
    $('reviewGroups').replaceChildren();
    reviewGroup('基本條件',[
      ['職業',display(a.occupation,c.occupation)],['車價預算上限',amount(a.budget_max)],['用車目的',display(a.purposes,c.purposes)],['每月預估里程',a.monthly_distance_km===null?'未提供':`${a.monthly_distance_km.toLocaleString()} 公里`]
    ]);
    reviewGroup('生活與用車',[
      ['主要乘車人數',`${a.usual_passengers} 人（含駕駛）`],['預計持有',`${a.ownership_years} 年`],['偏好車型',display(a.body_types,c.body_types)],['排除車型',display(a.avoid_body_types,c.body_types)],['在意的條件',display(a.priorities,c.priorities)],['考慮的動力',display(a.powertrains,c.powertrains)],
      ['停車方式',display(a.parking_type,c.parking_type)],['每月停車預算',model.hasParking(a)?amount(a.monthly_parking):'未提供'],
      ['住家充電',model.hasElectric(a)?display(a.home_charging,c.charging):'不適用（未選純電）'],['公共充電',model.hasElectric(a)?display(a.public_charging,c.charging):'不適用（未選純電）']
    ]);
    const payment=[['付款方式',display(a.payment_method,c.payment_method)]];
    if(a.payment_method==='financed') payment.push(['頭期款',amount(a.down_payment)],['貸款年利率',a.annual_interest_rate===null?'未提供':`${a.annual_interest_rate}%`],['貸款期數',a.loan_term_months===null?'未提供':`${a.loan_term_months} 月`]);
    reviewGroup('付款與財務',payment.concat(a.include_financial?[
      ['每月收入',amount(a.salary)],['現金與存款',amount(a.balance)],['每月固定支出',amount(a.fixed_expense)],['每月變動支出',amount(a.variable_expense)],['既有每月必要還款',amount(a.required_monthly_debt)]
    ]:[['財務資料','未加入，後續不能判斷個人負擔能力']]));
    reviewGroup('自由補充', [['原始需求',display(a.free_text)],['擷取狀態',state.extraction?.schema_version==='2.0'?`${state.extraction.provider} AI：接受 ${state.extraction.accepted_ids.length} 項、拒絕 ${state.extraction.rejected_ids.length} 項` : state.extraction?`Mock 模擬（${state.extraction.candidates.length} 項候選，僅套用你確認的項目）`:'未使用 AI 或模擬擷取']]);
    $('reviewNotice').textContent='未填項目保留 null；請再次確認已接受的條件。AI 不負責推薦排名或財務計算。';
    form.hidden=true;$('handoffPanel').hidden=true;$('reviewPanel').hidden=false;$('reviewedNeeds').checked=false;$('reviewError').hidden=true;
    document.querySelectorAll('#stepList li').forEach(node=>node.removeAttribute('aria-current'));
    $('reviewTitle').focus();
  }
  $('editNeeds').addEventListener('click',()=>showStep(2));
  $('reviseNeeds').addEventListener('click',()=>showStep(0));
  $('confirmNeeds').addEventListener('click',()=>{
    if(!$('reviewedNeeds').checked) {$('reviewError').textContent='請先勾選確認需求。';$('reviewError').hidden=false;$('reviewedNeeds').focus();return;}
    try {state=model.confirm(state);}
    catch(error) {$('reviewError').textContent=error.message;$('reviewError').hidden=false;return;}
    $('needsJson').textContent=JSON.stringify(model.serialize(state),null,2);
    $('reviewPanel').hidden=true;$('handoffPanel').hidden=false;$('handoffTitle').focus();
    $('recommendationResults').replaceChildren();
    $('recommendationStatus').textContent='';
    $('runRecommendations').hidden=false;
  });
  let recommendationController=null;
  const recommendationButton=$('runRecommendations');
  recommendationButton.addEventListener('click',async()=>{
    if(recommendationController) return;
    const revision=state.revision,controller=new AbortController();recommendationController=controller;
    const timer=setTimeout(()=>controller.abort(),15000);
    recommendationButton.disabled=true;$('recommendationResults').replaceChildren();$('recommendationStatus').textContent='正在比較車款與財務負擔…';
    try {
      const result=await window.CarRecommendations.request(model.serialize(state),{signal:controller.signal});
      if(!state.confirmed||revision!==state.revision) return;
      window.CarRecommendations.render($('recommendationResults'),result);
      $('recommendationStatus').textContent=`比較完成：${result.ranked.length} 款可排名、${result.incomplete.length} 款資料不足、${result.excluded.length} 款不符合條件。`;
      $('recommendationResults').focus();
    } catch(error) {if(state.confirmed&&revision===state.revision)$('recommendationStatus').textContent=error.name==='AbortError'?'計算逾時，需求仍保留，請再試一次。':error.message;}
    finally {clearTimeout(timer);recommendationController=null;recommendationButton.disabled=false;}
  });
  $('reviseNeeds').addEventListener('click',()=>{recommendationController?.abort();$('recommendationResults').replaceChildren();$('recommendationStatus').textContent='';});
  $('copyJson').addEventListener('click',async()=>{
    try {await navigator.clipboard.writeText($('needsJson').textContent);$('exportStatus').textContent='已複製需求 JSON';}
    catch {$('exportStatus').textContent='無法存取剪貼簿，請使用下載 JSON。';}
  });
  $('downloadJson').addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([$('needsJson').textContent],{type:'application/json;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='finsim-car-needs.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    $('exportStatus').textContent='已產生需求 JSON 下載';
  });
  showStep(0,false);
})();
