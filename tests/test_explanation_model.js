const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const E=require('../static/explanation-model.js');

class Node {
  constructor(tag,text){this.tagName=tag;this.children=[];this.attributes={};this.title='';this._text=text??'';}
  append(...nodes){this.children.push(...nodes);}
  set textContent(value){this.children=[];this._text=String(value);}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
}
const document={createElement:tag=>new Node(tag.toUpperCase()),createTextNode:text=>new Node('#text',text)};
const elements=node=>[node,...node.children.flatMap(elements)].filter(child=>child.tagName!=='#text');

test('fact segments become strong elements titled with their label',()=>{
  const [before,strong,after]=E.segmentNodes(document,[{text:'最低現金會降到 '},{fact:'minimum_cash',value:'NT$751,822',label:'最低現金'},{text:'。'}]);
  assert.equal(before.tagName,'#text');assert.equal(before.textContent,'最低現金會降到 ');
  assert.equal(strong.tagName,'STRONG');assert.equal(strong.textContent,'NT$751,822');assert.equal(strong.title,'最低現金');
  assert.equal(after.textContent,'。');
});

test('text segments containing markup stay plain text',()=>{
  const nodes=E.segmentNodes(document,[{text:'<script>alert(1)</script>'},{fact:'x',value:'<img src=x onerror=alert(1)>',label:'<b>'}]);
  assert.equal(nodes[0].tagName,'#text');assert.equal(nodes[0].textContent,'<script>alert(1)</script>');
  assert.equal(nodes[1].children.length,0);assert.equal(nodes[1].textContent,'<img src=x onerror=alert(1)>');
  const page=E.explanationNodes(document,{headline:[{text:'<script>x</script>'}],paragraphs:[[{text:'<script>y</script>'}]],watch_points:[],suggestions:[],disclaimer:'d'});
  assert.ok(page.flatMap(elements).every(node=>node.tagName!=='SCRIPT'));
});

test('explanation renders headline, paragraphs, watch points, suggestions, then disclaimer',()=>{
  const nodes=E.explanationNodes(document,{headline:[{text:'標題'}],paragraphs:[[{text:'第一段'}],[{text:'第二段'}]],
    watch_points:[[{text:'注意'}]],suggestions:[[{text:'建議'}]],disclaimer:'這是模擬結果，不是財務建議。'});
  assert.deepEqual(nodes.map(node=>node.tagName),['P','P','P','H4','UL','H4','UL','P']);
  assert.equal(nodes[0].children[0].tagName,'STRONG');
  assert.deepEqual([nodes[3].textContent,nodes[5].textContent],['要注意','可以在計畫裡試試']);
  assert.equal(nodes.at(-1).textContent,'這是模擬結果，不是財務建議。');
  const empty=E.explanationNodes(document,{headline:[],paragraphs:[[{text:'段落'}]],watch_points:[],suggestions:[],disclaimer:'d'});
  assert.ok(!empty.some(node=>node.tagName==='H4'));
});

test('request reuses the prepared simulation and only events inside the horizon',()=>{
  const prepared={request:{profile:{salary:1},months:60,events:[{type:'one_time',month:5}]},startPeriod:'2026-11',converted:{vehicles:[{name:'買車'}]}};
  const events=[{name:'出國',type:'one_time',start_period:'2027-03',amount:-80000},
    {name:'太早',type:'one_time',start_period:'2026-01',amount:1},{name:'太晚',type:'one_time',start_period:'2040-01',amount:1},
    {name:'未知',type:'other',start_period:'2027-03'}];
  const request=E.buildExplanationRequest({prepared,events,months:60,emergencyTargetMonths:'6',eventSummary:event=>`摘要${event.name}`});
  assert.equal(request.simulation,prepared.request);assert.equal(request.start_period,'2026-11');
  assert.deepEqual(request.events,[{name:'出國',type:'one_time',start_period:'2027-03',summary:'摘要出國'}]);
  assert.deepEqual(request.vehicles,[{name:'買車'}]);assert.equal(request.emergency_target_months,6);
  assert.deepEqual(E.buildExplanationRequest({prepared:{...prepared,converted:null},events:[],months:60,emergencyTargetMonths:3,eventSummary:String}).vehicles,[]);
});

test('template notices explain each fallback reason',()=>{
  assert.match(E.fallbackNotice('disabled'),/目前未啟用 AI/);
  assert.match(E.fallbackNotice('provider_error'),/暫時無法使用/);
  assert.match(E.fallbackNotice('invalid_output'),/未通過/);
});

test('plan page renders AI text without innerHTML and discloses what is sent',()=>{
  const read=file=>fs.readFileSync(path.join(__dirname,'../static',file),'utf8');
  for(const file of ['explanation-model.js','plan-page.js'])assert.doesNotMatch(read(file),/innerHTML|insertAdjacentHTML|outerHTML/);
  const html=read('plan.html');
  assert.match(html,/用白話解釋結果/);assert.match(html,/（系統範本）/);
  assert.match(html,/傳給 Google Gemini 產生說明/);
  assert.ok(html.indexOf('/explanation-model.js')<html.indexOf('/plan-page.js'));
});
