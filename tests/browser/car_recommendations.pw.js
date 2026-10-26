async page => {
  const check=(value,message)=>{if(!value)throw new Error(message);};
  const origin=new URL(page.url()).origin,errors=[],aiRequests=[],results=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/ai/'))aiRequests.push(r.url());});
  async function complete({budget=1000000,mileage=1000,exclude=false,finance=false,passengers=3}={}) {
    await page.goto(origin+'/vehicle.html');
    await page.getByRole('link',{name:'幫我選車',exact:true}).click();
    await page.locator('[name="budget_max"]').fill(String(budget));
    if(mileage!==null)await page.locator('[name="monthly_distance_km"]').fill(String(mileage));
    await page.getByRole('checkbox',{name:'日常通勤',exact:true}).press('Space');
    await page.getByRole('button',{name:'下一步',exact:true}).press('Enter');
    await page.locator('[name="usual_passengers"]').fill(String(passengers));
    await page.locator('[name="ownership_years"]').selectOption('5');
    if(exclude)await page.locator('[name="avoid_body_types"][value="suv"]').check();
    await page.locator('[name="parking_type"]').selectOption('own');
    await page.locator('[name="monthly_parking"]').fill('0');
    await page.locator('[name="payment_method"]').selectOption(finance?'financed':'cash');
    if(finance) {
      for(const [name,value] of Object.entries({down_payment:200000,annual_interest_rate:2.5,loan_term_months:84}))await page.locator(`[name="${name}"]`).fill(String(value));
      await page.locator('[name="include_financial"]').check();
      for(const [name,value] of Object.entries({salary:80000,balance:1200000,fixed_expense:12000,variable_expense:10000,required_monthly_debt:0}))await page.locator(`[name="${name}"]`).fill(String(value));
    }
    await page.getByRole('button',{name:'下一步',exact:true}).click();
    await page.locator('[name="free_text"]').fill('希望後座舒適，但不需要系統替我猜金額。');
    await page.getByRole('button',{name:'檢查需求',exact:true}).click();
    await page.locator('#reviewedNeeds').check();
    await page.getByRole('button',{name:'確認需求',exact:true}).click();
    await page.getByRole('button',{name:'查看符合條件車款',exact:true}).click();
    await page.locator('#recommendationStatus').filter({hasText:'比較完成'}).waitFor();
  }
  for(const [mode,width,height,scenario] of [
    ['desktop',1440,1000,{exclude:true,finance:true}],
    ['mobile',390,844,{budget:2000000,mileage:12000}],
    ['empty',390,844,{budget:100000}],
    ['seats',1440,1000,{passengers:7}],
    ['missing',390,844,{mileage:null}]
  ]) {
    await page.setViewportSize({width,height});await complete(scenario);
    const text=await page.locator('#recommendationResults').innerText();
    const cards=await page.locator('.recommendation-card').count();
    if(mode==='desktop') {check(cards===3,'SUV filter not applied');check(text.includes('五年後仍有 24 期'),'Remaining loan missing');check(text.includes('通過系統財務限制'),'Financial engine results absent');}
    if(mode==='mobile') {check(cards===6,'Expected six rankable versions');check((await page.locator('.recommendation-card h4').first().innerText()).includes('FIT'),'High mileage winner unexpected');check(text.includes('資料不足，暫不排名（1）'),'BEV missing data hidden');}
    if(mode==='empty'||mode==='seats')check(cards===0&&text.includes('目前沒有可完整排名'),'Empty results invented');
    if(mode==='missing')check(cards===0&&text.includes('請補充每月行駛里程'),'Missing input silently filled');
    const geometry=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
    check(geometry.document<=geometry.viewport,mode+': horizontal overflow');
    await page.locator('#recommendationResults').scrollIntoViewIfNeeded();
    await page.screenshot({path:`finsim-p2-${mode}.png`,fullPage:true});
    await page.locator('#jsonDetails summary').click();
    const download=page.waitForEvent('download');await page.getByRole('button',{name:'下載 JSON',exact:true}).click();
    check((await download).suggestedFilename()==='finsim-car-needs.json','JSON export failed');
    await page.getByRole('button',{name:'修改需求',exact:true}).click();
    check(await page.locator('.recommendation-card').count()===0,'Old result persisted after editing');
    check(await page.locator('[name="budget_max"]').inputValue()===String(scenario.budget||1000000),'Answers lost');
    results.push({mode,cards,geometry});
  }
  // API errors and retry must not discard confirmed answers.
  await complete();
  await page.route('**/decisions/vehicle/recommendations',route=>route.fulfill({status:503,contentType:'application/json',body:'{}'}));
  await page.getByRole('button',{name:'查看符合條件車款',exact:true}).click();
  await page.locator('#recommendationStatus').filter({hasText:'暫時無法完成'}).waitFor();
  check(await page.getByRole('button',{name:'查看符合條件車款',exact:true}).isEnabled(),'Retry disabled');
  await page.unroute('**/decisions/vehicle/recommendations');
  await page.getByRole('button',{name:'查看符合條件車款',exact:true}).click();
  await page.locator('#recommendationStatus').filter({hasText:'比較完成'}).waitFor();
  await page.route('**/decisions/vehicle/recommendations',()=>{});
  await page.getByRole('button',{name:'查看符合條件車款',exact:true}).click();
  await page.locator('#recommendationStatus').filter({hasText:'計算逾時'}).waitFor({timeout:20000});
  check(await page.locator('.recommendation-card').count()===0,'Old results remain after timeout');
  check(await page.getByRole('button',{name:'查看符合條件車款',exact:true}).isEnabled(),'Timeout blocks retry');
  await page.unroute('**/decisions/vehicle/recommendations');
  await page.getByRole('button',{name:'查看符合條件車款',exact:true}).click();
  await page.locator('#recommendationStatus').filter({hasText:'比較完成'}).waitFor();
  check(errors.length===0,errors.join('; '));check(aiRequests.length===0,'Unexpected AI dependency');
  return {results,errors,aiRequests,retry:true,timeout:true};
}
