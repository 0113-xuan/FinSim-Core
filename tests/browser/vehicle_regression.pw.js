async page => {
  const origin=new URL(page.url()).origin,errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(origin+'/vehicle.html');
  await page.locator('#vehicleModel option[value="toyota-cross-gas-luxury"]').waitFor({state:'attached'});
  await page.locator('#vehicleModel').selectOption('toyota-cross-gas-luxury');
  await page.locator('#applyVehiclePreset').click();
  await page.locator('[name="payment_method"]').selectOption('cash');
  await page.locator('#reviewed').check();
  await page.locator('#submitDecision').click();
  await page.locator('#singleCostResults').waitFor({state:'visible'});
  if(!(await page.locator('#singleCostMonthly').innerText()).includes('NT$'))throw new Error('Single result missing');
  await page.locator('[name="vehicleMode"][value="compare"]').check();
  for(const [key,value] of Object.entries({salary:80000,balance:1200000,fixed_expense:12000,variable_expense:10000,required_monthly_debt:0}))await page.locator(`#vehicleForm [name="${key}"]`).fill(String(value));
  await page.locator('#costLeft').selectOption('toyota-cross-gas-luxury');
  await page.locator('#costRight').selectOption('toyota-cross-hybrid-luxury');
  for(const side of ['left','right'])await page.locator(`#${side}Finance [data-finance="payment_method"]`).selectOption('cash');
  await page.locator('#compareReviewed').check();
  await page.locator('#compareCosts').click();
  await page.locator('#costCompareResults').waitFor({state:'visible'});
  if(!(await page.locator('#financialCompareScores').innerText()).includes('NT$'))throw new Error('Dual financial results missing');
  if(errors.length)throw new Error(errors.join('; '));
  return {single:true,dual_financial:true,errors};
}
