(function(root) {
  'use strict';
  const choices={
    occupation:{student:'學生',employee:'上班族',sales:'業務／服務業',self_employed:'自營工作者',other:'其他'},
    purposes:{commute:'日常通勤',family:'家庭接送',work:'工作用車',leisure:'休閒出遊',client_transport:'接送客戶',elderly_transport:'接送長輩'},
    body_types:{sedan:'轎車',hatchback:'掀背車',suv:'SUV／休旅車',mpv:'多人座車'},
    priorities:{space:'乘坐與載物空間',comfort:'乘坐舒適',energy_cost:'節省油電費',maintenance_cost:'保養費較低',safety:'安全配備'},
    powertrains:{ice:'汽油',hev:'油電',bev:'純電'},
    payment_method:{cash:'現金一次付清',financed:'貸款'},
    charging:{yes:'有',no:'沒有',unknown:'還不確定'},
    parking_type:{own:'自有車位',rented:'月租車位',street:'路邊／臨時停車',none:'尚無停車位置'}
  };
  const numericRules={budget_max:[1,20000000],monthly_distance_km:[0,16666.66],usual_passengers:[1,9],ownership_years:[1,5],monthly_parking:[0,20000000],salary:[0,50000000],balance:[-500000000,5000000000],fixed_expense:[0,20000000],variable_expense:[0,20000000],required_monthly_debt:[0,20000000],down_payment:[0,20000000],annual_interest_rate:[0,98],loan_term_months:[1,600]};
  function initialAnswers() {return {occupation:null,budget_max:null,purposes:[],monthly_distance_km:null,usual_passengers:null,body_types:[],avoid_body_types:[],priorities:[],powertrains:[],parking_type:null,monthly_parking:null,home_charging:null,public_charging:null,ownership_years:null,include_financial:false,salary:null,balance:null,fixed_expense:null,variable_expense:null,required_monthly_debt:null,payment_method:null,down_payment:null,annual_interest_rate:null,loan_term_months:null,free_text:''};}
  function createState() {return {step:0,revision:0,confirmed:false,answers:initialAnswers(),sources:{},extraction:null};}
  function numberOrNull(value) {return value===''||value===null?null:Number(value);}
  function update(state,key,value) {
    if(!Object.hasOwn(state.answers,key)) throw new Error('不支援的問卷欄位');
    const next=structuredClone(state);
    next.answers[key]=value;next.revision++;next.confirmed=false;next.sources[key]='user_provided';
    if(next.extraction?.schema_version==='2.0') {
      next.extraction=null;
      for(const field of Object.keys(next.sources))if(next.sources[field]==='user_confirmed_ai')next.sources[field]='user_provided';
    }
    if(key==='free_text') next.extraction=null;
    return next;
  }
  function hasElectric(a) {return a.powertrains.length===0||a.powertrains.includes('bev');}
  function hasParking(a) {return a.parking_type!==null&&a.parking_type!=='none';}
  function validate(answers,step) {
    const a=answers,errors={};
    const fields=step===0?['budget_max','monthly_distance_km']:step===1?['usual_passengers','ownership_years',...(hasParking(a)?['monthly_parking']:[]),...(a.include_financial?['salary','balance','fixed_expense','variable_expense','required_monthly_debt']:[]),...(a.payment_method==='financed'?['down_payment','annual_interest_rate','loan_term_months']:[])]:[];
    const required=step===0?['budget_max']:step===1?['usual_passengers','ownership_years',...(a.include_financial?['salary','balance','fixed_expense','variable_expense','required_monthly_debt']:[]),...(a.payment_method==='financed'?['down_payment','annual_interest_rate','loan_term_months']:[])]:[];
    for(const key of fields) {
      const v=a[key],range=numericRules[key];
      if(v===null||v===undefined) {if(required.includes(key)) errors[key]='請填寫這個欄位。';continue;}
      if(!Number.isFinite(v)||v<range[0]||v>range[1]) errors[key]=`請輸入 ${range[0].toLocaleString()} 至 ${range[1].toLocaleString()} 之間的數字。`;
      if(['usual_passengers','loan_term_months'].includes(key)&&!Number.isInteger(v)) errors[key]='請輸入整數。';
    }
    if(step===0&&!a.purposes.length) errors.purposes='請至少選擇一個用車目的。';
    if(step===1) {
      if(a.ownership_years!==null&&![1,3,5].includes(a.ownership_years)) errors.ownership_years='請選擇 1、3 或 5 年。';
      if(a.body_types.some(v=>a.avoid_body_types.includes(v))) errors.body_types='同一車型不能同時偏好及排除，請調整選項。';
      if(a.payment_method==='financed'&&a.down_payment!==null&&a.budget_max!==null&&a.down_payment>=a.budget_max) errors.down_payment='頭期款須小於購車預算；全額付款請選現金。';
      if(a.payment_method==='financed'&&Number.isFinite(a.annual_interest_rate)&&Math.abs(a.annual_interest_rate*100-Math.round(a.annual_interest_rate*100))>1e-8) errors.annual_interest_rate='年利率最多填兩位小數。';
    }
    if(step===2&&a.free_text.length>1000) errors.free_text='補充需求請控制在 1,000 字以內。';
    return errors;
  }
  // Local fixtures only: candidates require literal evidence in the user's text.
  function mockExtract(text) {
    const candidates=[];
    const add=(id,field,value,label,evidence)=>candidates.push({id,field,value,label,evidence,source:'mock_literal_fixture'});
    const clauses=text.split(/[，。！？；,;\n]/);
    const evidence=(phrases,negative)=>clauses.filter(clause=>!negative?.test(clause)).flatMap(clause=>phrases.filter(phrase=>clause.includes(phrase)))[0];
    const avoid=evidence(['不喜歡 SUV','不喜歡SUV','不喜歡休旅車','不考慮休旅車']);
    if(avoid) add('avoid-suv','avoid_body_types','suv','排除 SUV／休旅車',avoid);
    const elderly=evidence(['載長輩'],/(?:不|沒|無需|不用)[^，。]*載長輩/);
    if(elderly) add('elderly','purposes','elderly_transport','接送長輩',elderly);
    const negativePreference=/(?:不(?:是)?(?:很|太|特別)?在意|不怎麼在意|沒(?:有)?(?:很)?在意|不需要|不用|無需)/;
    const maintenance=evidence(['保養費低','保養費不要太高'],negativePreference);
    if(maintenance) add('maintenance','priorities','maintenance_cost','保養費較低',maintenance);
    const duration=evidence(['預計持有五年','預計持有5年','打算持有五年','預計持有這台車五年'],/(?:不|沒|無需|不用|可能|也許|考慮)/);
    if(duration) add('five-years','ownership_years',5,'預計持有 5 年',duration);
    const comfort=evidence(['後座舒服','後座舒適'],negativePreference);
    if(comfort) add('comfort','priorities','comfort','乘坐舒適（原文提及後座）',comfort);
    return {provider:'mock',is_real_ai:false,status:candidates.length?'candidates':'no_match',candidates};
  }
  function applyCandidate(state,candidate) {
    const options=mockExtract(state.answers.free_text).candidates;
    const verified=options.find(c=>c.id===candidate.id&&c.field===candidate.field&&c.value===candidate.value);
    if(!verified) throw new Error('模擬候選已失效，請重新預覽。');
    const value=state.answers[verified.field];
    if(verified.field==='avoid_body_types'&&state.answers.body_types.includes(verified.value)) throw new Error('你已偏好 SUV，請先回第二步決定車型偏好。');
    if(verified.field==='ownership_years'&&value!==null&&value!==verified.value) throw new Error('持有年限與第二步不同，請先回第二步確認。');
    const next=update(state,verified.field,Array.isArray(value)?[...new Set([...value,verified.value])]:verified.value);
    next.sources[verified.field]='user_confirmed_mock';return next;
  }
  function serialize(state) {
    const a=state.answers,financed=a.payment_method==='financed';
    const ai=state.extraction?.schema_version==='2.0';
    const extraction=state.extraction?structuredClone(state.extraction):{provider:'mock',is_real_ai:false,status:'not_requested',candidates:[]};
    delete extraction.active_revision;
    const reviewed=!ai||(state.extraction.expires_at*1000>=Date.now()&&state.extraction.active_revision===state.revision&&state.extraction.candidates.length===state.extraction.accepted_ids.length+state.extraction.rejected_ids.length);
    const ready=state.confirmed&&reviewed&&[0,1,2].every(step=>Object.keys(validate(a,step)).length===0);
    return {schema_version:ai?'1.1':'1.0',revision:state.revision,status:ready?'confirmed':'draft',currency:'TWD',
      background:{occupation:a.occupation},constraints:{budget_max:a.budget_max,budget_basis:'vehicle_price',min_seats:a.usual_passengers,avoid_body_types:[...a.avoid_body_types]},
      usage:{purposes:[...a.purposes],monthly_distance_km:a.monthly_distance_km,usual_passengers:a.usual_passengers,ownership_years:a.ownership_years,parking_type:a.parking_type,monthly_parking:hasParking(a)?a.monthly_parking:null,home_charging:hasElectric(a)?a.home_charging:null,public_charging:hasElectric(a)?a.public_charging:null},
      preferences:{body_types:[...a.body_types],priorities:[...a.priorities],powertrains:[...a.powertrains]},
      financial_profile:a.include_financial?{salary:a.salary,balance:a.balance,fixed_expense:a.fixed_expense,variable_expense:a.variable_expense,required_monthly_debt:a.required_monthly_debt,existing_debts:null,raise_rate:null,inflation_rate:null}:null,
      payment:{payment_method:a.payment_method,down_payment:financed?a.down_payment:null,annual_interest_rate:financed&&a.annual_interest_rate!==null?Number((a.annual_interest_rate/100).toFixed(6)):null,loan_term_months:financed?a.loan_term_months:null},
      free_text:a.free_text,extraction,
      field_sources:{...state.sources},recommendation_handoff:{status:ready?'ready_for_p2':'awaiting_confirmation',engine_connected:true}};
  }
  function confirm(state) {
    if(state.extraction?.schema_version==='2.0'&&state.extraction.expires_at*1000<Date.now())throw new Error('AI 候選已過期，請重新分析或略過這次分析。');
    if(state.extraction?.schema_version==='2.0'&&(state.extraction.active_revision!==state.revision||state.extraction.candidates.length!==state.extraction.accepted_ids.length+state.extraction.rejected_ids.length))throw new Error('請先逐項接受或拒絕 AI 候選，再確認需求。');
    if([0,1,2].some(step=>Object.keys(validate(state.answers,step)).length)) throw new Error('請先完成必填資料並修正錯誤，再確認需求。');
    return {...structuredClone(state),confirmed:true};
  }
  // Replace this adapter in P3; the wizard itself never depends on an AI response.
  function createExtractionClient(transport=null) {return {async extract(request) {return transport?transport(request):mockExtract(request.text);}};}
  const api={choices,numericRules,createState,numberOrNull,update,hasElectric,hasParking,validate,mockExtract,applyCandidate,serialize,confirm,createExtractionClient};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;
  else root.CarNeeds=api;
})(typeof globalThis!=='undefined'?globalThis:this);
