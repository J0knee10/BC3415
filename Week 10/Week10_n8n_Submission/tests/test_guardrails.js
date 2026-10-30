// Runs the two guardrail Code nodes exactly as exported in workflows/*.json against unsafe
// model outputs, with n8n's $ / $input replaced by small fakes. (node tests/test_guardrails.js)
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const wf = f => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'workflows', f), 'utf8'));
const code = (w, name) => w.nodes.find(n => n.name === name).parameters.jsCode;
const run = (src, $, $input) => new Function('$', '$input', src)($, $input);
let passed = 0;
const test = (name, fn) => { fn(); passed++; console.log('ok  -', name); };

// ---- P2 review explanation guardrail
const reviewGuard = code(wf('v4_sub_alerts_gemini.json'), 'Guardrail + join with rule output');
const theCase = { invoice_id: 'INV-203', status: 'REVIEW_MISSING_PO', reason: 'Purchase order missing', telegram_text: 'MERIDIAN AP V4' };
const review = text => run(reviewGuard, () => ({ all: () => [{ json: theCase }] }), { all: () => [{ json: { text } }] })[0].json;

test('a normal explanation passes and is appended to the Telegram text', () => {
  const r = review('There is no PO, so spend may be unbudgeted. Check with procurement before approving.');
  assert.strictEqual(r.ai_guardrail, 'PASSED');
  assert.ok(r.telegram_text.includes('guardrail PASSED'));
});
for (const bad of [
  'This invoice has been approved for payment.',
  'Payment was released this morning, nothing else to do.',
  'It is ready for payment once you click approve.',
  'Please ask the supplier to send us your bank account number.',
]) {
  test(`blocks a payment/approval claim: "${bad.slice(0, 40)}..."`, () => {
    const r = review(bad);
    assert.strictEqual(r.ai_guardrail, 'BLOCKED');
    assert.ok(r.ai_commentary.startsWith('[withheld by guardrail'));
    assert.ok(r.ai_commentary.includes('Purchase order missing')); // falls back to the rule's own reason
  });
}
test('blocks an answer that names a different status', () => {
  assert.strictEqual(review('Honestly this looks like READY_FOR_HUMAN_CHECK to me.').ai_guardrail, 'BLOCKED');
});
test('blocks an empty answer', () => {
  assert.strictEqual(review('').ai_guardrail, 'BLOCKED');
});

// ---- daily digest guardrail: numbers must come from the data
const digestGuard = code(wf('v4_E3_daily_ap_digest.json'), 'Guardrail: numbers must come from the data');
const facts = { cases: 13, on_hold_usd: 7200, needs_manager_usd: 51400, by_priority: { P1: 3, P2: 6, P3: 4 } };
const summary = { facts, facts_text: JSON.stringify(facts), header: 'MERIDIAN AP V4 | DAILY DIGEST' };
const digest = text => run(digestGuard, () => ({ first: () => ({ json: summary }) }), { first: () => ({ json: { text } }) })[0].json;

test('digest with only real numbers passes', () => {
  assert.strictEqual(digest('- 3 holds need action first\n- $7,200 is on hold\n- 13 cases in total').ai_guardrail, 'PASSED');
});
test('digest with an invented number is withheld', () => {
  const r = digest('- 5 holds need action\n- $9,999 on hold');
  assert.strictEqual(r.ai_guardrail, 'BLOCKED');
  assert.ok(r.ai_briefing.includes('numbers not in the data'));
  assert.ok(r.telegram_text.startsWith('MERIDIAN AP V4 | DAILY DIGEST')); // the deterministic header still goes out
});
test('digest claiming payments were made is withheld', () => {
  assert.strictEqual(digest('- 3 payments released today').ai_guardrail, 'BLOCKED');
});

console.log(`\n${passed} tests passed`);
