"""Runs the V4 test scenarios against the live n8n and saves every execution (sub-workflows too).

Start from an empty ledger:  python tools/n8n_setup.py --reset-ledger
Then:                         python tools/run_v4_scenarios.py
"""
import json
import time
from pathlib import Path

import requests

import pwhelp
import submit_form as sf

ROOT = Path(__file__).resolve().parent.parent
IDS = json.loads((ROOT / "data" / "instance_ids.local.json").read_text())["workflows"]
W = {k: IDS[v] for k, v in {
    "core": "Week10 V4 | sub | Core rules + AP ledger", "alerts": "Week10 V4 | sub | Alerts + Gemini explanation",
    "form": "Week10 V4 | E1 - AP intake form", "api": "Week10 V4 | E2 - Batch invoice API",
    "digest": "Week10 V4 | E3 - Daily AP exception digest"}.items()}
SESSION, _ = pwhelp.login_cookie()


def newest(wid):
    r = SESSION.get(f"{sf.URL}/rest/executions", params={"filter": json.dumps({"workflowId": wid}), "limit": 1}).json()
    rows = r["data"]["results"]
    return int(rows[0]["id"]) if rows else 0


def wait_and_save(prefix, marks, wids):
    """Wait for a new finished execution of each workflow in wids, then save it."""
    for key in wids:
        for _ in range(120):
            r = SESSION.get(f"{sf.URL}/rest/executions", params={"filter": json.dumps({"workflowId": W[key]}), "limit": 1}).json()
            row = r["data"]["results"][0] if r["data"]["results"] else None
            if row and int(row["id"]) > marks[key] and row["status"] not in ("running", "new", "waiting"):
                break
            time.sleep(1)
        else:
            raise TimeoutError(f"{prefix}: no execution for {key}")
        print(f"-- {prefix} / {key}: execution {row['id']} {row['status']}")
        sf.save_execution(SESSION, row["id"], f"{prefix}_{key}_execution_{row['id']}.json")


def marks():
    return {k: newest(v) for k, v in W.items()}


def api(prefix, payload_file):
    m = marks()
    body = json.loads((ROOT / "data" / "test_requests" / payload_file).read_text())
    resp = requests.post(f"{sf.URL}/webhook/meridian-ap-v4/batch", json=body, timeout=120).json()
    (ROOT / "data" / "test_requests" / payload_file.replace(".json", "_response.json")).write_text(json.dumps(resp, indent=2))
    for c in resp["cases"]:
        print(f"   {c['invoice_id']:<8} {c['priority']} {c['status']:<28} {c['control_flags']}")
    wait_and_save(prefix, m, ["api", "core", "alerts"])


def form(prefix, values):
    m = marks()
    sf.submit("meridian-ap-v4", W["form"], prefix, values)
    wait_and_save(prefix, m, ["core", "alerts"])


if __name__ == "__main__":
    print("== E2 batch API: the lab's 8 invoices in one call")
    api("E2_batch_lab8", "E2_batch_lab8.json")
    print("== E1 form: EPSILON invoice 1 of 2 (6,000 on PO-506)")
    form("E1_split_part1_INV-301", {"Team / clerk ID": "T01", "Invoice ID": "INV-301", "Supplier": "EPSILON",
                                    "Supplier invoice reference": "E-101", "Amount (USD)": "6000",
                                    "PO number (blank if none)": "PO-506", "Supplier says bank details changed?": "NO"})
    print("== E1 form: EPSILON invoice 2 of 2 (5,500 on PO-507) -> split under the $10k limit")
    form("E1_split_part2_INV-302", {"Team / clerk ID": "T01", "Invoice ID": "INV-302", "Supplier": "EPSILON",
                                    "Supplier invoice reference": "E-102", "Amount (USD)": "5500",
                                    "PO number (blank if none)": "PO-507", "Supplier says bank details changed?": "NO"})
    print("== E1 form: INV-201 keyed in again under a new invoice id -> persistent duplicate")
    form("E1_persistent_duplicate_INV-201B", {"Team / clerk ID": "T02", "Invoice ID": "INV-201B", "Supplier": "alpha",
                                              "Supplier invoice reference": " a-777 ", "Amount (USD)": "1250",
                                              "PO number (blank if none)": "PO-501", "Supplier says bank details changed?": "NO"})
    print("== E2 API: invoice against a CLOSED PO")
    api("E2_closed_po_INV-303", "E2_closed_po.json")
