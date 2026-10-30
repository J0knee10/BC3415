// Builds the five V4 workflow files in workflows/ (node tools/build_v4_workflows.js).
// The rule engine is copied verbatim from tests/classify_v4.js, so the Code node in n8n runs the
// same function the unit tests check. Credential and Data Table references are by NAME here;
// tools/n8n_setup.py swaps them for the instance's ids on import.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'workflows');
const rules = fs.readFileSync(path.join(ROOT, 'tests', 'classify_v4.js'), 'utf8')
  .replace(/\nif \(typeof module[^\n]*\n?/, '\n');

const NAMES = {
  core: 'Week10 V4 | sub | Core rules + AP ledger',
  notify: 'Week10 V4 | sub | Alerts + Gemini explanation',
  form: 'Week10 V4 | E1 - AP intake form',
  api: 'Week10 V4 | E2 - Batch invoice API',
  digest: 'Week10 V4 | E3 - Daily AP exception digest',
};
const TELEGRAM_CHAT = '={{ $env.TELEGRAM_CHAT_ID }}';
const GEMINI_MODEL = 'models/gemini-flash-lite-latest'; // 3.8-flash returned 503 (overloaded) during testing

let uid = 0;
const id = () => `00000000-0000-4000-8000-${String(++uid).padStart(12, '0')}`;
const table = name => ({ __rl: true, mode: 'id', value: name, cachedResultName: name });
const subflow = name => ({ __rl: true, mode: 'id', value: name, cachedResultName: name });
const node = (name, type, typeVersion, position, parameters, extra = {}) =>
  ({ parameters, id: id(), name, type, typeVersion, position, ...extra });
const link = (...names) => {
  const c = {};
  for (let i = 0; i < names.length - 1; i++) c[names[i]] = { main: [[{ node: names[i + 1], type: 'main', index: 0 }]] };
  return c;
};
const sticky = (name, content, position, width = 420, height = 220, color = 7) =>
  node(name, 'n8n-nodes-base.stickyNote', 1, position, { content, width, height, color });
const telegram = (name, position, text) => node(name, 'n8n-nodes-base.telegram', 1.2, position, {
  resource: 'message', operation: 'sendMessage', chatId: TELEGRAM_CHAT, text,
  additionalFields: { appendAttribution: false, parse_mode: 'None' }, // plain text: '_' in status names breaks Markdown
});
const gemini = (name, position) => node(name, '@n8n/n8n-nodes-langchain.lmChatGoogleGemini', 1, position,
  { modelName: GEMINI_MODEL, options: { temperature: 0.1 } });
const llmChain = (name, position, prompt) => node(name, '@n8n/n8n-nodes-langchain.chainLlm', 1.5, position,
  { promptType: 'define', text: prompt }, { retryOnFail: true, maxTries: 3, waitBetweenTries: 5000 });
const execSub = (name, position, target, wait) => node(name, 'n8n-nodes-base.executeWorkflow', 1.2, position, {
  source: 'database', workflowId: subflow(target), mode: 'once',
  workflowInputs: { mappingMode: 'defineBelow', value: {}, matchingColumns: [], schema: [], attemptToConvertTypes: false, convertFieldsToString: true },
  options: { waitForSubWorkflow: wait },
});
const wf = (name, nodes, connections) => ({
  name, nodes, connections, pinData: {}, active: false,
  settings: { executionOrder: 'v1', timezone: 'Asia/Singapore', saveManualExecutions: true, callerPolicy: 'workflowsFromSameOwner' },
  meta: { templateCredsSetupCompleted: false }, tags: [],
});
const write = (file, w) => {
  fs.writeFileSync(path.join(OUT, file), JSON.stringify(w, null, 2));
  console.log('wrote', file, '-', w.nodes.filter(n => n.type !== 'n8n-nodes-base.stickyNote').length, 'nodes');
};

// ------------------------------------------------------------------ core (sub-workflow)
{
  const T = 'When called by an intake workflow';
  const nodes = [
    node(T, 'n8n-nodes-base.executeWorkflowTrigger', 1.1, [0, 300], { inputSource: 'passthrough' }),
    node('Load PO master', 'n8n-nodes-base.dataTable', 1.1, [240, 300],
      { resource: 'row', operation: 'get', dataTableId: table('Week10_PO_Master'), returnAll: true },
      { executeOnce: true, alwaysOutputData: true }),
    node('Load AP ledger', 'n8n-nodes-base.dataTable', 1.1, [480, 300],
      { resource: 'row', operation: 'get', dataTableId: table('Week10_AP_Ledger_V4'), returnAll: true },
      { executeOnce: true, alwaysOutputData: true }),
    node('Classify invoice (V4 rules)', 'n8n-nodes-base.code', 2, [720, 300], {
      mode: 'runOnceForAllItems',
      jsCode: `${rules}\n// Inputs: invoices from the caller, PO master and every earlier ledger row (persistent duplicate / PO / split checks)\n` +
        `return classify($('${T}').all(), $('Load PO master').all(), $('Load AP ledger').all(), new Date());`,
    }),
    node('Save to AP ledger', 'n8n-nodes-base.dataTable', 1.1, [960, 300], {
      resource: 'row', operation: 'insert', dataTableId: table('Week10_AP_Ledger_V4'),
      columns: { mappingMode: 'autoMapInputData', value: {}, matchingColumns: [], schema: [], attemptToConvertTypes: false, convertFieldsToString: false },
      options: {},
    }),
    node('Return cases with ledger row id', 'n8n-nodes-base.code', 2, [1200, 300], {
      mode: 'runOnceForAllItems',
      jsCode: "// Insert returns the stored row (with its id). Hand the caller each case plus ledger_row_id,\n" +
        "// so the alerts workflow can write the AI note back to the same row.\n" +
        "const classified = $('Classify invoice (V4 rules)').all();\n" +
        "return $input.all().map((row, i) => ({ json: { ...classified[i].json, ledger_row_id: row.json.id } }));",
    }),
    sticky('About this sub-workflow',
      '## V4 core: deterministic rules + persistent ledger\nCalled by **E1 (form)** and **E2 (batch API)**.\n\n' +
      '- PO master is a **Data Table** finance can edit (lab V3 hard-coded it)\n' +
      '- Duplicate check reads **every earlier ledger row** (V3 only knew one fixture)\n' +
      '- New controls: closed PO, PO already invoiced, split invoices under the $10k limit\n' +
      '- Rules = `tests/classify_v4.js` (12 unit tests)\n\nNo AI here. Nothing here can pay.', [-40, -60], 640, 300, 5),
  ];
  write('v4_sub_core_rules_ledger.json', wf(NAMES.core, nodes,
    link(T, 'Load PO master', 'Load AP ledger', 'Classify invoice (V4 rules)', 'Save to AP ledger', 'Return cases with ledger row id')));
}

// ------------------------------------------------------------------ alerts + Gemini (sub-workflow)
{
  const T = 'When called with classified cases';
  const R = 'Route by priority';
  const rule = (p, key) => ({
    conditions: {
      options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
      conditions: [{ id: id(), leftValue: '={{ $json.priority }}', rightValue: p, operator: { type: 'string', operation: 'equals' } }],
      combinator: 'and',
    },
    renameOutput: true, outputKey: key,
  });
  const prompt = '={{ "You are an accounts-payable process analyst at a training company. A deterministic rule engine has ALREADY decided this invoice\'s status; you only explain it.\\n\\n' +
    'Invoice: " + $json.invoice_id + " from " + $json.supplier + ", amount $" + $json.amount_usd + ", PO " + ($json.po_id || "none") + ".\\n' +
    'Status (fixed): " + $json.status + "\\nFlags: " + $json.control_flags + "\\nRule reason: " + $json.reason + "\\n\\n' +
    'Write 2 short sentences for the AP reviewer: what the risk is and what to check before approving. ' +
    'Do NOT change or question the status, do NOT say the invoice is approved, paid or ready for payment, do NOT ask for personal or bank details." }}';
  const guard = [
    "// Guardrail: the model may explain, never decide. Pair each AI answer with its case (same order),",
    "// reject text that claims approval/payment or names a different status, and fall back to the rule reason.",
    "const cases = $('" + R + "').all(1);",
    "const STATUSES = ['READY_FOR_HUMAN_CHECK','HOLD_INVALID_DATA','HOLD_DUPLICATE','HOLD_BANK_CHANGE','REVIEW_MISSING_PO','REVIEW_UNKNOWN_PO',",
    "  'REVIEW_PO_CLOSED','REVIEW_PO_SUPPLIER','REVIEW_PO_ALREADY_INVOICED','REVIEW_AMOUNT_MISMATCH','REVIEW_SPLIT_SUSPECTED','REVIEW_MANAGER'];",
    "const FORBIDDEN = /(approved for payment|has been (approved|paid)|is approved|been paid|payment (has been|was|is) (made|sent|released|scheduled)|ready for payment|authori[sz]ed? (the |this )?payment|i (have )?approved|bank (account|details) (number|to)|send (us|me) your)/i;",
    "return $input.all().map((item, i) => {",
    "  const c = cases[i].json;",
    "  const raw = String(item.json.text ?? item.json.output ?? '').trim();",
    "  const otherStatus = STATUSES.find(s => s !== c.status && raw.includes(s));",
    "  const problems = [];",
    "  if (!raw) problems.push('empty answer');",
    "  if (FORBIDDEN.test(raw)) problems.push('claims approval/payment or asks for bank details');",
    "  if (otherStatus) problems.push('mentions a different status ' + otherStatus);",
    "  const passed = problems.length === 0;",
    "  const ai_commentary = passed ? raw.slice(0, 900) : `[withheld by guardrail: ${problems.join('; ')}] Rule reason: ${c.reason}`;",
    "  const ai_guardrail = passed ? 'PASSED' : 'BLOCKED';",
    "  return { json: { ...c, ai_commentary, ai_guardrail,",
    "    telegram_text: `${c.telegram_text}\\n\\nAI note (advisory, guardrail ${ai_guardrail}): ${ai_commentary}` } };",
    "});",
  ].join('\n');
  const nodes = [
    node(T, 'n8n-nodes-base.executeWorkflowTrigger', 1.1, [0, 320], { inputSource: 'passthrough' }),
    node(R, 'n8n-nodes-base.switch', 3.2, [240, 320], {
      mode: 'rules', rules: { values: [rule('P1', 'P1 hold'), rule('P2', 'P2 review'), rule('P3', 'P3 ready')] }, options: {},
    }),
    telegram('Telegram: urgent HOLD alert', [560, 80], '={{ $json.telegram_text }}'),
    llmChain('Gemini: explain the review (advisory)', [560, 320], prompt),
    gemini('Google Gemini Chat Model', [560, 540]),
    node('Guardrail + join with rule output', 'n8n-nodes-base.code', 2, [880, 320], { mode: 'runOnceForAllItems', jsCode: guard }),
    node('Save AI note to ledger row', 'n8n-nodes-base.dataTable', 1.1, [1120, 320], {
      resource: 'row', operation: 'update', dataTableId: table('Week10_AP_Ledger_V4'), matchType: 'allConditions',
      filters: { conditions: [{ keyName: 'id', condition: 'eq', keyValue: '={{ $json.ledger_row_id }}' }] },
      columns: {
        mappingMode: 'defineBelow',
        value: { ai_commentary: '={{ $json.ai_commentary }}', ai_guardrail: '={{ $json.ai_guardrail }}' },
        matchingColumns: [],
        schema: [
          { id: 'ai_commentary', displayName: 'ai_commentary', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
          { id: 'ai_guardrail', displayName: 'ai_guardrail', required: false, defaultMatch: false, display: true, type: 'string', readOnly: false, removed: false },
        ],
        attemptToConvertTypes: false, convertFieldsToString: false,
      },
      options: {},
    }),
    telegram('Telegram: review with AI note', [1360, 320], "={{ $('Guardrail + join with rule output').item.json.telegram_text }}"),
    node('P3: logged only (goes in daily digest)', 'n8n-nodes-base.noOp', 1, [560, 760], {}),
    sticky('About this sub-workflow',
      '## Alerts by priority\n- **P1 HOLD** (duplicate, bank change, bad data): instant Telegram, facts only, no AI\n' +
      '- **P2 REVIEW**: Gemini writes a 2-sentence explanation; a **guardrail** rejects any text that claims approval/payment, ' +
      'names another status or asks for bank details; the note is written back to the ledger row; then Telegram\n' +
      '- **P3 READY**: no message (avoids alert fatigue); counted in the daily digest', [-40, -120], 560, 300, 5),
  ];
  const connections = {
    [T]: { main: [[{ node: R, type: 'main', index: 0 }]] },
    [R]: { main: [
      [{ node: 'Telegram: urgent HOLD alert', type: 'main', index: 0 }],
      [{ node: 'Gemini: explain the review (advisory)', type: 'main', index: 0 }],
      [{ node: 'P3: logged only (goes in daily digest)', type: 'main', index: 0 }],
    ] },
    ...link('Gemini: explain the review (advisory)', 'Guardrail + join with rule output', 'Save AI note to ledger row', 'Telegram: review with AI note'),
    'Google Gemini Chat Model': { ai_languageModel: [[{ node: 'Gemini: explain the review (advisory)', type: 'ai_languageModel', index: 0 }]] },
  };
  write('v4_sub_alerts_gemini.json', wf(NAMES.notify, nodes, connections));
}

// ------------------------------------------------------------------ E1 form
{
  const F = 'AP intake form';
  const field = (fieldLabel, fieldName, fieldType = 'text', requiredField = true, extra = {}) =>
    ({ fieldLabel, fieldName, fieldType, requiredField, ...extra });
  const nodes = [
    node(F, 'n8n-nodes-base.formTrigger', 2.5, [0, 300], {
      formTitle: 'Meridian AP intake (V4)',
      formDescription: 'For AP clerks keying in supplier invoices. Synthetic training data only. The rules decide a review status; nothing here approves or pays.',
      formFields: { values: [
        field('Team / clerk ID', 'team_id', 'text', true, { placeholder: 'T01' }),
        field('Invoice ID', 'invoice_id', 'text', true, { placeholder: 'INV-301' }),
        field('Supplier', 'supplier', 'text', true, { placeholder: 'EPSILON' }),
        field('Supplier invoice reference', 'invoice_ref', 'text', true, { placeholder: 'E-101' }),
        field('Amount (USD)', 'amount_usd', 'number', true),
        field('PO number (blank if none)', 'po_id', 'text', false, { placeholder: 'PO-506' }),
        field('Supplier says bank details changed?', 'bank_changed', 'dropdown', true,
          { fieldOptions: { values: [{ option: 'NO' }, { option: 'YES' }] } }),
      ] },
      responseMode: 'lastNode',
      options: { path: 'meridian-ap-v4', appendAttribution: false, buttonLabel: 'Submit for triage' },
    }),
    node('Tag channel', 'n8n-nodes-base.code', 2, [240, 300], {
      mode: 'runOnceForAllItems',
      jsCode: "return $input.all().map(i => ({ json: { ...i.json, channel: 'form' } }));",
    }),
    execSub('Run V4 core (rules + ledger)', [480, 300], NAMES.core, true),
    execSub('Start alerts (no wait)', [720, 300], NAMES.notify, false),
    node('Show triage result', 'n8n-nodes-base.form', 2.5, [960, 300], {
      operation: 'completion', respondWith: 'text',
      completionTitle: "={{ $('Run V4 core (rules + ledger)').first().json.status }}",
      completionMessage: "={{ (() => { const c = $('Run V4 core (rules + ledger)').first().json; return 'Case ' + c.case_id + ' | ' + c.priority + ' | ' + c.reason + ' | Flags: ' + c.control_flags + '. A person must still review it; no payment has been made.'; })() }}",
      options: {},
    }),
  ];
  write('v4_E1_ap_intake_form.json', wf(NAMES.form, nodes,
    link(F, 'Tag channel', 'Run V4 core (rules + ledger)', 'Start alerts (no wait)', 'Show triage result')));
}

// ------------------------------------------------------------------ E2 batch API
{
  const H = 'POST /webhook/meridian-ap-v4/batch';
  const nodes = [
    node(H, 'n8n-nodes-base.webhook', 2, [0, 300], {
      httpMethod: 'POST', path: 'meridian-ap-v4/batch', responseMode: 'responseNode', options: {},
    }, { webhookId: id() }),
    node('Split batch into invoices', 'n8n-nodes-base.code', 2, [240, 300], {
      mode: 'runOnceForAllItems',
      jsCode: "// Accepts {invoices:[...]} or a single invoice object, e.g. from an OCR/email-capture system.\n" +
        "const body = $input.first().json.body || {};\n" +
        "const list = Array.isArray(body.invoices) ? body.invoices : [body];\n" +
        "if (!list.length || list.length > 200) throw new Error('Send 1-200 invoices per batch');\n" +
        "return list.map(inv => ({ json: { ...inv, team_id: inv.team_id || body.team_id || 'API', channel: 'api' } }));",
    }),
    execSub('Run V4 core (rules + ledger)', [480, 300], NAMES.core, true),
    execSub('Start alerts (no wait)', [720, 300], NAMES.notify, false),
    node('Build API response', 'n8n-nodes-base.code', 2, [960, 300], {
      mode: 'runOnceForAllItems',
      jsCode: "const cases = $('Run V4 core (rules + ledger)').all().map(i => i.json);\n" +
        "const by = (k) => cases.reduce((m, c) => (m[c[k]] = (m[c[k]] || 0) + 1, m), {});\n" +
        "return [{ json: { received: cases.length, by_priority: by('priority'), by_status: by('status'), payment_authorized: false,\n" +
        "  cases: cases.map(c => ({ case_id: c.case_id, invoice_id: c.invoice_id, status: c.status, priority: c.priority,\n" +
        "    control_flags: c.control_flags, manager_approval_required: c.manager_approval_required, reason: c.reason })) } }];",
    }),
    node('Respond to caller', 'n8n-nodes-base.respondToWebhook', 1.1, [1200, 300], { respondWith: 'firstIncomingItem', options: {} }),
  ];
  write('v4_E2_batch_invoice_api.json', wf(NAMES.api, nodes,
    link(H, 'Split batch into invoices', 'Run V4 core (rules + ledger)', 'Start alerts (no wait)', 'Build API response', 'Respond to caller')));
}

// ------------------------------------------------------------------ E3 daily digest
{
  const facts = [
    "// Deterministic numbers for the last 24 hours. The model only rewords these facts.",
    "const since = Date.now() - 24 * 3600 * 1000;",
    "const rows = $input.all().map(i => i.json).filter(r => r.case_id && new Date(r.received_at).getTime() >= since);",
    "const count = (k) => rows.reduce((m, r) => (m[r[k]] = (m[r[k]] || 0) + 1, m), {});",
    "const sum = (f) => rows.filter(f).reduce((s, r) => s + (Number(r.amount_usd) || 0), 0);",
    "const p1 = rows.filter(r => r.priority === 'P1');",
    "const facts = {",
    "  window: 'last 24 hours', cases: rows.length, by_priority: count('priority'), by_status: count('status'),",
    "  on_hold_usd: Math.round(sum(r => r.priority === 'P1') * 100) / 100,",
    "  needs_manager_usd: Math.round(sum(r => r.manager_approval_required) * 100) / 100,",
    "  ai_notes_blocked: rows.filter(r => r.ai_guardrail === 'BLOCKED').length,",
    "  holds: p1.map(r => `${r.invoice_id} ${r.supplier} $${r.amount_usd} ${r.status}`),",
    "};",
    "const header = `MERIDIAN AP V4 | DAILY DIGEST\\nCases: ${facts.cases} | P1 ${facts.by_priority.P1 || 0} / P2 ${facts.by_priority.P2 || 0} / P3 ${facts.by_priority.P3 || 0}\\n` +",
    "  `On hold: $${facts.on_hold_usd.toFixed(2)} | Needs manager: $${facts.needs_manager_usd.toFixed(2)}\\n` +",
    "  `By status: ${Object.entries(facts.by_status).map(([k, v]) => k + ' ' + v).join(', ') || 'none'}`;",
    "return [{ json: { facts, facts_text: JSON.stringify(facts), header } }];",
  ].join('\n');
  const guard = [
    "// Guardrail for the briefing: every number the model writes must exist in the facts,",
    "// and it may not claim anything was approved or paid. Otherwise send the numbers alone.",
    "const f = $('Summarise last 24 hours').first().json;",
    "const raw = String($input.first().json.text ?? '').trim();",
    "const allowed = new Set((f.facts_text.match(/\\d+(?:\\.\\d+)?/g) || []).map(n => String(Number(n))));",
    "const used = (raw.replace(/,/g, '').match(/\\d+(?:\\.\\d+)?/g) || []).map(n => String(Number(n)));",
    "const invented = used.filter(n => !allowed.has(n) && !['1','2','3','24'].includes(n));",
    "const unsafe = /(approved for payment|has been paid|were paid|payments? (made|sent|released))/i.test(raw);",
    "const ok = raw && !invented.length && !unsafe;",
    "const note = ok ? raw : `[AI briefing withheld: ${!raw ? 'empty' : unsafe ? 'payment claim' : 'numbers not in the data: ' + invented.join(', ')}]`;",
    "return [{ json: { ...f, ai_briefing: note, ai_guardrail: ok ? 'PASSED' : 'BLOCKED',",
    "  telegram_text: `${f.header}\\n\\n${note}\\n\\n(Advisory summary. Statuses come from the rules; nothing is approved or paid.)` } }];",
  ].join('\n');
  const prompt = '={{ "You brief a finance manager. Using ONLY these facts (JSON), write 3 short bullet points: what needs action first, ' +
    'total value on hold, and anything unusual. Do not invent numbers, do not say anything was approved or paid.\\n\\nFacts: " + $json.facts_text }}';
  const nodes = [
    node('Every weekday 08:30 SGT', 'n8n-nodes-base.scheduleTrigger', 1.2, [0, 200], {
      rule: { interval: [{ field: 'cronExpression', expression: '0 30 8 * * 1-5' }] },
    }),
    node('Run digest now (manual)', 'n8n-nodes-base.manualTrigger', 1, [0, 420], {}),
    node('Load AP ledger', 'n8n-nodes-base.dataTable', 1.1, [260, 300],
      { resource: 'row', operation: 'get', dataTableId: table('Week10_AP_Ledger_V4'), returnAll: true }, { alwaysOutputData: true }),
    node('Summarise last 24 hours', 'n8n-nodes-base.code', 2, [500, 300], { mode: 'runOnceForAllItems', jsCode: facts }),
    llmChain('Gemini: manager briefing', [740, 300], prompt),
    gemini('Google Gemini Chat Model', [740, 520]),
    node('Guardrail: numbers must come from the data', 'n8n-nodes-base.code', 2, [980, 300], { mode: 'runOnceForAllItems', jsCode: guard }),
    telegram('Telegram: send digest', [1220, 300], '={{ $json.telegram_text }}'),
  ];
  const connections = {
    'Every weekday 08:30 SGT': { main: [[{ node: 'Load AP ledger', type: 'main', index: 0 }]] },
    'Run digest now (manual)': { main: [[{ node: 'Load AP ledger', type: 'main', index: 0 }]] },
    ...link('Load AP ledger', 'Summarise last 24 hours', 'Gemini: manager briefing', 'Guardrail: numbers must come from the data', 'Telegram: send digest'),
    'Google Gemini Chat Model': { ai_languageModel: [[{ node: 'Gemini: manager briefing', type: 'ai_languageModel', index: 0 }]] },
  };
  write('v4_E3_daily_ap_digest.json', wf(NAMES.digest, nodes, connections));
}
