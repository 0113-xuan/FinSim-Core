const test = require('node:test');
const assert = require('node:assert/strict');

// A small fake page: enough of the DOM for the create-plan dialog and the real event picker.
let focused = null;
class Node {
  constructor(tag) { Object.assign(this, {tag, children:[], attrs:{}, listeners:{}, dataset:{}, textContent:'', className:'', value:'', hidden:false, disabled:false, scrollTop:0}); this.classList = {add() {}, remove() {}}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  fire(type) { for (const fn of this.listeners[type] || []) fn({preventDefault() {}}); }
  focus() { focused = this; }
  select() {}
  closest() { return null; }
  showModal() { this.open = true; }
  close() { this.open = false; this.fire('close'); }
  all(out = []) { for (const child of this.children) { out.push(child); child.all(out); } return out; }
  querySelectorAll(selector) { return this.all().filter(n => selector === '[data-template-id]' ? n.dataset.templateId !== undefined : n.tag === selector); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
}

globalThis.EventTemplates = require('../static/event-templates.js');
require('../static/event-picker.js');  // sets globalThis.EventPicker

function open() {
  const body = new Node('body');
  globalThis.document = {createElement: tag => new Node(tag), createElementNS: (ns, tag) => new Node(tag), body};
  const created = [], urls = [];
  globalThis.location = {assign: url => urls.push(url)};
  const ctx = {alive:true, busy:false, store:{addPlan: async plan => { created.push(plan); return {id:'p1'}; }}};
  require('../static/shell.js').setupPlanDialog(ctx, {closeDrawer() {}, openDrawer() {}});
  ctx.openPlanDialog(new Node('button'));
  const dialog = body.children[0], form = dialog.children[1];
  const input = dialog.querySelector('input'), title = dialog.children[0];
  const button = text => dialog.querySelectorAll('button').find(b => b.textContent === text);
  const pick = id => dialog.querySelectorAll('button').find(b => b.dataset.templateId === id).fire('click');
  const state = () => ({title:title.textContent, name:input.value, next:button('下一步').disabled, create:button('建立計畫').disabled});
  return {dialog, form, input, button, pick, state, created, urls};
}

test.afterEach(() => { for (const key of ['document', 'location']) delete globalThis[key]; });

test('pick an event first, then the name starts as the event name and creating opens the plan page with it', async () => {
  const d = open();
  assert.deepEqual(d.state(), {title:'這個計畫要安排什麼事件？', name:'', next:true, create:true});
  d.pick('vehicle');
  assert.equal(d.state().next, false);
  d.button('下一步').fire('click');
  assert.deepEqual(d.state(), {title:'建立計畫', name:'購車', next:false, create:false});
  assert.equal(focused, d.input);
  d.button('建立計畫').fire('click');
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(d.created, [{name:'購車', kind:'general'}]);
  assert.deepEqual(d.urls, ['/plan.html?id=p1&add=vehicle']);
});

test('going back to change the event renames only a name the program filled in', () => {
  const auto = open();
  auto.pick('vehicle'); auto.button('下一步').fire('click');
  auto.button('上一步').fire('click'); auto.pick('job_change'); auto.button('下一步').fire('click');
  assert.equal(auto.input.value, '換工作');

  const typed = open();
  typed.pick('vehicle'); typed.button('下一步').fire('click');
  typed.input.value = '我的計畫'; typed.input.fire('input');
  typed.button('上一步').fire('click'); typed.pick('job_change'); typed.button('下一步').fire('click');
  assert.equal(typed.input.value, '我的計畫');
});

test('skipping the event drops a name the program filled in and creates a plan without an event', async () => {
  const d = open();
  d.pick('vehicle'); d.button('下一步').fire('click'); d.button('上一步').fire('click');
  d.button('先不選事件').fire('click');
  assert.deepEqual(d.state(), {title:'建立計畫', name:'', next:true, create:true});
  d.input.value = '存錢計畫'; d.input.fire('input');
  d.button('建立計畫').fire('click');
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(d.urls, ['/plan.html?id=p1']);
  assert.equal(d.created[0].name, '存錢計畫');
});

test('Enter does nothing on the event step and creates the plan on the name step', async () => {
  const d = open();
  d.form.fire('submit');
  assert.equal(d.created.length, 0);
  d.pick('one_time'); d.button('下一步').fire('click');
  assert.equal(d.input.value, '一次性收支');
  d.input.value = '  '; d.input.fire('input');
  d.form.fire('submit');
  assert.equal(d.created.length, 0);         // a blank name is not accepted
  d.input.value = '獎金'; d.input.fire('input');
  d.form.fire('submit');
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(d.urls, ['/plan.html?id=p1&add=one_time']);
});
