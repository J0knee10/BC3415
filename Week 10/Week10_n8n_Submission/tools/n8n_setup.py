"""Rebuilds the Week 10 n8n environment on a fresh local n8n from the files in this folder.

What it does (idempotent: safe to run again):
  1. logs in to n8n (owner account)
  2. creates the Data Tables from data/table_schemas.json and seeds the PO master
  3. creates the Telegram and Gemini credentials from environment variables
  4. imports every workflows/*.json, wiring in credential ids and Data Table ids, and
     publishes the trigger-based ones

Secrets never live in this folder. Set them in the environment first:
  N8N_URL (default http://localhost:5678), N8N_OWNER_EMAIL, N8N_OWNER_PASSWORD,
  TELEGRAM_BOT_TOKEN, GEMINI_API_KEY
The Telegram recipient is read by the workflows at run time as {{ $env.TELEGRAM_CHAT_ID }},
so n8n itself must be started with TELEGRAM_CHAT_ID and N8N_BLOCK_ENV_ACCESS_IN_NODE=false.

  python tools/n8n_setup.py            # everything
  python tools/n8n_setup.py --no-publish
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
URL = os.environ.get("N8N_URL", "http://localhost:5678").rstrip("/")

# Placeholders used inside the exported workflow JSON. Replaced on import, restored on export.
CRED_TELEGRAM = "Telegram (Week 10 bot)"
CRED_GEMINI = "Google Gemini (Week 10)"


class N8n:
    def __init__(self):
        self.s = requests.Session()
        r = self.s.post(f"{URL}/rest/login", json={
            "emailOrLdapLoginId": os.environ["N8N_OWNER_EMAIL"], "password": os.environ["N8N_OWNER_PASSWORD"]})
        r.raise_for_status()
        self.project_id = self.get("/rest/projects/personal")["id"]

    def _json(self, r):
        if not r.ok:
            raise RuntimeError(f"{r.request.method} {r.url} -> {r.status_code}: {r.text[:400]}")
        return r.json().get("data", r.json()) if r.content else None

    def get(self, path, **kw):
        return self._json(self.s.get(URL + path, **kw))

    def post(self, path, body=None):
        return self._json(self.s.post(URL + path, json=body))

    def patch(self, path, body):
        return self._json(self.s.patch(URL + path, json=body))

    # ---- data tables
    def tables(self):
        res = self.get(f"/rest/projects/{self.project_id}/data-tables", params={"take": 100, "skip": 0})
        rows = res["data"] if isinstance(res, dict) else res
        return {t["name"]: t for t in rows}

    def ensure_table(self, name, columns):
        existing = self.tables()
        if name in existing:
            return existing[name]["id"], False
        t = self.post(f"/rest/projects/{self.project_id}/data-tables", {"name": name, "columns": columns})
        return t["id"], True

    def rows(self, table_id):
        res = self.get(f"/rest/projects/{self.project_id}/data-tables/{table_id}/rows", params={"take": 1000, "skip": 0})
        return res["data"] if isinstance(res, dict) else res

    def insert_rows(self, table_id, rows):
        return self.post(f"/rest/projects/{self.project_id}/data-tables/{table_id}/insert", {"data": rows, "returnType": "count"})

    # ---- credentials
    def ensure_credential(self, name, ctype, data):
        for c in self.get("/rest/credentials"):
            if c["name"] == name:
                return c["id"]
        return self.post("/rest/credentials", {"name": name, "type": ctype, "data": data, "projectId": self.project_id})["id"]

    # ---- workflows
    def workflows(self):
        return {w["name"]: w for w in self.get("/rest/workflows", params={"filter": "{}", "take": 200})}


def wire(wf, creds, tables, workflow_ids):
    """Swap the portable references in an exported workflow for this instance's ids."""
    for node in wf["nodes"]:
        p = node.get("parameters", {})
        if node["type"] == "n8n-nodes-base.telegram":
            node["credentials"] = {"telegramApi": {"id": creds["telegram"], "name": CRED_TELEGRAM}}
        if node["type"] == "@n8n/n8n-nodes-langchain.lmChatGoogleGemini":
            node["credentials"] = {"googlePalmApi": {"id": creds["gemini"], "name": CRED_GEMINI}}
        dt = p.get("dataTableId")
        if isinstance(dt, dict) and dt.get("cachedResultName", dt.get("value")) in tables:
            name = dt.get("cachedResultName", dt["value"])
            p["dataTableId"] = {"__rl": True, "mode": "id", "value": tables[name], "cachedResultName": name}
        wid = p.get("workflowId")
        if isinstance(wid, dict) and wid.get("cachedResultName") in workflow_ids:
            wid["value"] = workflow_ids[wid["cachedResultName"]]
            wid["mode"] = "id"
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--reset-ledger", action="store_true", help="drop and recreate Week10_AP_Ledger_V4 (empty)")
    args = ap.parse_args()
    n = N8n()

    # 1. tables
    if args.reset_ledger and "Week10_AP_Ledger_V4" in n.tables():
        n._json(n.s.delete(f"{URL}/rest/projects/{n.project_id}/data-tables/{n.tables()['Week10_AP_Ledger_V4']['id']}"))
        print("dropped Week10_AP_Ledger_V4")
    schemas = json.loads((ROOT / "data" / "table_schemas.json").read_text())
    tables = {}
    for name, cols in schemas.items():
        tid, created = n.ensure_table(name, [{"name": c, "type": t} for c, t in cols])
        tables[name] = tid
        print(f"table {name:28} {tid}  {'created' if created else 'exists'}")
    po_rows = json.loads((ROOT / "data" / "po_master_seed.json").read_text())
    if not n.rows(tables["Week10_PO_Master"]):
        n.insert_rows(tables["Week10_PO_Master"], po_rows)
        print(f"seeded Week10_PO_Master with {len(po_rows)} rows")

    # 2. credentials
    creds = {
        "telegram": n.ensure_credential(CRED_TELEGRAM, "telegramApi", {"accessToken": os.environ["TELEGRAM_BOT_TOKEN"]}),
        "gemini": n.ensure_credential(CRED_GEMINI, "googlePalmApi", {
            "host": "https://generativelanguage.googleapis.com", "apiKey": os.environ["GEMINI_API_KEY"]}),
    }
    print("credentials", creds)

    # 3. workflows: sub-workflows first so callers can be wired to their ids
    files = sorted((ROOT / "workflows").glob("*.json"), key=lambda p: (0 if "_sub_" in p.name else 1, p.name))
    have = n.workflows()
    ids = {name: w["id"] for name, w in have.items()}
    for f in files:
        wf = json.loads(f.read_text(encoding="utf-8"))
        wf = wire(wf, creds, tables, ids)
        body = {k: wf[k] for k in ("name", "nodes", "connections", "settings") if k in wf}
        body.setdefault("settings", {"executionOrder": "v1"})
        if wf["name"] in have:
            cur = n.get(f"/rest/workflows/{have[wf['name']]['id']}")
            saved = n.patch(f"/rest/workflows/{cur['id']}", {**body, "versionId": cur["versionId"]})
            action = "updated"
        else:
            saved = n.post("/rest/workflows", {**body, "projectId": n.project_id})
            action = "imported"
        ids[wf["name"]] = saved["id"]
        has_trigger = any(x["type"] in ("n8n-nodes-base.formTrigger", "n8n-nodes-base.webhook", "n8n-nodes-base.scheduleTrigger",
                                       "n8n-nodes-base.executeWorkflowTrigger")
                          for x in wf["nodes"])
        published = ""
        if has_trigger and not args.no_publish:
            n.post(f"/rest/workflows/{saved['id']}/activate", {"versionId": saved["versionId"]})
            published = " + published"
        print(f"{action:8} {saved['id']}  {wf['name']}{published}")

    (ROOT / "data" / "instance_ids.local.json").write_text(json.dumps({"tables": tables, "workflows": ids}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
