const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('static/vehicle.html','utf8');
const js=fs.readFileSync('static/vehicle.js','utf8');
const css=fs.readFileSync('static/vehicle.css','utf8');
test('vehicle script parses',()=>assert.doesNotThrow(()=>new vm.Script(js)));
test('one chart and explicit confirmation',()=>{
  assert.equal((html.match(/<canvas/g)||[]).length,1);
  assert.match(html,/id="reviewed" required/);
  assert.match(js,/chart.destroy\(\)/);
  assert.match(js,/onClick:\(\)=>\{\}/);
});
test('isolated deterministic API with timeout and stale response guard',()=>{
  assert.match(js,/fetch\('\/decisions\/vehicle'/);
  assert.match(js,/submittedRevision!==revision/);
  assert.match(js,/controller.abort\(\)/);
  assert.doesNotMatch(js,/\/ai\/|\/optimize|\/monte-carlo|\/compare/);
});
test('sources, stress, constraints and mobile table overflow remain visible',()=>{
  for(const id of ['stresses','sources','boundaryChecks','cashRows']) assert.match(html,new RegExp(`id="${id}"`));
  assert.match(css,/overflow:auto/);
  assert.match(css,/@media\(max-width:760px\)/);
  assert.doesNotMatch(html,/FSI|bankruptcy|advisor score/);
});
