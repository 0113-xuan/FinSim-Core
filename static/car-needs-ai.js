(function(root) {
  'use strict';
  const allowed={body_types:['sedan','hatchback','suv','mpv'],avoid_body_types:['sedan','hatchback','suv','mpv'],priorities:['space','comfort','energy_cost','maintenance_cost','safety'],purposes:['commute','family','work','leisure','client_transport','elderly_transport'],powertrains:['ice','hev','bev'],ownership_years:[1,3,5]};
  const metadataKeys=['schema_version','provider','is_real_ai','status','revision','candidates','unclear','receipt','expires_at','accepted_ids','rejected_ids'];
  function context(answers) {return Object.fromEntries(Object.keys(allowed).map(key=>[key,structuredClone(answers[key])]));}
  function validateCandidate(candidate,text) {
    if(!candidate||!allowed[candidate.field]?.includes(candidate.value)||!['add','remove','set'].includes(candidate.operation)||((candidate.field==='ownership_years')!==(candidate.operation==='set')))throw new Error('AI 候選欄位或數值無效。');
    if(typeof candidate.evidence!=='string'||!candidate.evidence.trim()||candidate.evidence.length>200||!text.includes(candidate.evidence))throw new Error('AI 原文證據不符合輸入。');
    if(typeof candidate.id!=='string'||!/^c\d{1,2}$/.test(candidate.id)||candidate.source!=='ai_structured'||typeof candidate.label!=='string'||candidate.label.length>150||!(candidate.conflict===null||typeof candidate.conflict==='string'))throw new Error('AI 候選格式無效。');
  }
  function attach(state,result) {
    if(!result||Object.keys(result).some(key=>!metadataKeys.includes(key))||!['candidates','no_match'].includes(result.status)||!Array.isArray(result.accepted_ids)||result.accepted_ids.length||!Array.isArray(result.rejected_ids)||result.rejected_ids.length)throw new Error('AI 回應格式無效。');
    if(!result||result.schema_version!=='2.0'||!['gemini','openai'].includes(result.provider)||result.is_real_ai!==true||result.revision!==state.revision||!Array.isArray(result.candidates)||result.candidates.length>10||!Array.isArray(result.unclear)||result.unclear.length>10||typeof result.receipt!=='string'||result.receipt.length<40||!Number.isFinite(result.expires_at)||result.expires_at*1000<Date.now())throw new Error('AI 回應已失效或版本不同，請重新分析。');
    for(const candidate of result.candidates)validateCandidate(candidate,state.answers.free_text);
    if(new Set(result.candidates.map(c=>c.id)).size!==result.candidates.length)throw new Error('AI 候選編號重複。');
    for(const item of result.unclear)if(!['uncertain','unsupported','injection','missing_information'].includes(item.reason)||typeof item.evidence!=='string'||!item.evidence.trim()||!state.answers.free_text.includes(item.evidence))throw new Error('AI 不確定資訊格式無效。');
    const next=structuredClone(state);
    next.extraction=Object.fromEntries(metadataKeys.map(key=>[key,structuredClone(result[key])]));
    next.extraction.accepted_ids=[];next.extraction.rejected_ids=[];next.extraction.active_revision=state.revision;next.confirmed=false;
    return next;
  }
  function decide(state,id,accept,{resolveConflict=false}={}) {
    const extraction=state.extraction;
    if(extraction?.schema_version!=='2.0'||extraction.active_revision!==state.revision||extraction.expires_at*1000<Date.now())throw new Error('問卷已修改或 AI 候選過期，請重新分析。');
    const candidate=extraction.candidates.find(c=>c.id===id);
    if(!candidate||[...extraction.accepted_ids,...extraction.rejected_ids].includes(id))throw new Error('這項候選已處理或不存在。');
    validateCandidate(candidate,state.answers.free_text);
    if(accept&&candidate.conflict&&!resolveConflict)throw new Error('請明確確認是否取代衝突答案。');
    const next=structuredClone(state),c=candidate;
    if(accept) {
      if(c.operation==='set')next.answers[c.field]=c.value;
      else {
        next.answers[c.field]=next.answers[c.field].filter(v=>v!==c.value);
        if(c.operation==='add') {
          next.answers[c.field].push(c.value);
          const opposite={body_types:'avoid_body_types',avoid_body_types:'body_types'}[c.field];
          if(opposite&&next.answers[opposite].includes(c.value)) {next.answers[opposite]=next.answers[opposite].filter(v=>v!==c.value);next.sources[opposite]='user_confirmed_ai';}
        }
      }
      next.sources[c.field]='user_confirmed_ai';
    }
    next.extraction[accept?'accepted_ids':'rejected_ids'].push(id);
    next.revision++;next.extraction.active_revision=next.revision;next.confirmed=false;
    return next;
  }
  function complete(state) {const e=state.extraction;return e?.schema_version!=='2.0'||(e.expires_at*1000>=Date.now()&&e.active_revision===state.revision&&e.candidates.length===e.accepted_ids.length+e.rejected_ids.length);}
  async function request(payload,{transport=fetch,signal}={}) {
    const response=await transport('/ai/car-needs/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal});
    if(!response.ok)throw new Error(response.status===429?'AI 分析次數較多，請稍後重試或直接使用問卷。':'AI 分析未完成，未修改需求。可以略過 AI，直接使用問卷推薦。');
    return response.json();
  }
  const api={context,attach,decide,complete,request};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.CarNeedsAI=api;
})(typeof globalThis!=='undefined'?globalThis:this);
