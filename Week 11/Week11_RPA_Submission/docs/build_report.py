"""Builds docs/RPA_Project_Report.html from the bot's real outputs and evidence.

Figures are read from output/ and evidence/, not typed in, so the report always
matches the last runs. Print to PDF with any browser (or Edge headless).
Standard library only:  python docs/build_report.py
"""
import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def table(headers, body, num=()):
    h = "".join(f"<th>{html.escape(x)}</th>" for x in headers)
    b = "".join(
        "<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{html.escape(str(c))}</td>' for i, c in enumerate(r)) + "</tr>"
        for r in body)
    return f"<table><tr>{h}</tr>{b}</table>"


def fig(rel, caption, width=""):
    style = f' style="max-width:{width}"' if width else ""
    return f'<figure><img src="../{rel}"{style}><figcaption>{html.escape(caption)}</figcaption></figure>'


exposure_path = sorted((ROOT / "output").glob("ap_fx_exposure_*.csv"))[-1]
rate_date = exposure_path.stem.rsplit("_", 1)[-1]
exposure = rows(exposure_path)
runs = rows(ROOT / "output" / "run_log.csv")
history = rows(ROOT / "output" / "fx_rates_history.csv")
alerts = rows(ROOT / "output" / "fx_alerts.csv")
test_exp = rows(ROOT / "evidence" / "alert_test" / "run3_alert_test_exposure.csv")
verify = (ROOT / "evidence" / "verification_vs_ecb_xml.txt").read_text(encoding="utf-8").strip()
verdict = re.search(r"(\d+) invoices checked, (\d+) mismatches -> (\w+)", verify)
final = runs[-1]
total_sgd = float(final["exposure_sgd"])
risk_sgd = float(final["fx_risk_sgd"])
durations = [float(r["duration_s"]) for r in runs]
labels = ["1: first run", "2: same date again", "3: alert test (0.5%)", "4: final, normal settings"]

css = """
:root{--ink:#1d2433;--mute:#5a6475;--line:#e3e7ee;--head:#f3f5f9;--accent:#0b5cad;--bad:#a4161a;--good:#1b7f3b}
body{font-family:'Segoe UI',Arial,sans-serif;color:var(--ink);background:#fff;max-width:960px;margin:28px auto;padding:0 20px;line-height:1.45;font-size:14px}
h1{font-size:24px;margin:0}h2{font-size:18px;margin:28px 0 8px;border-bottom:2px solid var(--line);padding-bottom:4px}h3{font-size:15px;margin:18px 0 6px}
.sub{color:var(--mute);margin:4px 0 18px}table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}th{background:var(--head)}td.n{text-align:right;font-variant-numeric:tabular-nums}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}.tile{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:150px}.tile b{display:block;font-size:19px}
figure{margin:12px 0 18px}figure img{max-width:100%;border:1px solid var(--line)}figcaption{color:var(--mute);font-size:12px;margin-top:4px}
pre{background:#f7f8fa;border:1px solid var(--line);padding:10px;font-size:11.5px;overflow-x:auto;white-space:pre}
.pass{color:var(--good);font-weight:600}.bad{color:var(--bad);font-weight:600}ol li,ul li{margin:3px 0}
@media print{body{margin:0 auto}h2{break-after:avoid}figure,table{break-inside:avoid}}
"""

exp_body = [[r["invoice_id"], r["supplier"], r["currency"], f'{float(r["amount"]):,.2f}', r["due_date"], r["payment_bucket"],
             f'{float(r["amount_sgd"]):,.2f}' if r["amount_sgd"] else "-", f'{float(r["fx_risk_sgd"]):,.2f}' if r["fx_risk_sgd"] else "-",
             r["status"]] for r in exposure]
test_changed = [[r["invoice_id"], r["currency"], r["status"], r["note"]] for r in test_exp if r["status"] == "CONVERTED_FX_ALERT"]
run_body = [[labels[i] if i < len(labels) else str(i + 1), r["run_started"], r["rate_date"], r["fx_alerts"], r["invoice_exceptions"],
             f'{float(r["exposure_sgd"]):,.2f}', r["history_rows_added"], r["duration_s"], r["result"]] for i, r in enumerate(runs)]
hist_body = [[r["rate_date"], r["currency"], r["eur_rate"], r["sgd_per_unit"], r["day_change_pct"]] for r in history]
alert_body = [[r["logged_at"], r["currency"], r["alert_type"], r["detail"], r["message"]] for r in alerts]

doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Meridian AP FX Exposure Bot</title><style>{css}</style></head><body>
<h1>Meridian AP FX Exposure Bot</h1>
<div class="sub">BC3415 Week 11 &middot; RPA project &middot; TagUI v6 &middot; Jonathan Low &middot; ECB rate date {rate_date}</div>

