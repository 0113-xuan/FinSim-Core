const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const script=fs.readFileSync('static/vehicle-analysis.js','utf8');
function harness() {
  const nodes={},rows=[];
  const element=()=>({hidden:false,disabled:false,textContent:'',dataset:{},children:[],handlers:{},addEventListener(type,fn){this.handlers[type]=fn;},replaceChildren(){this.children=[];},append(child){this.children.push(child);}});
  const node=id=>nodes[id] ||= element();
  const context={$:node,document:{createElement:element},structuredClone,window:{},revision:0,money:v=>v==null?'不適用':`NT$${v}`,num:v=>v==null?'不適用':String(v),name:k=>k,row:(id,values)=>rows.push({id,values})};
  vm.createContext(context);vm.runInContext(script,context);
  return {context,nodes,rows,node};
}
const input=()=>({profile:{salary:60000},start_period:'2026-09',constraints:{minimum_monthly_surplus:5000},scenario:{target_period:'2026-10',payload:{purchase_price:{value:650000}}}});
test('active financial context is a private copy, without saved A/B UI',()=>{
  const {context,node}=harness();
  const a=input();context.setVehicleAnalysisContext(a);
  a.scenario.payload.purchase_price.value=1;
  assert.equal(vm.runInContext('vehicleContext.scenario.payload.purchase_price.value',context),650000);
  context.invalidateVehicleAnalysis();
  assert.equal(node('runSensitivity').disabled,true);
  assert.doesNotMatch(script,/savedVehicleA|saveVehicleA|compareVehicleAB|comparisonChart/);
});
test('sensitivity renders backend changes and invalid endpoints without inventing numbers',()=>{
  const {context,node,rows}=harness();
  const metrics={ending_cash:1000000,minimum_cash_balance:400000,monthly_surplus:16000};
  const valid=(value,change)=>({value,status:'valid',ending_cash_change:change,metrics:{...metrics,ending_cash:metrics.ending_cash+change},constraints:[]});
  context.renderSensitivity({base_metrics:metrics,factors:[{key:'salary',label:'收入',original_value:60000,impact_span:720000,low:valid(54000,-360000),high:valid(66000,360000)},{key:'purchase_price',label:'車價',original_value:650000,impact_span:null,low:{value:585000,status:'not_applicable',ending_cash_change:null},high:valid(715000,-80000)}]});
  assert.equal(node('sensitivityResult').hidden,false);
  assert.equal(node('sensitivityChart').hidden,true);
  assert.match(node('sensitivityLeader').textContent,/收入/);
  assert.equal(rows[0].values[3],'NT$-360000');
  assert.equal(rows[0].values[5],'+NT$360000');
  assert.equal(rows[1].values[3],'條件不適用');
  assert.equal(node('sensitivityDetails').open,false);
  assert.equal(node('sensitivityStories').children.length,2);
  assert.match(node('sensitivityStories').children[0].children[0].textContent,/每月收入少 NT\$6000/);
});
test('plain-language explanation uses actual balances and explicit failed thresholds',()=>{
  const {context}=harness();
  const story=context.sensitivityStory({ending_cash:800000},{key:'salary',label:'收入',original_value:50000},{value:45000,status:'valid',ending_cash_change:-300000,metrics:{ending_cash:500000,minimum_cash_balance:40000,monthly_surplus:4000},constraints:[{key:'minimum_monthly_surplus',actual:4000,required:5000,passed:false}]});
  assert.equal(story.title,'每月收入少 NT$5000');
  assert.equal(story.effect,'五年後少留下 NT$300000');
  assert.equal(story.ending,'目前 NT$800000 → 調整後 NT$500000');
  assert.match(story.status,/4000.*5000/);
  assert.equal(story.failed,true);
});
test('inflation is an annual rate and invalid changes never get a success verdict',()=>{
  const {context}=harness();
  const invalid=context.sensitivityStory({ending_cash:800000},{key:'purchase_price',original_value:650000},{value:100000,status:'not_applicable',reason:'貸款條件不適用'});
  assert.equal(invalid.ending,'');
  assert.equal(invalid.failed,true);
  const inflation=context.sensitivityStory({ending_cash:800000},{key:'inflation_rate',original_value:.02},{value:.03,status:'valid',ending_cash_change:-10000,metrics:{ending_cash:790000,minimum_cash_balance:500000,monthly_surplus:20000},constraints:[]});
  assert.equal(inflation.title,'支出年漲幅改成 3%');
  assert.equal(inflation.input,'2% → 3%');
  assert.equal(inflation.status,'尚無限制判定');
});
test('invalidating results cancels an in-flight analysis and clears old charts',()=>{
  const {context,node}=harness();
  context.setVehicleAnalysisContext(input());
  context.aborted=false;context.destroyed=0;
  vm.runInContext('analysisController={abort(){aborted=true;}}; sensitivityChart={destroy(){destroyed++;}};',context);
  context.invalidateVehicleAnalysis();
  assert.equal(context.aborted,true);
  assert.equal(context.destroyed,1);
  assert.equal(node('runSensitivity').disabled,true);
  assert.equal(node('sensitivityResult').hidden,true);
});
