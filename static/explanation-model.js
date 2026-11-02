(function(root) {
  'use strict';
  const planner = typeof module !== 'undefined' && module.exports ? require('./planner-model.js') : root.PlannerModel;
  const fallbackNotices={
    disabled:'目前未啟用 AI，以下是系統依規則產生的說明。',
    provider_error:'AI 服務暫時無法使用，以下是系統依規則產生的說明。',
    invalid_output:'AI 回覆未通過數字檢查，以下改用系統依規則產生的說明。'
  };
  // Events outside the horizon or of unsupported types were skipped by the simulation request.
  function buildExplanationRequest({prepared, events, months, emergencyTargetMonths, eventSummary}) {
    const supported=['one_time','range','salary_change','vehicle_purchase'];
    const included=events.filter(event=>{
      if(!supported.includes(event.type))return false;
      try{const month=planner.periodToMonth(prepared.startPeriod,event.start_period);return month>=1&&month<=months;}catch(_){return false;}
    });
    return {simulation:prepared.request,start_period:prepared.startPeriod,
      events:included.map(event=>({name:event.name,type:event.type,start_period:event.start_period,summary:eventSummary(event)})),
      vehicles:prepared.converted?.vehicles||[],emergency_target_months:Number(emergencyTargetMonths)};
  }
  // AI text only ever becomes text nodes; numbers are backend facts shown in <strong title="label">.
  function segmentNodes(document, segments) {
    return segments.map(segment=>{
      if(segment.fact==null)return document.createTextNode(String(segment.text??''));
      const strong=document.createElement('strong');
      strong.textContent=String(segment.value);strong.title=String(segment.label);
      return strong;
    });
  }
  function explanationNodes(document, data) {
    const block=(tag,segments)=>{const node=document.createElement(tag);node.append(...segmentNodes(document,segments));return node;};
    const nodes=[];
    const headline=document.createElement('p'),bold=document.createElement('strong');
    bold.append(...segmentNodes(document,data.headline));headline.append(bold);nodes.push(headline);
    for(const paragraph of data.paragraphs)nodes.push(block('p',paragraph));
    for(const [title,items] of [['要注意',data.watch_points],['可以考慮',data.suggestions]]){
      if(!items?.length)continue;
      const heading=document.createElement('h4');heading.textContent=title;
      const list=document.createElement('ul');for(const item of items)list.append(block('li',item));
      nodes.push(heading,list);
    }
    const disclaimer=document.createElement('p'),small=document.createElement('small');
    small.textContent=data.disclaimer;disclaimer.append(small);nodes.push(disclaimer);
    return nodes;
  }
  const fallbackNotice=reason=>fallbackNotices[reason]||'以下是系統依規則產生的說明。';
  const api={buildExplanationRequest,segmentNodes,explanationNodes,fallbackNotice};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ExplanationModel=api;
})(globalThis);
