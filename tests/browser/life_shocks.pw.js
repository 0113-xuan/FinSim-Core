async page => {
  const origin=new URL(page.url()).origin;
  const html=await (await page.request.get(origin+'/plan.html')).text();
  await page.setViewportSize({width:375,height:812});
  await page.setContent(html.replace(/<script\b[^>]*>\s*<\/script>/g,''),{waitUntil:'domcontentloaded'});
  await page.addScriptTag({url:origin+'/planner-model.js'});
  await page.addScriptTag({url:origin+'/shell-model.js'});
  await page.addScriptTag({url:origin+'/results-model.js'});
  const source=await (await page.request.get(origin+'/plan-page.js')).text();
  const result=await page.evaluate(async source=>{
    document.querySelectorAll('#pageContent, #planWorkspace, #simulationResults').forEach(node=>node.hidden=false);
    const root=window, $=id=>document.getElementById(id), S={element:(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}};
    const fixture={probability_cash_shortfall:0.1233,net_worth_percentiles:{p5:0,p50:100000,p95:300000},assumptions:[
      {label:'重大醫療支出',kind:'expense',chance_in_horizon:0.2597,min_amount:50000,max_amount:300000},
      {label:'車禍與車損自付',kind:'expense',chance_in_horizon:0.2,min_amount:20000,max_amount:150000},
      {label:'收入中斷',kind:'income_gap',chance_in_horizon:0.2,duration_months:6}],disclaimer:'機率與金額是示範假設，不是統計或預測；只用來看這份計畫撐不撐得住意外。'};
    const run={mc:{...fixture,probability_cash_shortfall:0.02,net_worth_percentiles:{p5:100000,p50:300000,p95:500000}},request:{}},lastRun=run,ctx={alive:true,calculation:fn=>fn(async()=>fixture)};
    const start=source.indexOf('    async function loadLifeShocks(run)');
    const end=source.indexOf('    // Progress and failures',start);
    const load=eval(`(${source.slice(start,end).trim()})`);
    await load(run);
    return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,text:$('lifeShocksCard').innerText};
  },source);
  if(result.scrollWidth>result.width)throw new Error(`Horizontal overflow: ${result.scrollWidth} > ${result.width}`);
  if(!result.text.includes('沒有意外')||!result.text.includes('有意外')||!result.text.includes('收入中斷'))throw new Error('Comparison missing');
  await page.locator('#lifeShocksCard').scrollIntoViewIfNeeded();
  await page.screenshot({path:'life-shocks-375.png'});
  return result;
}


