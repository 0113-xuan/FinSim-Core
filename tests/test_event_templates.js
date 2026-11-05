const test=require('node:test');
const assert=require('node:assert/strict');
const T=require('../static/event-templates.js');

test('event template order and supported types match the product catalogue',()=>{
  assert.deepEqual(T.templates.map(({id,name,group,status,eventType})=>[id,name,group,status,eventType]),[
    ['vehicle','購車','life','available','vehicle_purchase'],
    ['job_change','換工作','life','available','salary_change'],
    ['home','買房','life','coming_soon',undefined],
    ['moving','搬家','life','coming_soon',undefined],
    ['marriage','結婚','life','coming_soon',undefined],
    ['child','生小孩','life','coming_soon',undefined],
    ['travel','旅遊','life','coming_soon',undefined],
    ['study','進修','life','coming_soon',undefined],
    ['one_time','一次性收支','custom','available','one_time'],
    ['range','期間每月收支','custom','available','range']
  ]);
  for(const template of T.templates){
    assert.ok(template.description.length>5);assert.ok(template.icon);
    if(template.status==='coming_soon')assert.equal(Object.hasOwn(template,'eventType'),false);
  }
});
test('available templates include only the four supported database event types',()=>{
  assert.deepEqual(T.availableTemplates().map(t=>t.id),['vehicle','job_change','one_time','range']);
  assert.ok(T.availableTemplates().every(t=>t.status==='available'&&['one_time','range','salary_change','vehicle_purchase'].includes(t.eventType)));
});
test('event types resolve to the same templates shown by the picker',()=>{
  for(const[type,id]of Object.entries({one_time:'one_time',range:'range',salary_change:'job_change',vehicle_purchase:'vehicle'}))
    assert.equal(T.templateForEvent({type}),T.templateById(id));
  assert.equal(T.templateForEvent({type:'home'}),undefined);
  assert.equal(T.templateForEvent(null),undefined);
  assert.equal(T.templateById('missing'),undefined);
});
test('an available add parameter selects its template and preserves other query values',()=>{
  for(const template of T.availableTemplates()){
    const result=T.resolveAddParameter(`?id=plan-id&add=${template.id}&view=full`);
    assert.equal(result.template,template);assert.equal(result.search,'?id=plan-id&view=full');
  }
});
for(const [name,search]of [['coming soon','?id=plan&add=home'],['unknown','?id=plan&add=missing'],['absent','?id=plan']]){
  test(`the ${name} add parameter is ignored without an error`,()=>{
    assert.deepEqual(T.resolveAddParameter(search),{template:null,search:'?id=plan'});
  });
}
test('the shared template catalogue cannot be mutated by an individual picker',()=>{
  assert.ok(Object.isFrozen(T.templates));assert.ok(T.templates.every(Object.isFrozen));
  const available=T.availableTemplates();available.pop();assert.equal(T.availableTemplates().length,4);
  assert.deepEqual(T.resolveAddParameter('?add=travel'),{template:null,search:''});
});
test('only custom income and expense templates ask the user for an event name',()=>{
  assert.deepEqual(T.availableTemplates().filter(T.asksForName).map(t=>t.id),['one_time','range']);
  assert.equal(T.asksForName(undefined),false);
});

test('the picker shows only usable templates and mentions planned ones in one line',()=>{
  const node=tag=>({tag,children:[],attrs:{},textContent:'',className:'',dataset:{},classList:{add(){}},
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},
    setAttribute(key,value){this.attrs[key]=value;},addEventListener(){},querySelectorAll(){return [];}});
  globalThis.EventTemplates=require('../static/event-templates.js');
  globalThis.document={createElement:node,createElementNS:(ns,tag)=>node(tag)};
  require('../static/event-picker.js');
  const walk=(item,out=[])=>{out.push(item);for(const child of item.children||[])walk(child,out);return out;};
  const container=node('div');
  globalThis.EventPicker.render(container,{});
  const all=walk(container);
  assert.deepEqual(all.filter(n=>n.tag==='button').map(n=>n.dataset.templateId),['vehicle','job_change','one_time','range']);
  assert.ok(all.every(n=>n.textContent!=='即將推出'));
  const upcoming=all.filter(n=>n.className==='template-upcoming');
  assert.equal(upcoming.length,1);
  assert.equal(upcoming[0].textContent,'之後會加入：買房、搬家、結婚、生小孩、旅遊、進修。');
  const locked=node('div');
  globalThis.EventPicker.render(locked,{selected:'vehicle',locked:true});
  assert.equal(walk(locked).filter(n=>n.className==='template-upcoming').length,0);
  delete globalThis.EventTemplates;delete globalThis.document;delete globalThis.EventPicker;
});
