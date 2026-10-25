"""Captures the editor evidence: executions on the canvas, node outputs, Data Tables, lists.

  python tools/capture_screenshots.py   (needs the executions listed in SHOTS to exist)
"""
import json
import sys
from pathlib import Path

from pwhelp import Browser, URL

ROOT = Path(__file__).resolve().parent.parent
IDS = json.loads((ROOT / "data" / "instance_ids.local.json").read_text())
WF, TB = IDS["workflows"], IDS["tables"]

# (file, workflow name, execution id, node to open or None)
EXECUTIONS = [
    ("B2_intake_execution_canvas.png", "Week10 V3 | B - Intake to Data Table to Telegram", 2, None),
    ("B3_intake_telegram_output.png", "Week10 V3 | B - Intake to Data Table to Telegram", 2, "Send Telegram notification"),
    ("C5_invoice_INV-203_execution_canvas.png", "Week10 V3 | C - Invoice rules to Data Table to Telegram", 4, None),
    ("C6_invoice_INV-203_classify_output.png", "Week10 V3 | C - Invoice rules to Data Table to Telegram", 4, "Classify invoice"),
    ("D0_troubleshoot_503_canvas.png", "Week10 V3 | D - Invoice rules plus Gemini explanation", 7, None),
    ("D2_gemini_execution_canvas.png", "Week10 V3 | D - Invoice rules plus Gemini explanation", 8, None),
    ("D3_gemini_join_output.png", "Week10 V3 | D - Invoice rules plus Gemini explanation", 8, "Join AI explanation with rule output"),
    ("E0_troubleshoot_telegram_markdown_canvas.png", "Week10 V4 | sub | Alerts + Gemini explanation", 11, None),
    ("E2_batch_api_execution_canvas.png", "Week10 V4 | E2 - Batch invoice API", 12, None),
    ("E2_batch_api_response_output.png", "Week10 V4 | E2 - Batch invoice API", 12, "Build API response"),
    ("V4_core_execution_canvas.png", "Week10 V4 | sub | Core rules + AP ledger", 13, None),
    ("V4_core_classify_output.png", "Week10 V4 | sub | Core rules + AP ledger", 13, "Classify invoice (V4 rules)"),
    ("V4_alerts_execution_canvas.png", "Week10 V4 | sub | Alerts + Gemini explanation", 14, None),
    ("V4_alerts_guardrail_output.png", "Week10 V4 | sub | Alerts + Gemini explanation", 14, "Guardrail + join with rule output"),
    ("E1_form_split_execution_canvas.png", "Week10 V4 | E1 - AP intake form", 18, None),
    ("E3_digest_2_execution_canvas.png", "Week10 V4 | E3 - Daily AP exception digest", 27, None),
    ("E3_digest_3_guardrail_output.png", "Week10 V4 | E3 - Daily AP exception digest", 27, "Guardrail: numbers must come from the data"),
]


def close_popups(p):
    for text in ("Production Checklist",):
        el = p.locator(f'xpath=//*[normalize-space(text())="{text}"]/following::button[1]')
        if el.count() and el.first.is_visible():
            el.first.click()
            p.wait_for_timeout(400)


def main(only=None):
    b = Browser(width=1600, height=900)
    p = b.page
    pid = b.session.get(f"{URL}/rest/projects/personal").json()["data"]["id"]

    for f, wname, ex, node in EXECUTIONS:
        if only and only not in f:
            continue
        p.goto(f"{URL}/workflow/{WF[wname]}/executions/{ex}")
        p.wait_for_timeout(4500)
        close_popups(p)
        if node:
            frame = p.frame_locator("iframe").first if p.locator("iframe").count() else p
            frame.locator(f'[data-test-id="canvas-node"][data-node-name="{node}"]').dblclick()
            p.wait_for_timeout(2500)
            json_tab = frame.locator('[data-test-id="ndv-output-panel"] [data-test-id="radio-button-json"], [data-test-id="output-panel"] [data-test-id="radio-button-json"]')
            if json_tab.count():
                json_tab.first.click()
                p.wait_for_timeout(800)
        b.shot(f)

    if not only or "tables" in only:
        for i, (name, w) in enumerate([("Week10_Intake", 1600), ("Week10_Invoice_Triage", 2600),
                                       ("Week10_PO_Master", 1600), ("Week10_AP_Ledger_V4", 3000)], 1):
            p.set_viewport_size({"width": w, "height": 900})
            p.goto(f"{URL}/projects/{pid}/datatables/{TB[name]}")
            p.wait_for_timeout(3500)
            close_popups(p)
            b.shot(f"T{i}_datatable_{name}.png")
        p.set_viewport_size({"width": 1600, "height": 900})

    if not only or "lists" in only:
        p.goto(f"{URL}/home/workflows")
        p.wait_for_timeout(3500)
        close_popups(p)
        b.shot("L1_workflow_list.png")
        p.goto(f"{URL}/home/credentials")
        p.wait_for_timeout(3000)
        close_popups(p)
        b.shot("L2_credentials_list_no_secrets.png")
    b.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
