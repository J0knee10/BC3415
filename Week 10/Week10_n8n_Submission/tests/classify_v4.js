// V4 invoice classification - the exact body of the "Classify invoice (V4 rules)" Code node.
// In n8n it runs as: return classify($('Normalize').all(), $('Load PO master').all(), $('Load AP ledger').all());
// Kept as a plain function so tests/test_classify_v4.js can exercise it outside n8n.
//
// Differences from the lab's V3 rules:
//   * PO master comes from a Data Table (Week10_PO_Master), not constants in the code.
//   * Duplicates are checked against EVERY invoice already in the ledger table (persistent),
//     plus earlier rows in the same batch, plus the lab's historic fixture.
//   * New controls: PO closed, PO already invoiced (re-billing under a new reference),
//     split invoices (same supplier, 7 days, each <= $10k, together > $10k).
//   * Each case gets a case_id and a priority (P1 hold / P2 review / P3 ready).
function classify(invoiceItems, poRows, ledgerRows, now) {
  now = now || new Date();
  const APPROVAL_LIMIT = 10000;
  const SPLIT_WINDOW_DAYS = 7;
  const historicFixture = new Set(['ALPHA|A-776']); // the lab's posted-invoice fixture, kept for continuity

  const up = (v, n) => String(v ?? '').trim().toUpperCase().slice(0, n);
  const po = {};
  for (const r of poRows) {
    const j = r.json || r;
    if (!j.po_id) continue;
    po[up(j.po_id, 60)] = { supplier: up(j.supplier, 60), amount: Number(j.amount_usd), status: up(j.status || 'OPEN', 20) };
  }

  // Ledger rows that count as "real" earlier invoices: anything not rejected as invalid or duplicate
  const ledger = ledgerRows.map(r => r.json || r).filter(j => j.invoice_id);
  const live = ledger.filter(j => !['HOLD_INVALID_DATA', 'HOLD_DUPLICATE'].includes(j.status));
  const seenKeys = new Set(ledger.map(j => `${up(j.supplier, 60)}|${up(j.invoice_ref, 60)}`));
  const poUsed = new Set(live.filter(j => j.po_id).map(j => up(j.po_id, 60)));
  const recent = live.map(j => ({ supplier: up(j.supplier, 60), amount: Number(j.amount_usd), at: new Date(j.received_at || j.createdAt || 0) }));

  const out = [];
  invoiceItems.forEach((item, idx) => {
    const d = item.json || item;
    const team_id = String(d.team_id ?? '').trim().slice(0, 20);
    const invoice_id = up(d.invoice_id, 60);
    const supplier = up(d.supplier, 60);
    const invoice_ref = up(d.invoice_ref, 60);
    const po_id = up(d.po_id, 60);
    const raw = String(d.amount_usd ?? '').trim();
    const amount = raw !== '' ? Number(raw) : NaN;
    const bank_changed = ['YES', 'TRUE', '1'].includes(up(d.bank_changed || 'NO', 10));
    const channel = String(d.channel || 'form');
    const valid = invoice_id && supplier && invoice_ref && Number.isFinite(amount) && amount > 0 && amount < 10000000;
    const key = `${supplier}|${invoice_ref}`;
    const high = Number.isFinite(amount) && amount > APPROVAL_LIMIT;

    // split detection: same supplier within the window, each at or under the limit, together over it
    const since = new Date(now.getTime() - SPLIT_WINDOW_DAYS * 86400000);
    const siblings = recent.filter(r => r.supplier === supplier && r.at >= since && r.amount <= APPROVAL_LIMIT);
    const splitTotal = siblings.reduce((s, r) => s + r.amount, 0) + (Number.isFinite(amount) ? amount : 0);
    const split = valid && !high && siblings.length > 0 && splitTotal > APPROVAL_LIMIT;

    const flags = [];
    let status = 'READY_FOR_HUMAN_CHECK', reason = 'All V4 controls passed; human confirmation still required';
    if (!valid) {
      status = 'HOLD_INVALID_DATA'; reason = 'Required field missing or invalid amount'; flags.push('INVALID_DATA');
    } else if (historicFixture.has(key) || seenKeys.has(key)) {
      status = 'HOLD_DUPLICATE';
      reason = historicFixture.has(key) ? 'Supplier and reference already in the historic posted-invoice fixture'
                                        : 'Supplier and reference already submitted (found in AP ledger table or earlier in this batch)';
      flags.push('DUPLICATE');
    } else if (bank_changed) {
      status = 'HOLD_BANK_CHANGE'; reason = 'Bank details changed; call the supplier on a known number before paying'; flags.push('BANK_CHANGE');
    } else if (!po_id) {
      status = 'REVIEW_MISSING_PO'; reason = 'Purchase order missing'; flags.push('MISSING_PO');
    } else if (!po[po_id]) {
      status = 'REVIEW_UNKNOWN_PO'; reason = `${po_id} is not in the PO master table`; flags.push('UNKNOWN_PO');
    } else if (po[po_id].status !== 'OPEN') {
      status = 'REVIEW_PO_CLOSED'; reason = `${po_id} is ${po[po_id].status}, not OPEN`; flags.push('PO_CLOSED');
    } else if (po[po_id].supplier !== supplier) {
      status = 'REVIEW_PO_SUPPLIER'; reason = `${po_id} belongs to ${po[po_id].supplier}, not ${supplier}`; flags.push('PO_SUPPLIER_MISMATCH');
    } else if (poUsed.has(po_id)) {
      status = 'REVIEW_PO_ALREADY_INVOICED'; reason = `${po_id} has already been invoiced under another reference (possible re-billing)`; flags.push('PO_ALREADY_INVOICED');
    } else if (Math.abs(po[po_id].amount - amount) > 0.01) {
      status = 'REVIEW_AMOUNT_MISMATCH'; reason = `PO amount is $${po[po_id].amount.toFixed(2)}, invoice says $${amount.toFixed(2)}`; flags.push('AMOUNT_MISMATCH');
    } else if (split) {
      status = 'REVIEW_SPLIT_SUSPECTED';
      reason = `${siblings.length + 1} invoices from ${supplier} in ${SPLIT_WINDOW_DAYS} days, each <= $10,000 but $${splitTotal.toFixed(2)} together (approval-limit splitting?)`;
      flags.push('SPLIT_SUSPECTED');
    } else if (high) {
      status = 'REVIEW_MANAGER'; reason = 'Finance-manager approval required (amount > $10,000)'; flags.push('HIGH_VALUE');
    }
    if (high && !flags.includes('HIGH_VALUE')) flags.push('HIGH_VALUE');
    if (split && !flags.includes('SPLIT_SUSPECTED')) flags.push('SPLIT_SUSPECTED');
    const manager_approval_required = high || split;
    if (manager_approval_required && status !== 'REVIEW_MANAGER' && status !== 'REVIEW_SPLIT_SUSPECTED') {
      reason += '; finance-manager approval also required';
    }
    const priority = status.startsWith('HOLD') ? 'P1' : (status.startsWith('REVIEW') ? 'P2' : 'P3');
    const control_flags = flags.join('|') || 'NONE';
    const received_at = now.toISOString();
    const case_id = `AP-${received_at.slice(0, 10).replace(/-/g, '')}-${(invoice_id || 'NOID').replace(/[^A-Z0-9]/g, '')}-${String(now.getTime() + idx).slice(-5)}`;
    const amountText = Number.isFinite(amount) ? amount.toFixed(2) : 'INVALID';
    const icon = { P1: '\u{1F534} HOLD', P2: '\u{1F7E0} REVIEW', P3: '\u{1F7E2} READY' }[priority];
    const telegram_text = `MERIDIAN AP V4 | ${icon}\nCase: ${case_id}\nInvoice: ${invoice_id} (${channel})\nSupplier: ${supplier}  Ref: ${invoice_ref}\nAmount: $${amountText}  PO: ${po_id || '-'}\nStatus: ${status}\nFlags: ${control_flags}\nReason: ${reason}\nHUMAN REVIEW REQUIRED. NO PAYMENT MADE.`;

    out.push({ json: {
      case_id, channel, priority, team_id, invoice_id, supplier, invoice_ref,
      amount_usd: Number.isFinite(amount) ? amount : null, po_id, bank_changed: bank_changed ? 'YES' : 'NO',
      status, reason, control_flags, received_at,
      manager_approval_required, human_approval_required: true, payment_authorized: false, ai_can_override_status: false,
      ai_commentary: '', ai_guardrail: priority === 'P2' ? 'PENDING' : 'NOT_REQUIRED', telegram_text,
    } });

    // later rows in the same batch must see this one
    seenKeys.add(key);
    if (valid && status !== 'HOLD_DUPLICATE') {
      if (po_id) poUsed.add(po_id);
      recent.push({ supplier, amount, at: now });
    }
  });
  return out;
}

if (typeof module !== 'undefined') module.exports = { classify };
