# Meridian AP FX Exposure Bot (TagUI RPA)

BC3415 Week 11, RPA task. Use case: **"scrape daily FX rates and append to a CSV"** (idea 2 in the brief), taken through to the accounts-payable job it supports: converting open foreign-currency supplier invoices into SGD each morning, with evidence and alerts.

Full write-up: `docs/RPA_Project_Report.pdf`.

## What the bot does

| # | Step | TagUI steps used |
|---|---|---|
| 1 | Read settings and the open-invoice list | `load`, `js` |
| 2 | Open the ECB euro reference-rate page, decline the cookie banner, read the rate date and the rate for every currency owed (+ SGD) | URL, `dom`, `read` (XPath), `for`, `if present()` |
| 3 | Screenshot the rate table and the page as audit evidence | `snap` |
| 4 | For each currency, click through to its chart page, pull about 2 months of daily rates from the page, screenshot the chart (retries up to 5 times if the chart loads late) | `click`, `dom`, `snap`, `for` / `break` |
| 5 | Append the day's rates to `output/fx_rates_history.csv`, **once per ECB date** (re-runs don't duplicate) | `load`, `write` |
| 6 | Convert every invoice to SGD; days to due date, payment bucket, FX risk at the 1-month high | `js` |
| 7 | Write alerts: big FX moves, overdue invoices, currencies the ECB doesn't publish | `write` |
| 8 | Build an HTML report, show it in the bot's browser and screenshot it | `dump`, `dom`, `snap` |
| 9 | Append one line to the run log | `write` |

The bot only reads a public web page and writes local files. It does not log in anywhere and makes no payments.

## Folder

```
fx_ap_bot.tag                  the RPA script (TagUI v6)
run_bot.cmd                    launcher:  run_bot.cmd   or   run_bot.cmd -headless
input/open_invoices.csv        10 synthetic Meridian AP invoices (7 currencies + one bad code, XYZ)
input/bot_settings.csv         alert thresholds the AP team can change without touching the script
output/                        exposure CSV, HTML report, rate history, alerts, run log  (from the runs below)
evidence/                      screenshots taken by the bot, console logs of each run, independent check
evidence/alert_test/           run with a tighter threshold to show the FX-alert branch working
tools/verify_against_ecb_xml.py   recomputes every SGD figure from the ECB's XML feed and compares (PASS)
tools/patch_tagui_2026.ps1     fixes TagUI 6.110 for current Chrome / Windows 11 (see below)
docs/                          project report (PDF + HTML source)
```

## Runs recorded in `evidence/`

| Run | Purpose | Result |
|---|---|---|
| 1 | first run, empty history | 7 rates added; exposure SGD 229,056.96; 1 exception (XYZ), 1 overdue (GBP) |
| 2 | same ECB date again | 0 history rows added (no duplicates), same figures |
| 3 | off-average threshold lowered to 0.5% | EUR, JPY, GBP flagged `OFF_1M_AVERAGE`; their invoices marked `CONVERTED_FX_ALERT` |
| 4 | normal settings again | final outputs in `output/` |
| check | `tools/verify_against_ecb_xml.py` | 10 of 10 invoices match the ECB XML feed to the cent: **PASS** |

## How to run it

1. Install TagUI v6.110 for Windows (https://github.com/aisingapore/TagUI/releases), unzip to `C:\tagui`. Google Chrome must be installed.
2. Patch it once for current Chrome / Windows 11:
   `powershell -ExecutionPolicy Bypass -File tools\patch_tagui_2026.ps1 -TagUISrc C:\tagui\src`
3. `run_bot.cmd` (watch it) or `run_bot.cmd -headless`.
4. Optional check: `python tools\verify_against_ecb_xml.py` (standard library only).

To run it every weekday morning: Task Scheduler, action `run_bot.cmd -headless`, start in this folder.

### Why TagUI needed patching

TagUI's last release (v6.110, June 2022) no longer runs as shipped on Windows 11 25H2 with Chrome 156. Five problems were found and fixed while building the bot; `tools/patch_tagui_2026.ps1` applies all of them and is safe to re-run:

1. Chrome now rejects DevTools websocket connections without `--remote-allow-origins=*` (TagUI hangs at "listening for inputs").
2. `wmic.exe` is gone from Windows 11; TagUI used it to find and close its Chrome. Replaced with a PowerShell helper.
3. The PATH check looks for `casperjs`, but the Windows package ships `casperjs.exe` ("'casperjs' is not recognized").
4. `find /i` can resolve to Git's Unix `find` and scan the whole drive. Pinned to Windows' `find.exe`.
5. Element screenshots used viewport coordinates and came out blank below the fold. Now uses page coordinates.

## Data and limits

- Invoices are synthetic. Rates are real ECB reference rates (rate date 23 Oct 2026, read on 26 Oct 2026).
- ECB reference rates are published around 16:00 CET, which is late evening in Singapore, so a 09:00 SGT run uses the previous business day's fixing. They are for information; the bank's dealt rate on payment day will differ.
- SGD cross rates are derived from two EUR rates (SGD per X = EUR/SGD ÷ EUR/X).
- The bot depends on the ECB page layout (table ids, chart script). If the ECB redesigns the page the `read` steps fail loudly rather than return wrong numbers, and the XML check would catch a silent change.
