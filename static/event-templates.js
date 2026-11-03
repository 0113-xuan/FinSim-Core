(function(root) {
  'use strict';
  const templates = Object.freeze([
    {id:'vehicle',name:'購車',description:'選車款與付款方式，系統幫你算車貸、持有成本，並做購車分析。',icon:'vehicle',group:'life',status:'available',eventType:'vehicle_purchase'},
    {id:'job_change',name:'換工作',description:'設定新工作的實領月薪，看看收入改變後的財務走勢。',icon:'job',group:'life',status:'available',eventType:'salary_change'},
    {id:'home',name:'買房',description:'規劃頭期款、房貸與買房後的生活開銷。',icon:'home',group:'life',status:'coming_soon'},
    {id:'moving',name:'搬家',description:'安排搬家費用與新住處的每月開銷。',icon:'moving',group:'life',status:'coming_soon'},
    {id:'marriage',name:'結婚',description:'規劃婚禮與共同生活的財務安排。',icon:'marriage',group:'life',status:'coming_soon'},
    {id:'child',name:'生小孩',description:'預先安排育兒支出與家庭收入的變化。',icon:'child',group:'life',status:'coming_soon'},
    {id:'travel',name:'旅遊',description:'為一趟旅行安排預算與出發時間。',icon:'travel',group:'life',status:'coming_soon'},
    {id:'study',name:'進修',description:'規劃學費與進修期間的生活費。',icon:'study',group:'life',status:'coming_soon'},
    {id:'one_time',name:'一次性收支',description:'加入只發生一次的收入或支出，例如獎金或家電。',icon:'one_time',group:'custom',status:'available',eventType:'one_time'},
    {id:'range',name:'期間每月收支',description:'加入一段期間內，每個月固定發生的收入或支出。',icon:'range',group:'custom',status:'available',eventType:'range'}
  ].map(Object.freeze));
  const availableTemplates=()=>templates.filter(template=>template.status==='available');
  const templateById=id=>templates.find(template=>template.id===id);
  const templateForEvent=event=>availableTemplates().find(template=>template.eventType===event?.type);
  // Life events are named after their template; only custom income/expense rows need a user-written name.
  const asksForName=template=>template?.group==='custom';
  // No location/history access here: the caller applies the returned URL once.
  function resolveAddParameter(search) {
    const params=new URLSearchParams(search),template=templateById(params.get('add'));
    params.delete('add');
    return {template:template?.status==='available'?template:null,search:params.toString()?`?${params}`:''};
  }
  const api={templates,availableTemplates,templateById,templateForEvent,asksForName,resolveAddParameter};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.EventTemplates=api;
})(globalThis);
