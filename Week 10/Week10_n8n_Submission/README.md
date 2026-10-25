# Week 10: AI workflow automation with n8n

BC3415 Week 10 lab (route: `01_n8n_Lab`). Full write-up with screenshots: **`docs/Week10_n8n_Report.pdf`**.

## What was done

1. **Deployed n8n 2.44.6 locally** (lab setup route A, without Docker: npm install with a portable Node 24) and connected my own Telegram bot and a Google Gemini key.
2. **Ran all four lab workflows** (A offline check, B intake → Data Table → Telegram, C invoice rules → Data Table → Telegram, D rules + Gemini explanation) with the guide's test cases. Every evidence-sheet checkpoint is met.
3. **Customisation: a V4 accounts-payable triage service** (five workflows) that fixes the limitations the guide lists:
   - PO master moved from JavaScript constants into a **Data Table** finance can edit
   - **Persistent duplicate check** against every earlier invoice (V3 only knew one fixture)
   - New fraud controls: **closed PO**, **PO already invoiced** (re-billing), **split invoices** under the $10k approval limit
   - **Priority routing**: P1 holds get an instant Telegram alert; P2 reviews get a Gemini explanation; P3 is logged only
   - **Guardrail** on the AI text (blocks approval/payment claims, wrong status names, bank-detail requests); the AI note is **written back to the ledger row** (the guide's suggested extension)
   - Two intake channels sharing the same rules: an **AP clerk form** and a **batch JSON API**
   - **Daily 08:30 digest** for the finance manager, with a guardrail that rejects numbers not in the data

Results: 26 executions logged, 16 Telegram messages delivered, 22 unit tests passing, 0 payments authorised.

## Folder

| Path | Contents |
|---|---|
| `workflows/lab_A..D_*.json` | Lab workflows as configured (Telegram chat id read from `$env.TELEGRAM_CHAT_ID`; D uses `gemini-flash-lite-latest` with retries after 3.8-flash returned 503) |
| `workflows/v4_*.json` | V4 workflows: two sub-workflows (core rules + ledger; alerts + Gemini) and E1 form, E2 batch API, E3 daily digest |
| `execution_logs/` | Every execution, decoded to readable JSON with a per-node summary. `D0_*` and `E0_*` are the two failures kept as troubleshooting evidence |
| `screenshots/` | Forms, canvases with run data, node outputs, the four Data Tables, workflow and credential lists |
| `data/` | Data Table schemas, PO master seed, API test requests and responses, CSV exports of all tables, the lab's schema CSVs |
| `tests/` | `classify_v4.js` (the V4 rules, copied into the Code node), `test_classify_v4.js` (12 tests), `test_guardrails.js` (10 tests) |
| `tools/` | `n8n_setup.py` rebuilds everything on a fresh n8n; `run_v4_scenarios.py`, `submit_form.py`, `capture_screenshots.py` produced the evidence; `build_v4_workflows.js` generates the V4 JSON |
| `docs/` | Report (PDF + HTML) and its generator |

## Reproduce

```
node tests/test_classify_v4.js && node tests/test_guardrails.js     # no n8n needed

# with n8n running (started with TELEGRAM_CHAT_ID and N8N_BLOCK_ENV_ACCESS_IN_NODE=false):
set N8N_OWNER_EMAIL / N8N_OWNER_PASSWORD / TELEGRAM_BOT_TOKEN / GEMINI_API_KEY
python tools/n8n_setup.py --reset-ledger     # tables, credentials, import, publish
python tools/run_v4_scenarios.py             # V4 scenarios + execution logs
```

To import by hand instead: n8n → Import from File, then bind the Telegram/Gemini credentials and select the Data Tables (schemas in `data/table_schemas.json`).

**No API keys, tokens or personal identifiers are in this folder.** Credentials live only in n8n's encrypted store; the Telegram chat id, name and username are masked in screenshots and logs. All invoice data is synthetic.