<h2>1. Summary</h2>
<p>An RPA bot that does a finance team's morning foreign-exchange routine: it reads the European Central Bank's reference rates
from the ECB website, keeps a daily rate history, converts every open foreign-currency supplier invoice into SGD, measures the FX risk,
raises alerts and saves screenshots as audit evidence. It is built on idea 2 from the brief ("scrape daily FX rates and append to a CSV")
and carried through to the accounts-payable task that the rates are needed for.</p>
<div class="tiles">
<div class="tile">Invoices processed<b>{final["invoices"]}</b></div>
<div class="tile">Currencies read live<b>{int(final["currencies_needed"]) - int(final["currencies_missing"])} + SGD</b></div>
<div class="tile">Open AP in SGD<b>{total_sgd:,.2f}</b></div>
<div class="tile">FX risk at 1-month high<b>{risk_sgd:,.2f}</b></div>
<div class="tile">Run time<b>{min(durations):.0f}&ndash;{max(durations):.0f} s</b></div>
<div class="tile">Check vs ECB XML<b class="{'pass' if verdict and verdict.group(3) == 'PASS' else 'bad'}">{verdict.group(3) if verdict else 'n/a'}</b></div>
</div>

<h2>2. Business problem</h2>
<p>Meridian (the fictional company used in the Week 10 n8n lab) buys from suppliers in Europe, the US, Japan, Malaysia, China, the UK and Australia,
and reports in SGD. Before each payment run an AP analyst:</p>
<ol><li>opens the ECB reference-rate page and copies the rate for each currency into a spreadsheet;</li>
<li>works out SGD cross rates (the ECB quotes everything against the euro);</li>
<li>converts each open invoice, sorts them by due date and spots overdue ones;</li>
<li>checks whether any currency has moved sharply, which changes how much SGD to set aside;</li>
<li>saves a screenshot of the source page so auditors can see which rates were used.</li></ol>
<p>That takes roughly 20&ndash;30 minutes a day, and copy-typing rates is a known source of errors (a JPY rate of 0.008153 is easy to mistype).
It is rule-based, repetitive, done in a browser and a spreadsheet, and has no judgement in it until the exceptions: a good fit for RPA.</p>
{table(["", "Manual (as-is)", "Bot (to-be)"], [
    ["Time per day", "about 20-30 min of analyst time (estimate)", f"about {sum(durations) / len(durations):.0f} s unattended (measured)"],
    ["Rates", "typed by hand", "read from the page's own elements"],
    ["Audit evidence", "screenshot if remembered", "rate table, page and every chart captured each run"],
    ["History", "spreadsheet tab, if kept", "CSV appended once per ECB date (re-runs safe)"],
    ["Exceptions", "noticed or not", "unknown currency, overdue invoice and FX moves written to an alerts file"],
    ["Who decides", "analyst", "analyst: the bot prepares numbers, it approves nothing"]])}

