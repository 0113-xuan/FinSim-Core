(function(root) {
  'use strict';
  const ids=['compulsory','third_party','excess_liability','body_a','body_b','body_c','theft'];
  function insuranceSelection(rows) {
    const selected=rows.filter(row=>row.selected);
    if(!selected.some(row=>row.id==='compulsory'))throw new Error('強制險不可取消');
    if(new Set(selected.map(row=>row.id)).size!==selected.length||selected.some(row=>!ids.includes(row.id)))throw new Error('保險項目不正確');
    if(selected.filter(row=>row.id.startsWith('body_')).length>1)throw new Error('車體險最多只能選一種');
    const insurance_items=selected.map(row=>{
      if(row.amount==null||String(row.amount).trim()===''||!Number.isFinite(Number(row.amount))||Number(row.amount)<0)throw new Error('請填寫有效的保險金額');
      return {id:row.id,amount:Number(row.amount)};
    });
    return {insurance_items,annual_insurance:Math.round(insurance_items.reduce((sum,item)=>sum+item.amount,0)*100)/100};
  }
  function restoreInsurance(items,references) {
    const defaults=['compulsory','third_party','excess_liability','body_b'];
    return references.map(ref=>{
      const saved=items?.find(item=>item.id===ref.id);
      return {id:ref.id,selected:items?saved!=null:defaults.includes(ref.id),amount:saved?.amount??ref.default};
    });
  }
  const money=value=>value==null?'查無官方費額':`NT$${Number(value).toLocaleString('zh-TW',{maximumFractionDigits:2})}`;
  const api={insuranceSelection,restoreInsurance,money};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.VehicleFeesModel=api;
})(globalThis);
