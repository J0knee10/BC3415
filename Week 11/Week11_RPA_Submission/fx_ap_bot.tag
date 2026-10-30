// =====================================================================
// Meridian AP FX Exposure Bot  (TagUI v6 RPA flow)
// BC3415 Week 11 - RPA use case: "scrape daily FX rates and append to CSV",
// extended into the accounts-payable task it actually supports.
//
// What a person did by hand every morning, and what this bot now does:
//   1. open the ECB euro reference-rate page and note the rate date
//   2. copy today's rate for every currency we owe suppliers in (+ SGD)
//   3. screenshot the rate table as audit evidence
//   4. open each currency's chart page, read ~1 month of history,
//      screenshot the chart
//   5. append the day's rates to a running history CSV (once per date)
//   6. convert every open foreign-currency invoice into SGD, work out
//      days to due date, payment bucket and FX risk at the 1-month high
//   7. raise alerts for big FX moves and for invoices it cannot convert
//   8. build an HTML report, open it in the browser and screenshot it
//   9. append one line per run to a run log
//
// Input : input/open_invoices.csv  (synthetic Meridian AP data)
// Output: output/*.csv, output/*.html, evidence/*.png
// Run   : run_bot.cmd            (visible browser)
//         run_bot.cmd -headless  (no browser window)
//
// The bot only READS a public web page and writes local files.
// It never logs in anywhere and never makes a payment.
// JavaScript in js blocks runs in TagUI's engine (ES5: var/function only);
// dom blocks run inside Chrome.
// =====================================================================

// ---------- settings (input/bot_settings.csv; defaults below if a key is missing) ----------
// dod_alert_pct : alert when SGD per unit moves this much (%) day-on-day
// avg_alert_pct : alert when today's rate is this far (%) from its 1-month average
// history_days  : ECB fixings that count as "1 month" for average / low / high
dod_alert_pct = 0.5
avg_alert_pct = 2.0
history_days = 22
run_started = new Date()
load input/bot_settings.csv to settings_csv
js begin
var srows = settings_csv.replace(/\r/g, '').split('\n');
for (var i = 1; i < srows.length; i++) {
  var kv = srows[i].split(',');
  var v = parseFloat(kv[1]);
  if (isNaN(v)) continue;
  if (kv[0] === 'dod_alert_pct') dod_alert_pct = v;
  if (kv[0] === 'avg_alert_pct') avg_alert_pct = v;
  if (kv[0] === 'history_days') history_days = Math.round(v);
}
js finish
echo Settings: day-move alert `dod_alert_pct`%, off-average alert `avg_alert_pct`%, 1 month = `history_days` fixings

