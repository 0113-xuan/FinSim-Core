(function(root){
  'use strict';
  const taxNote='官方統計為稅前金額，實領約少 5–10%，請依實際情況調整。';
  const publicLoanNote=occupation=>occupation==='public_sector'?'軍公教可向銀行詢問專案車貸利率。':'';
  const initialOccupation=(profile,details)=>details===undefined?profile?.occupation||'':details?.occupation||'';
  function chooseOccupation(state,occupation){return {...state,occupation,reference:null};}
  function receiveReference(state,reference){
    return reference?.occupation===state.occupation?{...state,reference}:{...state};
  }
  function canApply(reference){
    return reference?.available===true&&typeof reference.average_regular_salary==='number'&&Number.isFinite(reference.average_regular_salary)&&reference.average_regular_salary>=0;
  }
  function applyReference(state){
    if(!canApply(state.reference)||state.reference.occupation!==state.occupation)throw new Error('目前沒有可帶入的薪資參考，請自行填寫新實領月薪。');
    return {...state,new_salary:String(state.reference.average_regular_salary)};
  }
  function referenceText(reference){
    if(!reference?.available)return reference?.note||'選擇行業後可查看官方薪資參考。';
    const salary=Number(reference.average_regular_salary).toLocaleString('zh-TW');
    return `同行業平均經常性薪資 NT$${salary}（主計總處，${reference.source.period_label}）`;
  }
  function occupationOptions(items,selected=''){
    const options=[{value:'',label:'未選擇（選填）'},...items.map(item=>({value:item.id,label:item.name}))];
    if(selected&&!items.some(item=>item.id===selected))options.push({value:selected,label:`${selected}（先前儲存，請重新選擇）`});
    return options;
  }
  const api={taxNote,publicLoanNote,initialOccupation,chooseOccupation,receiveReference,canApply,applyReference,referenceText,occupationOptions};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OccupationModel=api;
})(globalThis);
