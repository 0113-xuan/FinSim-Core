const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../static/location-model.js');
const {createStore}=require('../static/shell.js');
const regions=[{city:'臺中市',districts:['北屯區','西屯區']},{city:'臺北市',districts:['中正區']}];

test('city and district linkage returns copies and clears stale selections',()=>{
  assert.deepEqual(M.districtsForCity(regions,'臺中市'),['北屯區','西屯區']);
  assert.deepEqual(M.districtsForCity(regions,''),[]);
  assert.deepEqual(M.locationValues(regions,'','北屯區'),{city:null,district:null});
  assert.deepEqual(M.locationValues(regions,'臺中市',''),{city:'臺中市',district:null});
  assert.throws(()=>M.locationValues(regions,'臺北市','北屯區'));
  const districts=M.districtsForCity(regions,'臺中市');districts.pop();assert.equal(regions[0].districts.length,2);
});
test('parking display prioritises priced lots and truncates unpriced original text',()=>{
  const lots=[{name:'B',address:'測試地址',monthly_rent_twd:null,fare_description:'計時30元'.repeat(12)},
    {name:'C',monthly_rent_twd:2000},{name:'A',monthly_rent_twd:0}];
  assert.deepEqual(M.sortParkingLots(lots).map(l=>l.name),['A','C','B']);
  assert.match(M.parkingLotText(lots[1]),/NT\$2,000／月/);
  assert.equal(M.parkingLotText(lots[0]).split('｜')[2],Array.from(lots[0].fare_description).slice(0,40).join(''));
  assert.match(M.parkingSummary('北屯區',{count:2,median:null}),/不足 3 間/);
  assert.match(M.parkingSummary('北屯區',{count:5,median:2800}),/中位數 NT\$2,800/);
});
test('only known missing profile location columns trigger the compatibility retry',()=>{
  for(const error of [{code:'42703',message:'column profiles.city does not exist'},
    {code:'PGRST204',message:"Could not find the 'district' column in the schema cache"}])assert.equal(M.missingLocationColumns(error),true);
  for(const error of [{code:'42703',message:'column salary does not exist'},
    {code:'42501',message:'city permission denied'},{code:'PGRST301',message:'invalid JWT'},new Error('network')])assert.equal(M.missingLocationColumns(error),false);
});
function clientWith(results){
  const calls=[];
  return {calls,from(table){
    const call={table,steps:[]};calls.push(call);
    const query={then(resolve,reject){return Promise.resolve(results.shift()).then(resolve,reject);}};
    for(const step of ['select','eq','maybeSingle','upsert','single'])query[step]=(...args)=>{call.steps.push([step,...args]);return query;};
    return query;
  }};
}
const missing={data:null,error:{code:'PGRST204',message:"Could not find the 'city' column in the schema cache"}};
test('legacy profile reads retry without new columns and surface the SQL notice',async()=>{
  const client=clientWith([missing,{data:{user_id:'owner',monthly_income:80000},error:null}]),warnings=[];
  const store=createStore(client,'owner',{onWarning:m=>warnings.push(m)});
  assert.equal((await store.profile()).monthly_income,80000);assert.equal(store.locationSupported,false);
  assert.equal(warnings[0],M.schemaWarning);assert.equal(client.calls.length,2);
  assert.match(client.calls[0].steps.find(s=>s[0]==='select')[1],/city,district/);
  assert.doesNotMatch(client.calls[1].steps.find(s=>s[0]==='select')[1],/city|district/);
  for(const call of client.calls)assert.ok(call.steps.some(s=>s[0]==='eq'&&s[1]==='user_id'&&s[2]==='owner'));
});
test('legacy profile writes preserve finances and owner while retrying without location',async()=>{
  const client=clientWith([missing,{data:{user_id:'owner',monthly_income:90000},error:null}]),warnings=[];
  const values={user_id:'wrong',monthly_income:90000,city:'臺中市',district:'北屯區'};
  const store=createStore(client,'owner',{onWarning:m=>warnings.push(m)});
  assert.equal((await store.saveProfile(values)).monthly_income,90000);
  const body=client.calls[1].steps.find(s=>s[0]==='upsert')[1];
  assert.equal(body.monthly_income,90000);assert.equal(body.user_id,'owner');assert.equal(Object.hasOwn(body,'city'),false);assert.equal(Object.hasOwn(body,'district'),false);
  assert.equal(values.city,'臺中市');assert.equal(warnings.length,1);
});
test('permission and unrelated column failures are not retried or hidden',async()=>{
  const client=clientWith([{data:null,error:{code:'42501',message:'無權限存取'}}]);
  await assert.rejects(()=>createStore(client,'owner').saveProfile({monthly_income:1,city:'臺中市'}),/無權限/);
  assert.equal(client.calls.length,1);
});
