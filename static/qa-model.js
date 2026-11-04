(function(root) {
  'use strict';
  const node = typeof module !== 'undefined' && module.exports;
  const explanationModel = () => node ? require('./explanation-model.js') : root.ExplanationModel;
  const MAX_QUESTION_LENGTH = 200;
  const EXAMPLES = Object.freeze([
    '現金不足機率是什麼意思？', '一般情況和較差情況差在哪？', '淨資產是怎麼算的？',
    '這裡的車價和保險資料從哪來？', '為什麼不能保證報酬？'
  ]);
  const notices = {
    disabled:'目前未使用 AI，以下是最相關的說明。AI 尚未啟用。',
    provider_error:'目前未使用 AI，以下是最相關的說明。AI 服務暫時無法使用。',
    invalid_output:'目前未使用 AI，以下是最相關的說明。AI 回答未通過出處或數字檢查。'
  };
  function questionState(value) {
    const text = String(value ?? ''), length = Array.from(text).length;
    return {question:text.trim(), length, remaining:MAX_QUESTION_LENGTH-length,
      valid:!!text.trim() && length <= MAX_QUESTION_LENGTH && !/[\p{Cc}\p{Cf}\p{Cs}]/u.test(text)};
  }
  function questions(items = EXAMPLES) {
    return [...new Set(items.filter(item=>typeof item==='string' && questionState(item).valid))];
  }
  function citationRows(citations = []) {
    const seen = new Set();
    return citations.filter(item=>item && !seen.has(item.id) && seen.add(item.id))
      .map(item=>({id:String(item.id), text:`${String(item.title)}｜${String(item.source)}`}));
  }
  function answerNodes(document, data) {
    const byId = new Map((data.citations || []).map(item=>[item.id,item.title]));
    return (data.answer || []).map((segments,index)=>{
      const paragraph=document.createElement('p');
      paragraph.append(...explanationModel().segmentNodes(document,segments));
      const sources=(data.paragraph_sources?.[index] || []).map(id=>byId.get(id)).filter(Boolean);
      if(sources.length){
        const label=document.createElement('small');label.className='qa-paragraph-source';
        label.textContent=`依據：${sources.join('、')}`;paragraph.append(label);
      }
      return paragraph;
    });
  }
  const fallbackNotice=reason=>notices[reason] || '目前未使用 AI，以下是最相關的說明。';
  const api={MAX_QUESTION_LENGTH,EXAMPLES,questionState,questions,citationRows,answerNodes,fallbackNotice};
  if(node)module.exports=api;else root.QAModel=api;
})(globalThis);