<h2>3. How the bot works</h2>
{fig("evidence/" + rate_date + "_ecb_rate_table.png", "Step 2-3: the ECB rate table, captured by the bot (snap of //table[@class='forextable']).", "340px")}
<ol>
<li><b>Load inputs.</b> <code>input/open_invoices.csv</code> (10 synthetic invoices in 7 currencies plus one bad code, XYZ) and
<code>input/bot_settings.csv</code> (alert thresholds the AP team can change without editing the script).</li>
<li><b>Read today's rates.</b> Opens the ECB page, declines the cookie banner, reads the reference date heading and, for each currency, the
spot rate using XPath anchored on the table row id (<code>//td[@id="USD"]/../td[contains(@class,"spot")]//span[@class="rate"]</code>).
A currency missing from the table (XYZ) is recorded rather than crashing the run.</li>
<li><b>Evidence.</b> Screenshots of the rate table and the whole page.</li>
<li><b>History per currency.</b> For each currency the bot clicks through to its chart page and reads the last ~40 daily rates from the
page's own chart data (<code>generateChartData()</code>, via a <code>dom</code> step), then screenshots the chart. The chart script sometimes
loads late, so the read is retried up to 5 times; this was added after a real failure during testing.</li>
<li><b>Cross rates and statistics.</b> SGD per unit = (EUR&rarr;SGD) &divide; (EUR&rarr;currency), for today and every historical date.
Day-on-day change, 1-month (22 fixings) average, low and high.</li>
<li><b>History file.</b> Appends today's rates to <code>output/fx_rates_history.csv</code> only if that ECB date is not already there.</li>
<li><b>Invoices.</b> Amount in SGD, days to due, bucket (overdue / this week / 30 days / later), and FX risk = extra SGD if paid at the 1-month high.</li>
<li><b>Alerts.</b> FX move &ge; 0.5% day-on-day or &ge; 2% from the 1-month average; overdue invoices; unsupported currencies.</li>
<li><b>Report.</b> Builds an HTML report, shows it in the bot's browser and screenshots it; writes one line to <code>output/run_log.csv</code>.</li>
</ol>
{fig("evidence/" + rate_date + "_chart_USD.png", "Step 4: USD chart page captured after the bot clicked through from the rate table.", "640px")}

<h2>4. Results</h2>
<h3>Report produced by the final run</h3>
{fig("evidence/" + rate_date + "_report.png", "Step 9: the bot's report, opened in its browser and captured.")}
<h3>Open invoices in SGD (output/{exposure_path.name})</h3>
{table(["Invoice", "Supplier", "Ccy", "Amount", "Due", "Bucket", "SGD", "FX risk", "Status"], exp_body, num=(3, 6, 7))}
<h3>Runs (output/run_log.csv)</h3>
{table(["Run", "Started", "Rate date", "FX alerts", "Exceptions", "Exposure SGD", "History rows added", "Seconds", "Result"], run_body, num=(3, 4, 5, 6, 7))}
<p>Run 2 repeated run 1 on the same ECB date and added no history rows, so the bot can be re-run safely after a failure.
Run 3 lowered the off-average threshold to 0.5% to exercise the alert branch (the market was calm, so 2% did not trigger):</p>
{table(["Invoice", "Ccy", "Status in run 3", "Note"], test_changed)}
{fig("evidence/alert_test/run3_alert_test_report.png", "Run 3: alert rows highlighted in the report.", "760px")}
<h3>Rate history (output/fx_rates_history.csv)</h3>
{table(["Rate date", "Currency", "Units per EUR", "SGD per unit", "Day change %"], hist_body, num=(2, 3, 4))}
<h3>Alerts written (output/fx_alerts.csv)</h3>
{table(["Logged", "Ccy", "Type", "Detail", "Message"], alert_body)}

<h2>5. Is it right? Independent check</h2>
<p>The bot's figures come from scraping web pages, so a second, independent route was used to check them: the ECB also publishes the same
rates as an XML file for machines. <code>tools/verify_against_ecb_xml.py</code> downloads it, recomputes every SGD amount and FX-risk figure,
and compares them with the bot's CSV.</p>
<pre>{html.escape(verify)}</pre>

<h2>6. Controls and design choices</h2>
<ul>
<li><b>Read-only.</b> The bot reads a public page and writes local files. No logins, no credentials, no payments.</li>
<li><b>Re-runnable.</b> History is keyed on ECB date; repeating a run does not duplicate rows (run 2).</li>
<li><b>Fails loudly.</b> Missing elements stop a <code>read</code> step with an error instead of producing a zero; an unknown currency becomes an
<code>EXCEPTION</code> row for a person to handle.</li>
<li><b>Evidence every run.</b> Screenshots of the table, page, each chart and the report, plus the console log of each run.</li>
<li><b>Settings outside the code.</b> Thresholds live in a CSV the AP team can edit.</li>
<li><b>Human decision kept.</b> The report says it is advisory; FX risk is a planning number, not a hedge instruction.</li>
</ul>

<h2>7. Building it: problems met and fixed</h2>
<p>TagUI's last release (v6.110, June 2022) does not run as shipped on Windows 11 25H2 with Chrome 156. Five fixes were needed, now packaged
as <code>tools/patch_tagui_2026.ps1</code> (tested on the original files, safe to re-run):</p>
<ol>
<li>Chrome rejects TagUI's DevTools websocket without <code>--remote-allow-origins=*</code>: TagUI hung at "listening for inputs".</li>
<li><code>wmic.exe</code> has been removed from Windows 11; TagUI used it to find and close its Chrome. Replaced with a PowerShell helper.</li>
<li>TagUI's PATH check looks for <code>casperjs</code> but the Windows package ships <code>casperjs.exe</code>: "'casperjs' is not recognized".</li>
<li><code>find /i</code> resolved to Git's Unix <code>find</code> and scanned the C: drive. Pinned to Windows' <code>find.exe</code>.</li>
<li>Element screenshots were clipped with viewport coordinates, so anything below the fold came out blank. Switched to page coordinates.</li>
</ol>
<p>In the flow itself: TagUI wraps each step in its own function, so helper functions had to be global; Chrome blocks a web page from opening a
local <code>file://</code> report, so the report HTML is written into a blank tab instead; and the chart-data read got a retry loop.</p>

<h2>8. Limits and next steps</h2>
<ul>
<li>ECB reference rates are fixed around 16:00 CET (late evening in Singapore), so a 09:00 SGT run uses the previous business day's rate.
They are indicative; the bank's dealt rate on payment day will differ.</li>
<li>The bot depends on the ECB page layout. A redesign breaks the <code>read</code> steps (loudly); the XML check would catch a silent change.</li>
<li>Next: read invoices straight from the AP system export instead of a CSV, schedule it in Task Scheduler at 09:00, and send the alerts file to the
team chat (the Week 10 n8n workflow already has a Telegram channel that could receive it).</li>
</ul>
<p class="sub">Files: <code>fx_ap_bot.tag</code> (script), <code>run_bot.cmd</code>, <code>input/</code>, <code>output/</code>, <code>evidence/</code>,
<code>tools/</code>. All invoice data is synthetic; exchange rates are real ECB reference rates.</p>
</body></html>"""

(DOCS / "RPA_Project_Report.html").write_text(doc, encoding="utf-8")
print("wrote", DOCS / "RPA_Project_Report.html")
