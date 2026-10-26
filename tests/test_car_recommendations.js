const test=require('node:test');
const assert=require('node:assert/strict');
const api=require('../static/car-recommendations.js');
const needs=require('../static/car-needs-state.js');

test('currency is readable and unknown never becomes zero',()=>{
  assert.equal(api.money(null),'資料不足');assert.equal(api.money(0),'NT$0');assert.equal(api.money(12345.67),'NT$12,346');
});
test('results keep ranked, incomplete, and excluded separate',()=>{
  const result={ranked:[{rank:1}],incomplete:[{five_year_cash_outflow:null}],excluded:[{reasons:['預算']}]};
  assert.deepEqual(api.groups(result),result);assert.throws(()=>api.groups({ranked:[]}));
});
test('request uses confirmed P1 payload and no AI endpoint',async()=>{
  let state=needs.createState();Object.assign(state.answers,{budget_max:1000000,purposes:['commute'],usual_passengers:3,ownership_years:5});
  const json=needs.serialize(needs.confirm(state));
  let observed;
  await api.request(json,{transport:async(url,init)=>{observed={url,init};return {ok:true,json:async()=>({ranked:[],incomplete:[],excluded:[]})};}});
  assert.equal(observed.url,'/decisions/vehicle/recommendations');assert.deepEqual(JSON.parse(observed.init.body),json);
  assert.equal(observed.init.method,'POST');
});
test('draft cannot request recommendations and server errors remain controlled',async()=>{
  await assert.rejects(api.request({status:'draft'}),/先確認/);
  await assert.rejects(api.request({status:'confirmed'},{transport:async()=>({ok:false,status:422})}),/未通過驗證/);
  await assert.rejects(api.request({status:'confirmed'},{transport:async()=>({ok:true,json:async()=>({})})}),/格式/);
});
test('abort signal is passed to fetch',async()=>{
  const controller=new AbortController();controller.abort();
  await assert.rejects(api.request({status:'confirmed'},{signal:controller.signal,transport:async(_,options)=>{assert.equal(options.signal,controller.signal);throw new DOMException('aborted','AbortError');}}),{name:'AbortError'});
});
test('known P1 mock boundaries remain documented, not silently repaired',()=>{
  assert.equal(needs.mockExtract('不喜歡休旅車但是常載長輩').candidates.some(c=>c.id==='elderly'),false);
  assert.equal(needs.mockExtract('後座舒服不重要').candidates.some(c=>c.id==='comfort'),true);
});
