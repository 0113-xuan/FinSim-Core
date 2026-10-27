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

function renderFixture(overrides={}) {
  class Element {
    constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
    append(...items){this.children.push(...items);}
    replaceChildren(){this.children=[];}
  }
  const container=new Element('section');container.ownerDocument={createElement:tag=>new Element(tag)};
  const vehicle={brand:'Fixture',model:'Test',trim:'Test',body_type:'sedan',powertrain:'ice',seats:5,price_twd:100,
    checked_on:'2026-10-26',model_year_note:'年式未確認',efficiency:10,efficiency_unit:'km/L',limitations:[],
    sources:{price:'https://example.test/price',seats:'https://example.test/seats'},
    source_types:{price:'official',seats:'third_party'},verification:{price:'verified',seats:'indexed_only'},
    verification_notes:{seats:'座位僅第三方索引佐證'},...overrides};
  const data={ranked:[{rank:1,vehicle,five_year_cash_outflow:100,costs:{monthly_vehicle_outflow:10,one_time_payment:100,loan_payments_total:0,items:[]},affordability:null,preferences:[],ranking_reason:'cash',energy_formula:'fixture'}],incomplete:[],excluded:[],missing_inputs:[],assumptions:[],limitations:[],purchase_period:'2026-11'};
  const flatten=node=>[node,...node.children.flatMap(flatten)];
  return {container,data,flatten};
}

test('seat sources distinguish verified official facts from third-party index evidence',()=>{
  const {container,data,flatten}=renderFixture();api.render(container,data);
  const nodes=flatten(container),links=nodes.filter(n=>n.tag==='a');
  assert.ok(links.some(n=>n.textContent==='座位數 · 第三方資料 · 僅索引佐證，未完成現行頁面核對'));
  assert.ok(links.some(n=>n.textContent==='價格 · 品牌官方 · 已核對'));
  assert.ok(nodes.some(n=>n.textContent==='座位僅第三方索引佐證'));
  assert.ok(links.every(n=>n.target==='_blank'&&n.rel==='noopener noreferrer'));
});

test('old optional provenance metadata remains renderable',()=>{
  const {container,data}=renderFixture({source_types:undefined,verification:undefined,verification_notes:undefined});
  assert.doesNotThrow(()=>api.render(container,data));
});

test('missing seats in incomplete entries are not rendered as five',()=>{
  const {container,data,flatten}=renderFixture({seats:null});
  data.incomplete=[{vehicle:data.ranked[0].vehicle,reasons:['座位數未知']}];data.ranked=[];
  api.render(container,data);
  assert.ok(flatten(container).some(n=>n.textContent.includes('未知 人：座位數未知')));
});
