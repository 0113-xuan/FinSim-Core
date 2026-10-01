const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const P = require('../static/profile-onboarding.js');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
const appSource = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../static/style.css'), 'utf8');

function field(value, source = 'user_provided', confirmed = true, confidence = 0.98) {
  return { value, source, confirmed, confidence, reason: '測試資料' };
}

function draft() {
  return {
    cash_and_deposits: field(800000),
    investments: field(200000),
    other_assets: field(0, 'system_default', false, 1),
    monthly_salary: field(60000),
    other_recurring_income: field(0, 'system_default', false, 1),
    fixed_expenses: field(20000),
    total_variable_expenses: field(15000, 'ai_extracted', false, .76),
    monthly_debt_payments: field(0),
    emergency_fund: field(100000),
    simulation_months: field(60),
    risk_preference: field('中性', 'system_default', false, 1),
    variable_expense_allocation: Object.keys(P.CATEGORY_LABELS).map((category, index) => ({
      category,
      amount: index === 7 ? 1050 : [4500, 2250, 1800, 1500, 1200, 1200, 1500][index],
      percentage: index === 7 ? 7 : [30, 15, 12, 10, 8, 8, 10][index],
      source: 'ai_estimated',
      confidence: .55,
      confirmed: false,
      reason: '系統比例提案'
    })),
    future_plans: [],
    validation_errors: [],
    conflicts: []
  };
}

test('Traditional Chinese onboarding entry and manual fallback are present', () => {
  assert.match(html, /1\. 你的財務資料/);
  assert.match(html, /用 AI 引導建立/);
  assert.match(html, /手動填寫/);
  assert.match(html, /AI 建立的財務資料草稿/);
  assert.match(html, /雲端 AI 暫時無法使用/);
  assert.match(html, /第 1 步，共 5 步/);
  assert.match(html, /現金與存款大約多少/);
  assert.doesNotMatch(html, /這會成為資產模擬的起點/);
  assert.match(html, /startAiOnboardingBtn[^>]+aria-pressed="false"/);
  assert.match(html, /startManualProfileBtn[^>]+aria-pressed="false"/);
});

test('AI and manual setup modes are mutually exclusive', () => {
  assert.match(appSource, /function setProfileSetupMode/);
  assert.match(appSource, /onboardingWorkspace'\)\.hidden = !useAi/);
  assert.match(appSource, /profile'\)\.hidden = !useManual/);
  assert.match(appSource, /setProfileSetupMode\('ai'\)/);
  assert.match(appSource, /setProfileSetupMode\('manual'\)/);
  assert.match(css, /\.onboarding-method\.is-selected/);
});

test('review renders value, source, confidence and confirmation status', () => {
  const output = P.renderReview(draft());
  assert.match(output, /現金與存款/);
  assert.match(output, /AI 擷取/);
  assert.match(output, /76%/);
  assert.match(output, /等待確認/);
  assert.match(output, /is-estimated/);
});

test('backend-normalized weekly income shows original value and calculation source', () => {
  const data = draft();
  data.other_recurring_income = {
    ...field(21666.67, 'backend_normalized', false, .99),
    original_amount: 5000,
    original_frequency: 'weekly',
    normalized_from: '後端計算：5000 × 52 ÷ 12',
    normalization_source: 'backend_calculation'
  };
  const output = P.renderReview(data);
  assert.match(output, /系統計算/);
  assert.match(output, /原始：5000（每週）/);
  assert.match(output, /5000 × 52 ÷ 12/);
});

test('current debt details show debt name, payment and remaining term', () => {
  const data = draft();
  data.debts = [{
    name: '車貸',
    principal: field(350000, 'user_provided', true, .99),
    monthly_payment: field(11000, 'ai_extracted', false, .99),
    remaining_months: field(60, 'ai_extracted', false, .99)
  }];
  const output = P.renderReview(data);
  assert.match(output, /債務明細/);
  assert.match(output, /車貸/);
  assert.match(output, /剩餘本金 NT\$350,000/);
  assert.match(output, /11,000/);
  assert.match(output, /剩餘 60 期/);
});

test('scenario clarification is handled before generic no-change fallback', () => {
  assert.match(appSource, /if \(data\.clarification\)/);
  assert.match(appSource, /scenarioClarificationText/);
});

test('user edits become unconfirmed user-modified values', () => {
  const data = draft();
  P.updateField(data, 'monthly_salary', 70000);
  assert.equal(data.monthly_salary.value, 70000);
  assert.equal(data.monthly_salary.source, 'user_modified');
  assert.equal(data.monthly_salary.confirmed, false);
});

test('fixed-total redistribution preserves allocation total and 100 percent', () => {
  const data = draft();
  P.redistributeAllocation(data, 0, 6000, true);
  assert.equal(data.variable_expense_allocation.reduce((sum, item) => sum + item.amount, 0), 15000);
  assert.equal(Math.round(data.variable_expense_allocation.reduce((sum, item) => sum + item.percentage, 0) * 100) / 100, 100);
});

test('changing allocation total updates variable-expense total', () => {
  const data = draft();
  P.redistributeAllocation(data, 0, 7000, false);
  const sum = data.variable_expense_allocation.reduce((total, item) => total + item.amount, 0);
  assert.equal(data.total_variable_expenses.value, sum);
  assert.equal(data.total_variable_expenses.source, 'user_modified');
});

test('client validation catches allocation mismatch', () => {
  const data = draft();
  data.variable_expense_allocation[0].amount += 100;
  assert.match(P.clientValidation(data).join(' '), /必須等於總額/);
});

test('draft must be explicitly confirmed before applying to simulation', () => {
  assert.match(appSource, /explicit_confirmation: true/);
  assert.match(appSource, /profileMode/);
  assert.match(appSource, /請先用 AI 建立並確認財務資料/);
  assert.match(appSource, /runBtn'\)\.disabled = true/);
});

test('draft persistence and provider-failure fallback retain data', () => {
  assert.match(appSource, /sessionStorage\.setItem\('finsim-profile-draft'/);
  assert.match(appSource, /sessionStorage\.setItem\('finsim-onboarding-unsent'/);
  assert.match(appSource, /financial-profile-drafts/);
});

test('onboarding requests time out, cancel stale responses and prevent duplicate sends', () => {
  assert.match(appSource, /new AbortController\(\)/);
  assert.match(appSource, /timeoutMs: 25000/);
  assert.match(appSource, /state\.onboardingRequestController\?\.abort\(\)/);
  assert.match(appSource, /requestId !== state\.onboardingRequestId/);
  assert.match(appSource, /!text \|\| state\.onboardingRequestController/);
});

test('unknown debt payment is not rendered as zero', () => {
  const data = draft();
  data.debts = [{
    name: '學貸',
    principal: field(150000, 'user_provided', false, .99),
    monthly_payment: field(null, 'system_default', false, 0)
  }];
  const output = P.renderReview(data);
  assert.match(output, /剩餘本金 NT\$150,000/);
  assert.match(output, /每月付款尚未提供/);
  assert.match(output, /等待補充/);
  assert.doesNotMatch(output, /每月付款 NT\$0/);
  const progress = P.renderProgress(data);
  assert.match(progress, /債務[\s\S]*部分完成[\s\S]*50%/);
});

test('mobile onboarding becomes a single-column workflow', () => {
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.match(css, /\.onboarding-methods \{ grid-template-columns: 1fr; \}/);
  assert.match(css, /\.onboarding-workspace \{ grid-template-columns: 1fr; \}/);
});
