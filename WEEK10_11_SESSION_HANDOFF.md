# Week 10 + Week 11 labs: session handoff

Last session: 26 October 2026 (desktop, `D:\Jon\Uni\BC3415`). **Both tasks are finished. Upload the two zips.**

| Task | Upload this | Write-up |
|---|---|---|
| Week 10: n8n workflow (lab `01_n8n_Lab`) | `Week 10/BC3415_Week10_n8n_Submission.zip` | `Week 10/Week10_n8n_Submission/docs/Week10_n8n_Report.pdf` |
| Week 11: RPA script (TagUI) | `Week 11/BC3415_Week11_RPA_Submission.zip` | `Week 11/Week11_RPA_Submission/docs/RPA_Project_Report.pdf` |

The zips are built from the two `*_Submission/` folders and scanned: no API key, bot token, chat id, Telegram username or n8n password inside (0 hits).
The Render.com line in the Week 11 brief was a typo (user confirmed), so Week 11 is RPA only.

## Week 10: what's in it

- n8n 2.44.6 running locally (no Docker), with the Telegram bot `@bc3415_smishing_bot` and the Gemini key from `Project/Indiv/.env`.
- Lab workflows A–D all run with the guide's cases (A matches Appendix A; B/C/D sent Telegram messages).
- Customisation "V4 AP triage service" (5 workflows): PO master as a Data Table, persistent duplicate check, closed-PO / PO-re-billing / split-invoice controls,
  P1/P2/P3 routing, a Gemini note behind a guardrail that is written back to the ledger, a form + batch API, and a daily 08:30 digest.
- 26 executions logged, 16 Telegram messages, 22 unit tests (`node tests/test_classify_v4.js`, `node tests/test_guardrails.js`).
- Two real failures kept as troubleshooting evidence: Gemini 3.8 Flash 503 (switched D to `gemini-flash-lite-latest` + retries) and a Telegram Markdown parse error (`parse_mode: None`).
- Caveat written into the report: the digest guardrail checks that numbers come from the data, not that they are paired correctly (Gemini called $54,050 "1 case"; it is 4).

## Week 11: what's in it

- `fx_ap_bot.tag`: reads live ECB reference rates, keeps a rate history (once per ECB date), converts 10 synthetic invoices to SGD, FX risk, alerts, screenshots, HTML report, run log.
- 4 recorded runs + an alert test; `tools/verify_against_ecb_xml.py` re-checks every figure against the ECB XML feed: PASS (10/10).
- TagUI 6.110 needed 5 fixes for Chrome 156 / Windows 11 25H2, packaged as `tools/patch_tagui_2026.ps1`.

## Local runtimes (gitignored, only on the desktop)

All under `BC3415/_runtime/` (paths without spaces on purpose; TagUI breaks on spaces):

| Folder | What | Start |
|---|---|---|
| `node24/` | portable Node 24.22.1 (n8n 2.x needs >= 24; global Node 22 untouched) | – |
| `n8n/` | npm install of n8n, data in `n8n/data/.n8n` (SQLite + encryption key) | `powershell -File _runtime\n8n\start_n8n.ps1` then http://localhost:5678 |
| `n8n/local_secrets.env` | TELEGRAM_CHAT_ID, n8n owner login, screenshot redaction tokens | read by `start_n8n.ps1` |
| `tagui/` | TagUI 6.110, already patched | `Week 11\Week11_RPA_Submission\run_bot.cmd` |
| `pwvenv/` | Python venv with Playwright + requests (uses installed Edge; the course `.venv` was not changed) | – |

n8n was left running at the end of the session; it can simply be closed. The E3 digest is published, so if n8n is started on a weekday it sends a digest at 08:30.

To rebuild n8n elsewhere: start n8n, then `python tools/n8n_setup.py --reset-ledger` with N8N_OWNER_EMAIL / N8N_OWNER_PASSWORD / TELEGRAM_BOT_TOKEN / GEMINI_API_KEY set
(see `Week 10/Week10_n8n_Submission/README.md`). The laptop already has the same keys in `Project/Indiv/.env`.

## Git

Everything is pushed (26 Oct, on request "push everything"):
- **`indiv-submission`** (now on GitHub for the first time): the two individual-project commits, a commit with the Week 10/11 work + group brief +
  GAI declarations + group handoff, and a merge of `week10-11-labs`. Working tree clean.
- **`week10-11-labs`**: the Week 10/11 work alone, branched from `main`.
- **`main`** was not changed. Merge `indiv-submission` into `main` on GitHub if everything should be on the default branch.
- **`backup-before-fix` was deliberately NOT pushed**: it contains a 159 MB zip (over GitHub's 100 MB limit) and the past-assignments
  reference pack, which includes other students' projects and `.env` files.

## Possible next steps (optional)

- Record a short screen capture of the TagUI bot running (`run_bot.cmd`, visible browser) or of an n8n form submission, if a demo video is wanted.
- Merge `indiv-submission` into `main`.
