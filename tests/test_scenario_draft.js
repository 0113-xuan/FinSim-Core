const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'app.js'), 'utf8');

test('scenario conversation uses the stateless draft endpoint and sends prior draft', () => {
  assert.match(source, /api\('\/scenarios\/draft\/message'/);
  assert.match(source, /draft: state\.scenarioDraft/);
  assert.match(source, /draftResponse\.draft\.next_question/);
});

test('short contextual answers are sent to the backend', () => {
  assert.doesNotMatch(source, /compact\.length < 4/);
});

test('scenario draft survives reload and is cleared on restart or completion', () => {
  assert.match(source, /sessionStorage\.setItem\('finsim-scenario-draft'/);
  assert.match(source, /sessionStorage\.getItem\('finsim-scenario-draft'/);
  assert.ok((source.match(/sessionStorage\.removeItem\('finsim-scenario-draft'\)/g) || []).length >= 2);
});

test('typed comparison is gated by explicit confirmation', () => {
  assert.match(source, /api\('\/scenarios\/draft\/confirm'/);
  assert.match(source, /explicit_confirmation: true/);
  const draftCreation = source.indexOf("scenario.scenarioDraft = draftResponse.draft");
  const confirmation = source.indexOf("api('/scenarios/draft/confirm'");
  const comparison = source.indexOf('T.runTypedScenarioComparison', confirmation);
  assert.ok(draftCreation >= 0 && confirmation > draftCreation && comparison > confirmation);
});

test('modified generic review cannot run a stale typed comparison', () => {
  assert.match(source, /const wasModified = scenario\.status === '使用者已修改'/);
  assert.match(source, /if \(wasModified\) \{[\s\S]*scenario\.typedScenarioRequest = null/);
  assert.match(source, /scenario\.scenarioDraft = null/);
  assert.match(source, /typed comparison 未執行/);
});

test('confirmed comparison uses the active AI or manual profile', () => {
  assert.match(source, /state\.profileMode === 'manual'/);
  assert.match(source, /\? buildProfile\(\)/);
  assert.match(source, /: state\.confirmedProfile/);
  assert.match(source, /confirmedProfile: comparisonProfile/);
  assert.match(source, /baselineLoans: monthlyDebtLoan\(\)/);
});
