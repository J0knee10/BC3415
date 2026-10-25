// Unit tests for the V4 rules (node tests/test_classify_v4.js). No n8n needed.
const assert = require('assert');
const { classify } = require('./classify_v4.js');

const PO = [
  ['PO-501', 'ALPHA', 1250, 'OPEN'], ['PO-502', 'BETA', 8950, 'OPEN'], ['PO-503', 'GAMMA', 4700, 'OPEN'],
  ['PO-505', 'DELTA', 24600, 'OPEN'], ['PO-506', 'EPSILON', 6000, 'OPEN'], ['PO-507', 'EPSILON', 5500, 'OPEN'],
  ['PO-508', 'ZETA', 3200, 'CLOSED'],
].map(([po_id, supplier, amount_usd, status]) => ({ json: { po_id, supplier, amount_usd, status } }));

const inv = (invoice_id, supplier, invoice_ref, amount_usd, po_id, bank_changed = 'NO') =>
  ({ json: { team_id: 'T01', invoice_id, supplier, invoice_ref, amount_usd, po_id, bank_changed } });

const LAB8 = [
  inv('INV-201', 'ALPHA', 'A-777', 1250, 'PO-501'), inv('INV-202', 'BETA', 'B-431', 8950, 'PO-502'),
  inv('INV-203', 'GAMMA', 'G-211', 14800, ''), inv('INV-204', 'ALPHA', 'A-776', 1250, 'PO-501'),
  inv('INV-205', 'DELTA', 'D-555', 24600, 'PO-505'), inv('INV-206', 'BETA', 'B-432', 9150, 'PO-502'),
  inv('INV-207', 'EPSILON', 'E-007', 500, 'PO-999'), inv('INV-208', 'GAMMA', 'G-323', 4700, 'PO-503', 'YES'),
];

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok  -', name); }
const statuses = rows => Object.fromEntries(rows.map(r => [r.json.invoice_id, r.json.status]));

test('lab cases one at a time on an empty ledger give the lab answers (Appendix A)', () => {
  const got = {};
  for (const i of LAB8) Object.assign(got, statuses(classify([i], PO, [])));
  assert.deepStrictEqual(got, {
    'INV-201': 'READY_FOR_HUMAN_CHECK', 'INV-202': 'READY_FOR_HUMAN_CHECK', 'INV-203': 'REVIEW_MISSING_PO',
    'INV-204': 'HOLD_DUPLICATE', 'INV-205': 'REVIEW_MANAGER', 'INV-206': 'REVIEW_AMOUNT_MISMATCH',
    'INV-207': 'REVIEW_UNKNOWN_PO', 'INV-208': 'HOLD_BANK_CHANGE',
  });
});

test('as ONE batch, INV-206 is caught re-using PO-502 (V3 only saw an amount mismatch)', () => {
  const r = classify(LAB8, PO, []).map(x => x.json);
  const i206 = r.find(x => x.invoice_id === 'INV-206');
  assert.strictEqual(i206.status, 'REVIEW_PO_ALREADY_INVOICED');
  assert.ok(i206.control_flags.includes('SPLIT_SUSPECTED')); // BETA 8,950 + 9,150 in one week
});

test('safety invariants hold for every row', () => {
  for (const { json: j } of classify(LAB8, PO, [])) {
    assert.strictEqual(j.human_approval_required, true);
    assert.strictEqual(j.payment_authorized, false);
    assert.strictEqual(j.ai_can_override_status, false);
  }
});

test('INV-203: missing PO is primary, HIGH_VALUE still flagged, manager approval required', () => {
  const [j] = classify([LAB8[2]], PO, []).map(x => x.json);
  assert.strictEqual(j.control_flags, 'MISSING_PO|HIGH_VALUE');
  assert.strictEqual(j.manager_approval_required, true);
  assert.strictEqual(j.priority, 'P2');
});

test('persistent duplicate: resubmitting INV-201 is held once the ledger has it', () => {
  const first = classify([LAB8[0]], PO, []).map(x => x.json);
  const again = classify([inv('INV-201B', 'alpha', ' a-777 ', 1250, 'PO-501')], PO, first)[0].json;
  assert.strictEqual(again.status, 'HOLD_DUPLICATE');
  assert.strictEqual(again.priority, 'P1');
});

test('duplicate inside the same batch is held', () => {
  const r = classify([LAB8[0], inv('INV-209', 'ALPHA', 'A-777', 1250, 'PO-501')], PO, []);
  assert.strictEqual(r[1].json.status, 'HOLD_DUPLICATE');
});

test('PO already invoiced under a different reference is reviewed', () => {
  const ledger = classify([LAB8[0]], PO, []).map(x => x.json);
  const j = classify([inv('INV-210', 'ALPHA', 'A-778', 1250, 'PO-501')], PO, ledger)[0].json;
  assert.strictEqual(j.status, 'REVIEW_PO_ALREADY_INVOICED');
});

test('split invoices: two EPSILON invoices under $10k each but $11,500 together', () => {
  const now = new Date('2026-10-26T02:00:00Z');
  const first = classify([inv('INV-301', 'EPSILON', 'E-101', 6000, 'PO-506')], PO, [], now).map(x => x.json);
  assert.strictEqual(first[0].status, 'READY_FOR_HUMAN_CHECK');
  const second = classify([inv('INV-302', 'EPSILON', 'E-102', 5500, 'PO-507')], PO, first, new Date('2026-10-27T02:00:00Z'))[0].json;
  assert.strictEqual(second.status, 'REVIEW_SPLIT_SUSPECTED');
  assert.strictEqual(second.manager_approval_required, true);
});

test('split window: the same pair 8 days apart is not a split', () => {
  const first = classify([inv('INV-301', 'EPSILON', 'E-101', 6000, 'PO-506')], PO, [], new Date('2026-10-01T02:00:00Z')).map(x => x.json);
  const later = classify([inv('INV-302', 'EPSILON', 'E-102', 5500, 'PO-507')], PO, first, new Date('2026-10-09T03:00:00Z'))[0].json;
  assert.strictEqual(later.status, 'READY_FOR_HUMAN_CHECK');
});

test('closed PO is reviewed', () => {
  const j = classify([inv('INV-303', 'ZETA', 'Z-1', 3200, 'PO-508')], PO, [])[0].json;
  assert.strictEqual(j.status, 'REVIEW_PO_CLOSED');
});

test('invalid amount and missing fields are held', () => {
  assert.strictEqual(classify([inv('INV-304', 'ALPHA', 'A-9', -5, 'PO-501')], PO, [])[0].json.status, 'HOLD_INVALID_DATA');
  assert.strictEqual(classify([inv('', 'ALPHA', 'A-9', 10, 'PO-501')], PO, [])[0].json.status, 'HOLD_INVALID_DATA');
});

test('priorities and AI flags follow the status family', () => {
  const r = classify(LAB8, PO, []).map(x => x.json);
  for (const j of r) {
    const p = j.status.startsWith('HOLD') ? 'P1' : j.status.startsWith('REVIEW') ? 'P2' : 'P3';
    assert.strictEqual(j.priority, p);
    assert.strictEqual(j.ai_guardrail, p === 'P2' ? 'PENDING' : 'NOT_REQUIRED');
  }
});

console.log(`\n${passed} tests passed`);
