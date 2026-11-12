const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Q=require('../static/qa-model.js');

class Node {
  constructor(tag,text=''){this.tagName=tag;this.children=[];this._text=text;}
  append(...children){this.children.push(...children);}
  set textContent(text){this.children=[];this._text=String(text);}
  get textContent(){return this._text+this.children.map(node=>node.textContent).join('');}
}
const document={createElement:tag=>new Node(tag.toUpperCase()),createTextNode:text=>new Node('#text',text)};

test('question limits cover empty, controls, boundary, remaining count, and Unicode',()=>{
  assert.equal(Q.questionState('  ').valid,false);
  assert.equal(Q.questionState('問'.repeat(200)).valid,true);
  assert.equal(Q.questionState('問'.repeat(201)).valid,false);
  assert.equal(Q.questionState('問\n').valid,false);
  assert.equal(Q.questionState('問\u200b').valid,false);
  assert.equal(Q.questionState('你好😀').length,3);
  assert.deepEqual(Q.questionState('問題'),{question:'問題',length:2,remaining:198,valid:true});
});

test('five examples are fixed and question buttons deduplicate valid text',()=>{
  assert.equal(Q.EXAMPLES.length,5);assert.equal(Q.questions().length,5);
  assert.deepEqual(Q.questions(['問？','問？','',null]),['問？']);
  assert.ok(Q.EXAMPLES.includes('為什麼不能保證報酬？'));
});

test('citations stay plain text, deduplicate by id and preserve source order',()=>{
  assert.deepEqual(Q.citationRows([{id:'a',title:'標題',source:'app/core.py'},{id:'a',title:'重複',source:'x'},
    {id:'b',title:'<script>',source:'<a href=x>'}]),[{id:'a',text:'標題｜app/core.py'},{id:'b',text:'<script>｜<a href=x>'}]);
  assert.deepEqual(Q.citationRows(),[]);
});

test('answer uses shared safe segment renderer and ties each paragraph to evidence',()=>{
  const nodes=Q.answerNodes(document,{answer:[[{text:'<script>alert(1)</script>'},
    {fact:'minimum_cash',value:'<img onerror=x>',label:'最低現金'}]],paragraph_sources:[['cash']],citations:[{id:'cash',title:'現金定義'}]});
  assert.equal(nodes[0].tagName,'P');assert.equal(nodes[0].children[0].tagName,'#text');
  assert.equal(nodes[0].children[1].tagName,'STRONG');assert.equal(nodes[0].children[1].title,'最低現金');
  assert.equal(nodes[0].children[1].textContent,'<img onerror=x>');
  assert.equal(nodes[0].children[2].textContent,'依據：現金定義');
});

test('each fallback explains why AI was not used',()=>{
  for(const reason of ['disabled','provider_error','invalid_output'])assert.match(Q.fallbackNotice(reason),/目前未使用 AI/);
});

test('Q&A timeout and safe DOM path are present',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../static/qa-form.js'),'utf8');
  assert.doesNotMatch(source,/innerHTML|insertAdjacentHTML|outerHTML/);
  assert.match(source,/AbortController/);assert.match(source,/90000/);assert.match(source,/ctx\.perform/);
});

test('the Q&A section is just heading, examples, form and result, and example questions only fill the box',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../static/qa-form.js'),'utf8');
  assert.match(source,/section\.append\(heading,examples,form,result\)/);
  assert.doesNotMatch(source,/qaPrivacy|Google Gemini/);
  const handler=source.slice(source.indexOf("button.addEventListener('click'"),source.indexOf('parent.append(button)'));
  assert.match(handler,/input\.value=question;sync\(\);input\.focus\(\);/);
  assert.doesNotMatch(handler,/send\(\)/);
  assert.equal((source.match(/send\(\)/g)||[]).length,2);  // the definition and the form's submit handler
});
