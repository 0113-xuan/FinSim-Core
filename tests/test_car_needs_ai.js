const test=require('node:test');
const assert=require('node:assert/strict');
const model=require('../static/car-needs-state');
const ai=require('../static/car-needs-ai');
const cases=require('./fixtures/car_needs_p3_cases.json');

function state(text=cases[0].text) {
  let s=model.createState();
  for(const [k,v] of Object.entries({budget_max:2000000,purposes:['commute'],usual_passengers:3,ownership_years:5,free_text:text}))s=model.update(s,k,v);
  return s;
}
function metadata(s,fixture=cases[0]) {
  return {schema_version:'2.0',provider:'gemini',is_real_ai:true,status:fixture.expected.candidates.length?'candidates':'no_match',revision:s.revision,
    candidates:fixture.expected.candidates.map((c,i)=>({...c,id:`c${i}`,label:`條件 ${i}`,conflict:null,source:'ai_structured'})),
    unclear:fixture.expected.unclear,receipt:'signed-receipt-fixture'.repeat(3),expires_at:Math.floor(Date.now()/1000)+1800,accepted_ids:[],rejected_ids:[]};
}
for(const fixture of cases)test(`P3 annotated frontend contract ${fixture.id}`,()=>{
  const s=state(fixture.text),next=ai.attach(s,metadata(s,fixture));
  assert.deepEqual(s.answers,next.answers);
  for(const c of next.extraction.candidates)assert.ok(fixture.text.includes(c.evidence));
});
test('accept/reject is required; real candidates do not use Mock regex',()=>{
  let s=state();s=ai.attach(s,metadata(s));
  assert.equal(ai.complete(s),false);assert.throws(()=>model.confirm(s));
  s=ai.decide(s,'c0',true);s=ai.decide(s,'c1',false);
  assert.deepEqual(s.answers.avoid_body_types,['suv']);
  assert.equal(s.answers.purposes.includes('elderly_transport'),false);
  s=model.confirm(s);const payload=model.serialize(s);
  assert.equal(payload.schema_version,'1.1');assert.equal(payload.status,'confirmed');
  assert.equal(payload.extraction.active_revision,undefined);
  assert.throws(()=>ai.decide(s,'c0',false));
});
test('negative comfort removes preference only after explicit conflict confirmation',()=>{
  let s=state(cases[1].text);s.answers.priorities=['comfort'];
  const m=metadata(s,cases[1]);m.candidates[0].conflict='取代原答案';s=ai.attach(s,m);
  assert.throws(()=>ai.decide(s,'c0',true));
  s=ai.decide(s,'c0',true,{resolveConflict:true});assert.deepEqual(s.answers.priorities,[]);
});
test('opposite body preference is removed on explicit acceptance',()=>{
  let s=state();s.answers.body_types=['suv'];const m=metadata(s);m.candidates[0].conflict='衝突';
  s=ai.decide(ai.attach(s,m),'c0',true,{resolveConflict:true});
  assert.deepEqual(s.answers.body_types,[]);assert.deepEqual(s.answers.avoid_body_types,['suv']);
});
test('manual edits invalidate receipt and preserve manual fallback',()=>{
  let s=state();s=ai.decide(ai.attach(s,metadata(s)),'c0',true);
  s=model.update(s,'budget_max',1000000);
  assert.equal(s.extraction,null);assert.equal(s.sources.avoid_body_types,'user_provided');
  assert.equal(model.serialize(model.confirm(s)).schema_version,'1.0');
});
test('stale, expired, unknown, fabricated and unexpected candidates fail closed',()=>{
  const s=state();
  for(const change of [m=>m.revision++,m=>m.expires_at=1,m=>m.candidates[0].field='salary',m=>m.candidates[0].evidence='invented',m=>m.secret='unexpected']) {
    const m=metadata(s);change(m);assert.throws(()=>ai.attach(s,m));
  }
  const next=ai.attach(s,metadata(s));next.extraction.expires_at=1;
  assert.equal(ai.complete(next),false);assert.throws(()=>model.confirm(next));
  next.confirmed=true;assert.equal(model.serialize(next).recommendation_handoff.status,'awaiting_confirmation');
});
test('AI context has no financial or personal background data',()=>{
  const s=state();s.answers.salary=100000;s.answers.occupation='sales';
  assert.deepEqual(Object.keys(ai.context(s.answers)).sort(),['avoid_body_types','body_types','ownership_years','powertrains','priorities','purposes']);
});
test('provider request failures preserve original answers',async()=>{
  const s=state();const before=structuredClone(s);
  await assert.rejects(ai.request({}, {transport:async()=>({ok:false,status:503})}),/未修改/);
  await assert.rejects(ai.request({}, {transport:async()=>({ok:false,status:429})}),/稍後/);
  assert.deepEqual(s,before);
});