// ---------- 1. load the open invoices ----------
load input/open_invoices.csv to invoices_csv
js begin
pad2 = function (n) { return (n < 10 ? '0' : '') + n; }
iso = function (d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
stamp = function (d) { return iso(d) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()); }
money = function (x) { return x.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
csvq = function (s) { s = String(s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }
run_id = iso(run_started) + '_' + pad2(run_started.getHours()) + pad2(run_started.getMinutes()) + pad2(run_started.getSeconds());
invoices = [];
var lines = invoices_csv.replace(/\r/g, '').split('\n');
var head = lines[0].split(',');
for (var i = 1; i < lines.length; i++) {
  if (!lines[i].replace(/\s/g, '')) continue;
  var cells = lines[i].split(',');
  var inv = {};
  for (var j = 0; j < head.length; j++) inv[head[j]] = (cells[j] || '').replace(/^\s+|\s+$/g, '');
  inv.currency = inv.currency.toUpperCase();
  inv.amount = parseFloat(inv.amount);
  invoices.push(inv);
}
// currencies we need a rate for (SGD is our reporting currency, EUR is the ECB base)
need = [];
for (var k = 0; k < invoices.length; k++) {
  var c = invoices[k].currency;
  if (c !== 'SGD' && c !== 'EUR' && need.indexOf(c) < 0) need.push(c);
}
need_text = need.join(', ');
invoice_count = invoices.length;
js finish
echo Loaded `invoice_count` open invoices; currencies to look up: `need_text`

// ---------- 2. open the ECB reference-rate page ----------
https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
wait 3
// the ECB shows a cookie banner over the page; decline it once (the choice is kept in TagUI's browser profile)
dom begin
var box = document.getElementById('cookieConsent');
var no = box ? box.querySelector('button.cross') : null;
if (box && no && !box.classList.contains('hidden')) { no.click(); return 'declined'; }
return 'none';
dom finish
echo Cookie banner: `dom_result`
wait 1
read (//div[@class="jumbo-box"]//h3)[1] to ref_date_text
read //td[@id="SGD"]/../td[contains(@class,"spot")]//span[@class="rate"] to eur_sgd_text
js begin
var months = ['january','february','march','april','may','june','july','august','september','october','november','december'];
var p = ref_date_text.replace(/^\s+|\s+$/g, '').split(/\s+/);
ref_date = p[2] + '-' + pad2(months.indexOf(p[1].toLowerCase()) + 1) + '-' + pad2(parseInt(p[0], 10));
eur_rate = { 'EUR': 1, 'SGD': parseFloat(eur_sgd_text) };
missing = [];
js finish
echo ECB reference date: `ref_date` (1 EUR = `eur_sgd_text` SGD)

for n from 0 to need.length-1
  ccy = need[n]
  if present('//td[@id="' + ccy + '"]')
    read //td[@id="`ccy`"]/../td[contains(@class,"spot")]//span[@class="rate"] to rate_text
    js eur_rate[ccy] = parseFloat(rate_text)
    echo   1 EUR = `rate_text` `ccy`
  else
    js missing.push(ccy)
    echo   `ccy` is not published by the ECB - invoices in it will be flagged

dom window.scrollTo(0, 0)
snap //table[@class="forextable"] to evidence/`ref_date`_ecb_rate_table.png
snap page to evidence/`ref_date`_ecb_page.png

// ---------- 3. one month of history per currency, from each chart page ----------
// SGD first: every SGD cross rate needs EUR->SGD on the same day.
js chart_ccys = ['SGD'].concat(need.filter(function (c) { return missing.indexOf(c) < 0; }))
js history = {}
for n from 0 to chart_ccys.length-1
  ccy = chart_ccys[n]
  js ccy_lower = ccy.toLowerCase()
  https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
  wait 2
  click //td[@id="`ccy`"]/a
  wait 3
  // the chart's data script can load late: try up to 5 times before giving up on this currency's history
  js got = ''
  for attempt from 1 to 5
    dom begin
    if (typeof generateChartData !== 'function') return '';
    var data = generateChartData();
    var out = [];
    for (var i = Math.max(0, data.length - 40); i < data.length; i++) {
      var d = data[i].date;
      out.push([d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2), data[i].rate]);
    }
    return JSON.stringify(out);
    dom finish
    js got = dom_result ? String(dom_result) : ''
    if got.length > 2
      break
    wait 2
  js history[ccy] = got.length > 2 ? JSON.parse(got) : []
  js points = history[ccy].length
  snap //div[@id="chart-container"] to evidence/`ref_date`_chart_`ccy`.png
  echo   `ccy` chart page read (`points` daily rates) and captured

// ---------- 4. SGD cross rates, statistics and alerts ----------
js begin
// SGD per 1 unit of each currency, by date, from the two EUR-based series
crossSeries = function (c) {
  var sgd = {}, out = [];
  for (var i = 0; i < history['SGD'].length; i++) sgd[history['SGD'][i][0]] = history['SGD'][i][1];
  if (c === 'EUR') { for (var e = 0; e < history['SGD'].length; e++) out.push(history['SGD'][e]); return out; }
  var h = history[c] || [];
  for (var k = 0; k < h.length; k++) if (sgd[h[k][0]]) out.push([h[k][0], sgd[h[k][0]] / h[k][1]]);
  return out;
}
if (!history['SGD']) history['SGD'] = [];
stats = {};
alerts = [];
var all_ccys = ['EUR'].concat(chart_ccys.filter(function (c) { return c !== 'SGD'; }));
for (var a = 0; a < all_ccys.length; a++) {
  var c = all_ccys[a];
  var s = crossSeries(c);
  // keep only dates up to the page's reference date, then the last history_days points
  s = s.filter(function (r) { return r[0] <= ref_date; });
  var today = (c === 'EUR') ? eur_rate['SGD'] : eur_rate['SGD'] / eur_rate[c];
  var last = s.slice(-history_days);
  // previous fixing = latest date strictly before the reference date
  var prev = null;
  for (var b = s.length - 1; b >= 0; b--) if (s[b][0] < ref_date) { prev = s[b]; break; }
  var sum = 0, lo = today, hi = today;
  for (var q = 0; q < last.length; q++) { sum += last[q][1]; lo = Math.min(lo, last[q][1]); hi = Math.max(hi, last[q][1]); }
  var avg = last.length ? sum / last.length : today;
  var st = {
    ccy: c, today: today, prev_date: prev ? prev[0] : '', prev: prev ? prev[1] : today,
    avg: avg, lo: lo, hi: hi, days: last.length, first_date: last.length ? last[0][0] : ''
  };
  st.dod_pct = (st.today / st.prev - 1) * 100;
  st.vs_avg_pct = (st.today / st.avg - 1) * 100;
  st.alert = '';
  if (Math.abs(st.dod_pct) >= dod_alert_pct) st.alert = 'DAILY_MOVE';
  if (Math.abs(st.vs_avg_pct) >= avg_alert_pct) st.alert = st.alert ? st.alert + '|OFF_1M_AVERAGE' : 'OFF_1M_AVERAGE';
  // without history the statistics are only today's rate: say so rather than look reassuring
  if (!last.length) st.alert = st.alert ? st.alert + '|NO_HISTORY' : 'NO_HISTORY';
  stats[c] = st;
  if (st.alert) alerts.push(st);
}
stats['SGD'] = { ccy: 'SGD', today: 1, prev: 1, avg: 1, lo: 1, hi: 1, dod_pct: 0, vs_avg_pct: 0, alert: '', days: 0, prev_date: '', first_date: '' };
alert_count = alerts.length;
js finish
echo FX moves needing attention: `alert_count`

// ---------- 5. append today's rates to the history file (once per ECB date) ----------
load output/fx_rates_history.csv to history_csv
js begin
history_lines = [];
var keys = Object.keys(stats).sort();
for (var i = 0; i < keys.length; i++) {
  var st = stats[keys[i]];
  if (st.ccy === 'SGD') continue;
  if (history_csv.indexOf('\n' + ref_date + ',' + st.ccy + ',') >= 0) continue;
  var eur = st.ccy === 'EUR' ? 1 : eur_rate[st.ccy];
  history_lines.push([ref_date, st.ccy, eur, st.today.toFixed(6), st.dod_pct.toFixed(3), 'ECB euro reference rate', stamp(run_started)].join(','));
}
history_new = history_lines.length;
history_block = history_lines.join('\n');
js finish
if history_new > 0
  quiet_mode = true
  write `history_block` to output/fx_rates_history.csv
  quiet_mode = false
  echo Added `history_new` rows for `ref_date` to output/fx_rates_history.csv
else
  echo Rates for `ref_date` were already in the history file - nothing appended

// ---------- 6. convert open invoices to SGD ----------
js begin
var today0 = new Date(run_started.getFullYear(), run_started.getMonth(), run_started.getDate());
rows = [];
totals = {};
exposure_sgd = 0; risk_sgd = 0; exceptions = 0; due_week_sgd = 0; overdue_count = 0;
for (var i = 0; i < invoices.length; i++) {
  var v = invoices[i];
  var st = stats[v.currency];
  var dp = v.due_date.split('-');
  var due = new Date(parseInt(dp[0], 10), parseInt(dp[1], 10) - 1, parseInt(dp[2], 10));
  var days = Math.round((due - today0) / 86400000);
  var bucket = days < 0 ? 'OVERDUE' : (days <= 7 ? 'DUE_THIS_WEEK' : (days <= 30 ? 'DUE_30_DAYS' : 'LATER'));
  var r = { invoice_id: v.invoice_id, supplier: v.supplier, currency: v.currency, amount: v.amount, due_date: v.due_date,
            days_to_due: days, bucket: bucket, rate: '', sgd: '', sgd_hi: '', risk: '', status: '', note: '' };
  if (!st || isNaN(v.amount) || v.amount <= 0) {
    r.status = 'EXCEPTION';
    r.note = !st ? 'No ECB reference rate for ' + v.currency + ' - check supplier master / convert manually' : 'Invalid amount';
    exceptions++;
  } else {
    r.rate = st.today;
    r.sgd = v.amount * st.today;
    r.sgd_hi = v.amount * st.hi;
    r.risk = r.sgd_hi - r.sgd;
    r.status = st.alert ? 'CONVERTED_FX_ALERT' : 'CONVERTED';
    r.note = st.alert ? v.currency + ' ' + st.alert.replace('|', ' + ') + ' (' + st.dod_pct.toFixed(2) + '% d/d)' : '';
    exposure_sgd += r.sgd; risk_sgd += r.risk;
    if (bucket === 'OVERDUE' || bucket === 'DUE_THIS_WEEK') due_week_sgd += r.sgd;
    if (!totals[v.currency]) totals[v.currency] = { n: 0, amount: 0, sgd: 0, risk: 0 };
    totals[v.currency].n++; totals[v.currency].amount += v.amount; totals[v.currency].sgd += r.sgd; totals[v.currency].risk += r.risk;
  }
  if (bucket === 'OVERDUE') overdue_count++;
  rows.push(r);
}
var out = ['invoice_id,supplier,currency,amount,due_date,days_to_due,payment_bucket,sgd_per_unit,rate_date,amount_sgd,amount_sgd_at_1m_high,fx_risk_sgd,status,note'];
for (var k = 0; k < rows.length; k++) {
  var x = rows[k];
  out.push([x.invoice_id, csvq(x.supplier), x.currency, x.amount.toFixed(2), x.due_date, x.days_to_due, x.bucket,
            x.rate === '' ? '' : x.rate.toFixed(6), x.rate === '' ? '' : ref_date,
            x.sgd === '' ? '' : x.sgd.toFixed(2), x.sgd_hi === '' ? '' : x.sgd_hi.toFixed(2), x.risk === '' ? '' : x.risk.toFixed(2),
            x.status, csvq(x.note)].join(','));
}
exposure_csv = out.join('\n');
exposure_text = money(exposure_sgd); risk_text = money(risk_sgd); due_week_text = money(due_week_sgd);
js finish
quiet_mode = true
dump `exposure_csv` to output/ap_fx_exposure_`ref_date`.csv
quiet_mode = false
echo Open AP exposure: SGD `exposure_text`  (FX risk at 1-month high: SGD `risk_text`; exceptions: `exceptions`)

// ---------- 7. alerts file ----------
js begin
var al = [];
for (var i = 0; i < alerts.length; i++) {
  var s = alerts[i];
  al.push([stamp(run_started), ref_date, s.ccy, 'FX_MOVE', s.alert, s.today.toFixed(6), s.dod_pct.toFixed(3), s.vs_avg_pct.toFixed(3),
           csvq('SGD per ' + s.ccy + ' moved ' + s.dod_pct.toFixed(2) + '% vs ' + s.prev_date + ', ' + s.vs_avg_pct.toFixed(2) + '% vs 1-month average')].join(','));
}
for (var k = 0; k < rows.length; k++) {
  if (rows[k].status === 'EXCEPTION') al.push([stamp(run_started), ref_date, rows[k].currency, 'INVOICE_EXCEPTION', rows[k].invoice_id, '', '', '', csvq(rows[k].note)].join(','));
  if (rows[k].bucket === 'OVERDUE') al.push([stamp(run_started), ref_date, rows[k].currency, 'OVERDUE_INVOICE', rows[k].invoice_id, '', '', '', csvq(rows[k].supplier + ' was due ' + rows[k].due_date)].join(','));
}
alert_lines = al.length;
alert_block = al.join('\n');
js finish
if alert_lines > 0
  quiet_mode = true
  write `alert_block` to output/fx_alerts.csv
  quiet_mode = false
  echo `alert_lines` alert lines written to output/fx_alerts.csv

// ---------- 8. HTML report, opened in the browser and captured ----------
js begin
pct = function (x) { return (x >= 0 ? '+' : '') + x.toFixed(2) + '%'; }
var h = [];
h.push('<!doctype html><html><head><meta charset="utf-8"><title>AP FX exposure ' + ref_date + '</title><style>');
h.push('body{font-family:Segoe UI,Arial,sans-serif;margin:24px;max-width:1180px;color:#1d2433;background:#fff}h1{font-size:22px;margin:0 0 4px}');
h.push('.sub{color:#5a6475;margin-bottom:18px}.tiles{display:flex;gap:12px;margin:12px 0 20px;flex-wrap:wrap}');
h.push('.tile{border:1px solid #d9dee7;border-radius:8px;padding:10px 14px;min-width:170px}.tile b{display:block;font-size:20px}');
h.push('table{border-collapse:collapse;width:100%;margin:6px 0 22px;font-size:13px}th,td{border-bottom:1px solid #e3e7ee;padding:6px 8px;text-align:left}');
h.push('th{background:#f3f5f9}td.n{text-align:right;font-variant-numeric:tabular-nums}.alert{color:#a4161a;font-weight:600}.ok{color:#1b7f3b}');
h.push('h2{font-size:16px;margin:18px 0 4px}.foot{color:#5a6475;font-size:12px}</style></head><body>');
h.push('<h1>Meridian AP &middot; foreign-currency exposure</h1>');
h.push('<div class="sub">ECB euro reference rates of <b>' + ref_date + '</b> &middot; bot run ' + stamp(run_started) + ' &middot; synthetic data</div>');
h.push('<div class="tiles"><div class="tile">Open invoices<b>' + invoice_count + '</b></div>');
h.push('<div class="tile">Exposure in SGD<b>' + exposure_text + '</b></div>');
h.push('<div class="tile">Due this week / overdue<b>' + due_week_text + '</b></div>');
h.push('<div class="tile">FX risk at 1-month high<b>' + risk_text + '</b></div>');
h.push('<div class="tile">Exceptions<b class="' + (exceptions ? 'alert' : 'ok') + '">' + exceptions + '</b></div></div>');
h.push('<h2>Rates used (SGD per 1 unit)</h2><table><tr><th>Currency</th><th>Today</th><th>Previous (' + (stats['EUR'] ? stats['EUR'].prev_date : '') + ')</th><th>Day change</th><th>1-month avg</th><th>vs avg</th><th>1-month low</th><th>1-month high</th><th>Alert</th></tr>');
var ks = Object.keys(stats).sort();
for (var i = 0; i < ks.length; i++) {
  var s = stats[ks[i]];
  if (s.ccy === 'SGD') continue;
  h.push('<tr><td>' + s.ccy + '</td><td class="n">' + s.today.toFixed(5) + '</td><td class="n">' + s.prev.toFixed(5) + '</td><td class="n">' + pct(s.dod_pct) +
         '</td><td class="n">' + s.avg.toFixed(5) + '</td><td class="n">' + pct(s.vs_avg_pct) + '</td><td class="n">' + s.lo.toFixed(5) + '</td><td class="n">' + s.hi.toFixed(5) +
         '</td><td class="' + (s.alert ? 'alert' : 'ok') + '">' + (s.alert || 'none') + '</td></tr>');
}
h.push('</table><h2>Open invoices converted to SGD</h2><table><tr><th>Invoice</th><th>Supplier</th><th>Ccy</th><th>Amount</th><th>Due</th><th>Bucket</th><th>SGD</th><th>FX risk</th><th>Status</th></tr>');
for (var k = 0; k < rows.length; k++) {
  var x = rows[k];
  h.push('<tr><td>' + x.invoice_id + '</td><td>' + x.supplier + '</td><td>' + x.currency + '</td><td class="n">' + money(x.amount) + '</td><td>' + x.due_date + ' (' + x.days_to_due + 'd)</td><td' +
         (x.bucket === 'OVERDUE' ? ' class="alert"' : '') + '>' + x.bucket + '</td><td class="n">' + (x.sgd === '' ? '&ndash;' : money(x.sgd)) + '</td><td class="n">' + (x.risk === '' ? '&ndash;' : money(x.risk)) +
         '</td><td class="' + (x.status === 'CONVERTED' ? 'ok' : 'alert') + '">' + x.status + (x.note ? '<br><span class="foot">' + x.note + '</span>' : '') + '</td></tr>');
}
h.push('</table><h2>Totals by currency</h2><table><tr><th>Currency</th><th>Invoices</th><th>Amount</th><th>SGD</th><th>FX risk</th></tr>');
var tk = Object.keys(totals).sort();
for (var t = 0; t < tk.length; t++) {
  var tt = totals[tk[t]];
  h.push('<tr><td>' + tk[t] + '</td><td class="n">' + tt.n + '</td><td class="n">' + money(tt.amount) + '</td><td class="n">' + money(tt.sgd) + '</td><td class="n">' + money(tt.risk) + '</td></tr>');
}
h.push('</table><p class="foot">FX risk = extra SGD needed if the invoice were paid at the highest rate of the last ' + history_days + ' ECB fixings instead of today\'s. ECB reference rates are for information only; the bank\'s dealt rate on the payment day will differ. This report is advisory: it does not approve or make payments.</p></body></html>');
report_html = h.join('\n');
report_file = 'output/AP_FX_Report_' + ref_date + '.html';
js finish
quiet_mode = true
dump `report_html` to `report_file`
quiet_mode = false
// show the report in the bot's browser and screenshot it as the run's evidence
// (Chrome won't let a web page open a local file:// URL, so the HTML is written into a blank tab)
about:blank
dom_json = report_html
dom begin
document.open(); document.write(dom_json); document.close();
dom finish
wait 1
snap //html to evidence/`ref_date`_report.png
echo Report saved to `report_file`

// ---------- 9. run log ----------
js begin
var secs = ((new Date()) - run_started) / 1000;
run_line = [stamp(run_started), ref_date, invoice_count, need.length, missing.length, alert_count, exceptions, exposure_sgd.toFixed(2), risk_sgd.toFixed(2), history_new, secs.toFixed(1), 'SUCCESS'].join(',');
js finish
write `run_line` to output/run_log.csv
echo Run complete - `run_line`
