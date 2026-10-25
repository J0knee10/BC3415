"""Builds docs/Week10_n8n_Report.html from the saved execution logs and screenshots.

Every execution id, status, Telegram message id and AI note below is read from
execution_logs/*.json, so the report matches what actually ran.  python docs/build_report.py
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "execution_logs"


def log(prefix):
    f = sorted(LOGS.glob(prefix + "*.json"))
    if not f:
        raise SystemExit(f"missing log {prefix}")
    return json.loads(f[0].read_text(encoding="utf-8"))


def out(e, node, i=0):
    return e["runData"][node][-1]["data"]["main"][0][i]["json"]


def outs(e, node, branch=0):
    return [x["json"] for x in (e["runData"][node][-1]["data"]["main"][branch] or [])]


def esc(x):
    return html.escape(str(x))


def table(headers, rows, num=()):
    h = "".join(f"<th>{esc(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def fig(name, caption, width=""):
    style = f' style="max-width:{width}"' if width else ""
    return f'<figure><img src="../screenshots/{name}"{style}><figcaption>{esc(caption)}</figcaption></figure>'


def tg(e, node):
    j = out(e, node)
    return f"ok={str(j.get('ok')).lower()}, message_id {j['result']['message_id']}"


# ---- lab A-D
A = None  # run from the editor; numbers read from the screenshot-backed summary below
B = log("B1_intake_execution")
C = {k: log(f"C{i}_{k}_execution") for i, k in [(1, "INV-201"), (2, "INV-203"), (3, "INV-204"), (4, "INV-205")]}
D0 = log("D0_troubleshoot_503")
D = log("D1_INV-203_gemini_execution")
lab_rows = [
    ["B", "INV request T01 / Alex", f"#{B['id']}", B["status"], "row saved to Week10_Intake", tg(B, "Send Telegram notification")],
]
for k, e in C.items():
    j = out(e, "Classify invoice")
    lab_rows.append(["C", k, f"#{e['id']}", e["status"], f"{j['status']} ({j['control_flags']}); manager={str(j['manager_approval_required']).lower()}, paid={str(j['payment_authorized']).lower()}",
                     tg(e, "Send Telegram notification")])
jd = out(D, "Join AI explanation with rule output")
lab_rows.append(["D", "INV-203 (team T02)", f"#{D0['id']}", D0["status"], "Gemini 3.8 Flash: 503 Service unavailable (see 6.1)", "not sent"])
lab_rows.append(["D", "INV-203 (team T02)", f"#{D['id']}", D["status"], f"{jd['status']} + AI note", tg(D, "Send Telegram notification")])

# ---- V4
E2 = {k: log(f"E2_batch_lab8_{k}_execution") for k in ("api", "core", "alerts")}
batch = out(E2["api"], "Build API response")
alert_notes = {j["invoice_id"]: j for j in outs(E2["alerts"], "Guardrail + join with rule output")}
v4_rows = []
for c in batch["cases"]:
    a = alert_notes.get(c["invoice_id"])
    route = {"P1": "instant HOLD alert", "P2": "Gemini note + alert", "P3": "logged, digest only"}[c["priority"]]
    v4_rows.append([c["invoice_id"], c["priority"], c["status"], c["control_flags"], route, esc(a["ai_guardrail"]) if a else "-"])

scen = []
for prefix, label in [("E1_split_part1_INV-301", "INV-301 EPSILON $6,000 PO-506 (form)"),
                      ("E1_split_part2_INV-302", "INV-302 EPSILON $5,500 PO-507 (form)"),
                      ("E1_persistent_duplicate_INV-201B", "INV-201B 'alpha' ' a-777 ' $1,250 (form, re-keyed)"),
                      ("E2_closed_po_INV-303", "INV-303 ZETA $3,200 PO-508 (API)")]:
    core = log(prefix + "_core_execution")
    alerts = log(prefix + "_alerts_execution")
    j = out(core, "Classify invoice (V4 rules)")
    notes = {x["invoice_id"]: x for x in outs(alerts, "Guardrail + join with rule output")} if "Guardrail + join with rule output" in alerts["runData"] else {}
    sent = "Telegram: urgent HOLD alert" if "Telegram: urgent HOLD alert" in alerts["runData"] else (
        "Telegram: review with AI note" if "Telegram: review with AI note" in alerts["runData"] else None)
    scen.append([esc(label), f"#{core['id']} / #{alerts['id']}", j["status"], esc(j["reason"]),
                 tg(alerts, sent) if sent else "none (P3)", esc(notes[j["invoice_id"]]["ai_guardrail"]) if j["invoice_id"] in notes else "-"])

E3 = log("E3_daily_digest_execution")
digest = out(E3, "Guardrail: numbers must come from the data")
ai_examples = [[esc(j["invoice_id"]), esc(j["status"]), esc(j["ai_commentary"])] for j in list(alert_notes.values())[:3]]
split_note = notes_split = out(log("E1_split_part2_INV-302_alerts_execution"), "Guardrail + join with rule output")

css = """
:root{--ink:#1d2433;--mute:#5a6475;--line:#e3e7ee;--head:#f3f5f9;--good:#1b7f3b;--bad:#a4161a}
body{font-family:'Segoe UI',Arial,sans-serif;color:var(--ink);background:#fff;max-width:980px;margin:28px auto;padding:0 20px;line-height:1.45;font-size:14px}
h1{font-size:24px;margin:0}h2{font-size:18px;margin:30px 0 8px;border-bottom:2px solid var(--line);padding-bottom:4px}h3{font-size:15px;margin:18px 0 6px}
.sub{color:var(--mute);margin:4px 0 18px}table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}th{background:var(--head)}td.n{text-align:right}
figure{margin:12px 0 18px}figure img{max-width:100%;border:1px solid var(--line)}figcaption{color:var(--mute);font-size:12px;margin-top:4px}
pre{background:#f7f8fa;border:1px solid var(--line);padding:10px;font-size:11.5px;white-space:pre-wrap}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}.tile{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:150px}.tile b{display:block;font-size:19px}
code{font-size:12.5px}.ok{color:var(--good);font-weight:600}
@media print{body{margin:0 auto}h2,h3{break-after:avoid}figure,table,pre{break-inside:avoid}}
"""

n_tests = "22"  # 12 rule tests + 10 guardrail tests (tests/*.js)
telegram_sent = sum(1 for f in LOGS.glob("*.json") for node, runs in json.loads(f.read_text(encoding="utf-8"))["runData"].items()
                    if node.startswith(("Send Telegram", "Telegram")) for x in ((runs[-1].get("data") or {}).get("main") or [[]])[0] or []
                    if x["json"].get("ok"))
doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Week 10 n8n Lab</title><style>{css}</style></head><body>
<h1>AI workflow automation with n8n</h1>
<div class="sub">BC3415 Week 10 &middot; Jonathan Low &middot; n8n 2.44.6 self-hosted (local) &middot; Telegram + Google Gemini &middot; synthetic data only</div>

<h2>1. Summary</h2>
<p>I installed and ran n8n locally, imported and configured all four lab workflows (A&ndash;D) with my own Telegram bot and Gemini key,
and ran the guide's test cases. Every checkpoint on the lab's evidence sheet is met, and every execution is logged in <code>execution_logs/</code>.
I then built a customised <b>V4 accounts-payable triage service</b>: five workflows that fix the limitations the lab guide itself lists (Appendix D and section 7.4):
a hard-coded PO list, a duplicate check that never learns, and AI text that is never stored. V4 also adds new fraud controls,
priority-based alerting, a batch API, a guardrail on the AI output, and a daily manager digest.</p>
<div class="tiles">
<div class="tile">Workflows built and run<b>9</b></div>
<div class="tile">Executions logged<b>{len(list(LOGS.glob('*.json')))}</b></div>
<div class="tile">Telegram messages sent<b>{telegram_sent}</b></div>
<div class="tile">Unit tests passing<b>{n_tests}</b></div>
<div class="tile">Payments authorised<b>0</b></div>
</div>

<h2>2. Setup</h2>
<ul>
<li><b>Route A (local)</b>, without Docker: n8n 2.44.6 installed with npm into a project folder, using a portable Node 24 (n8n 2.x needs Node &ge; 24; the
machine's global Node 22 was left alone). Editor at <code>http://localhost:5678</code>, telemetry off, timezone Asia/Singapore.</li>
<li>Telegram: my own bot from @BotFather. The recipient is my numeric private chat id (from <code>getUpdates</code> after sending <code>/start</code>), not the bot's id,
which avoids the guide's "bot can't send messages to the bot" 403 error.</li>
<li>Gemini: Google AI Studio key, stored as an n8n credential.</li>
<li><b>No secrets in this submission.</b> Keys live only in n8n's encrypted credential store. The chat id is read at run time as
<code>{{{{ $env.TELEGRAM_CHAT_ID }}}}</code>, so it isn't in any workflow JSON. Chat id, name and username are masked in screenshots and logs.</li>
<li>Reproducible: <code>tools/n8n_setup.py</code> rebuilds everything on a fresh n8n: Data Tables, seeded PO master, credentials (from environment variables),
workflow import with id wiring, and publishing.</li>
</ul>
{fig("L1_workflow_list.png", "All nine workflows imported and published.", "820px")}

<h2>3. Lab workflows A&ndash;D (as supplied, configured)</h2>
{fig("A1_offline_workflow_executed.png", "A: offline check, 1 → 8 → 8 → 1 items.", "820px")}
{fig("A2_offline_summary_output.png", "A: Summary for class: cases = 8, two READY and one of each other status, exactly the guide's Appendix A answer.")}
{table(["Flow", "Case", "Execution", "Result", "What happened", "Telegram"], lab_rows)}
{fig("B2_intake_execution_canvas.png", "B: form → Normalize intake → Data Table → Telegram, all green.", "820px")}
{fig("B3_intake_telegram_output.png", "B2 checkpoint: Telegram API returned ok=true with a message_id (recipient details masked).")}
{fig("C6_invoice_INV-203_classify_output.png", "C2 checkpoint: INV-203 is REVIEW_MISSING_PO with MISSING_PO|HIGH_VALUE, manager_approval_required=true, payment_authorized=false.")}
{fig("T2_datatable_Week10_Invoice_Triage.png", "C1 checkpoint: Week10_Invoice_Triage with its 16 application columns and the C/D rows.")}
{fig("D3_gemini_join_output.png", "D: Gemini's explanation joined to the unchanged rule output; payment_authorized stays false.")}
<p><b>Evidence sheet (guide section 9.1):</b> A, B1 (<code>T1_datatable_Week10_Intake.png</code>), B2, C1, C2, C3 (INV-204 HOLD_DUPLICATE and INV-205 REVIEW_MANAGER in the table above),
and D are all met, with execution logs for each.</p>

<h2>4. Customisation: V4 AP triage service</h2>
<h3>4.1 Business problem</h3>
<p>Workflow C is a good teaching template, but the guide lists why it can't be used for real: the PO list is fixed in JavaScript, so finance can't update it;
the duplicate check only knows one historic invoice, so the same invoice submitted twice is not caught ("Duplicate not detected on second submission");
it treats each invoice alone, so it misses patterns across invoices; every outcome sends the same Telegram message; and the Gemini note in D is never saved.
These are exactly the gaps that let duplicate payments and approval-limit splitting through in real accounts-payable teams.</p>

<h3>4.2 Design</h3>
{table(["Workflow", "Role"], [
    ["<b>sub | Core rules + AP ledger</b>", "Loads the PO master and the whole ledger from Data Tables, runs the V4 rules, writes each case to <code>Week10_AP_Ledger_V4</code>. Deterministic; no AI."],
    ["<b>sub | Alerts + Gemini explanation</b>", "Switch by priority. P1 HOLD: instant Telegram, facts only. P2 REVIEW: Gemini explains, a guardrail checks it, the note is written back to the ledger row, then Telegram. P3 READY: no message (avoids alert fatigue)."],
    ["<b>E1 AP intake form</b>", "Form for AP clerks; dropdown for the bank-change question; shows the triage result and case id when submitted."],
    ["<b>E2 Batch invoice API</b>", "<code>POST /webhook/meridian-ap-v4/batch</code> takes 1&ndash;200 invoices (e.g. from an OCR or email-capture system) and returns a JSON summary."],
    ["<b>E3 Daily AP exception digest</b>", "Every weekday at 08:30 SGT: counts and amounts from the ledger; Gemini writes a 3-bullet briefing; a guardrail checks that every number in it exists in the data."],
])}
{fig("V4_core_execution_canvas.png", "Core sub-workflow on the batch run: 8 invoices → PO master (7 rows) → ledger → rules → saved.", "820px")}
{fig("V4_alerts_execution_canvas.png", "Alerts sub-workflow: 2 instant HOLD alerts, 4 Gemini-explained reviews (guardrail → ledger update → Telegram), 2 logged only.", "820px")}

<h3>4.3 Rules added (precedence order)</h3>
{table(["#", "Status", "Condition", "New in V4?"], [
    ["1", "HOLD_INVALID_DATA", "missing field or invalid amount", ""],
    ["2", "HOLD_DUPLICATE", "same supplier + reference anywhere in the ledger, earlier in the batch, or in the lab fixture (case and spaces ignored)", "<b>persistent</b>"],
    ["3", "HOLD_BANK_CHANGE", "supplier says bank details changed", ""],
    ["4", "REVIEW_MISSING_PO", "no PO", ""],
    ["5", "REVIEW_UNKNOWN_PO", "PO not in the PO master <b>Data Table</b>", "table, not code"],
    ["6", "REVIEW_PO_CLOSED", "PO status is not OPEN", "<b>new</b>"],
    ["7", "REVIEW_PO_SUPPLIER", "PO belongs to another supplier", ""],
    ["8", "REVIEW_PO_ALREADY_INVOICED", "the PO was already used by an earlier invoice with a different reference (re-billing)", "<b>new</b>"],
    ["9", "REVIEW_AMOUNT_MISMATCH", "amount differs from the PO", ""],
    ["10", "REVIEW_SPLIT_SUSPECTED", "same supplier, last 7 days, each &le; $10k but together &gt; $10k (approval-limit splitting); also sets manager approval", "<b>new</b>"],
    ["11", "REVIEW_MANAGER", "amount &gt; $10,000", ""],
    ["12", "READY_FOR_HUMAN_CHECK", "all controls pass", ""],
])}
<p>Each case also gets a <code>case_id</code> and a priority (P1/P2/P3). <code>human_approval_required=true</code>, <code>payment_authorized=false</code> and
<code>ai_can_override_status=false</code> on every row, as in the lab. The rules are a plain function (<code>tests/classify_v4.js</code>) that the build script copies into the Code node,
with 12 unit tests, including the guide's Appendix A answers for all 8 lab invoices.</p>

<h2>5. V4 results</h2>
<h3>5.1 The lab's 8 invoices sent as one API batch (executions #{E2['api']['id']}, #{E2['core']['id']}, #{E2['alerts']['id']})</h3>
{table(["Invoice", "Priority", "Status", "Flags", "Route", "AI guardrail"], v4_rows)}
<p>Same answers as the lab for 7 of 8. The difference is <b>INV-206</b>: V3 only saw an amount mismatch, while V4 sees that INV-202 already used PO-502 in the same batch
(possible re-billing) and that the two BETA invoices ($8,950 + $9,150) look like a split.</p>
{fig("E2_batch_api_response_output.png", "E2: JSON returned to the calling system.")}

<h3>5.2 Scenarios for the new controls</h3>
{table(["Submitted", "Executions (core / alerts)", "Status", "Reason", "Telegram", "AI"], scen)}
{fig("E1_split_part2_INV-302_1_form_filled.png", "E1: the AP clerk form (INV-302).", "460px")}
{fig("E1_split_part2_INV-302_2_form_response.png", "E1: result shown to the clerk: split suspected. The rule counted three EPSILON invoices this week (INV-207 $500 from the batch, INV-301, INV-302).", "460px")}
<p>Gemini's note for INV-302 (guardrail {esc(split_note['ai_guardrail'])}):</p><pre>{esc(split_note['ai_commentary'])}</pre>
{fig("T4_datatable_Week10_AP_Ledger_V4.png", "Week10_AP_Ledger_V4 after all scenarios: 12 cases from the API and the form.")}

<h3>5.3 Daily digest (E3, execution #{E3['id']}, guardrail {esc(digest['ai_guardrail'])})</h3>
<pre>{esc(digest['telegram_text'])}</pre>
{fig("E3_digest_2_execution_canvas.png", "E3: ledger → deterministic summary → Gemini briefing → number guardrail → Telegram.", "820px")}

<h2>6. Problems met and how they were fixed</h2>
<h3>6.1 Gemini 503 (lab D, execution #{D0['id']})</h3>
<p>The template's <code>models/gemini-3.8-flash</code> answered "Service unavailable". A direct API check showed 3.8-flash and flash-latest overloaded, while
<code>gemini-flash-lite-latest</code> answered normally. Following the guide's troubleshooting advice ("choose another currently accessible model"), workflow D now uses
flash-lite with n8n's <i>Retry on fail</i> (3 tries, 5 s apart). Re-run #{D['id']}: success.</p>
{fig("D0_troubleshoot_503_canvas.png", "The failed run, kept as evidence.", "760px")}
<h3>6.2 Telegram "can't parse entities" (V4 alerts, first run)</h3>
<p>The V4 alert text has status codes like <code>HOLD_DUPLICATE</code>, and Telegram read the underscores as Markdown. The lab template avoids this with
<code>parse_mode: None</code>, which I had left out of my new Telegram nodes. Fixed, ledger reset, all scenarios re-run.</p>
<h3>6.3 Other setup issues</h3>
<ul><li>n8n 2.x needs Node &ge; 24, so I used a portable Node 24 rather than changing the global install.</li>
<li>n8n 2.x will only publish a workflow if the sub-workflows it calls are published, so the setup script publishes sub-workflows first.</li></ul>

<h2>7. AI boundaries and reflection</h2>
<p><b>Is this an agent?</b> No. As the guide says, these are fixed workflows with a model in an advisory slot. In V4 the model writes text only; it
cannot change a status, call a tool, approve or pay. Its output passes through code guardrails, tested in <code>tests/test_guardrails.js</code> against claims like
"has been approved for payment", requests for bank details, a different status name, and invented numbers in the digest.</p>
<p><b>Two places where deterministic rules beat LLM judgement:</b></p>
<ol><li><b>Duplicate and re-billing detection.</b> Whether supplier + reference already exists, or a PO is already used, is an exact lookup over every
earlier invoice. Rules get it right every time and can be audited; a model reading invoices one at a time cannot see the history and could be talked out of it.</li>
<li><b>Approval thresholds and split detection.</b> "&gt; $10,000" and "the sum this week &gt; $10,000" are policy, not opinion. They must give the same answer
on every run, and an auditor must be able to replay them. The model only explains why the rule fired.</li></ol>
<p><b>Limitations:</b></p>
<ul><li><b>Static fixtures (lab):</b> V3's PO master and one-row history are constants in code, so they go stale and miss real duplicates. V4 moves both into
Data Tables, but the PO table is still a manual copy, not a live ERP feed.</li>
<li><b>Guardrails check form, not meaning.</b> In the digest, Gemini wrote "the 1 manager review case worth $54,050", but $54,050 is the total across four cases
needing a manager. Each number exists in the data, so the guardrail passed it. The deterministic header above the AI text is the figure to rely on.</li>
<li>Split detection uses supplier name and a 7-day window; a real system would also match supplier ids, bank accounts and invoice dates.</li>
<li>The local n8n is not reachable from the internet (forms and the webhook work on this machine only), and the webhook has no authentication. Production would need
HTTPS, header auth and a unique constraint on supplier + reference.</li></ul>

<h2>8. Files</h2>
{table(["Path", "Contents"], [
    ["workflows/lab_*.json", "Lab workflows A&ndash;D as configured (chat id as an env expression; D on flash-lite with retries)"],
    ["workflows/v4_*.json", "The five V4 workflows (generated by tools/build_v4_workflows.js)"],
    ["execution_logs/", "Every execution: per-node status and full data, decoded from n8n's format, personal identifiers masked"],
    ["screenshots/", "Forms, canvases with run data, node outputs, Data Tables, workflow and credential lists"],
    ["data/", "Table schemas, PO master seed, API test requests and responses, CSV exports of all four Data Tables"],
    ["tests/", "classify_v4.js (rules) + 12 rule tests + 10 guardrail tests (node tests/test_*.js)"],
    ["tools/", "n8n_setup.py (rebuild), run_v4_scenarios.py, submit_form.py, capture_screenshots.py, build_v4_workflows.js"],
])}
</body></html>"""

(ROOT / "docs" / "Week10_n8n_Report.html").write_text(doc, encoding="utf-8")
print("wrote docs/Week10_n8n_Report.html")
