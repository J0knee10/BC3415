"""Fills and submits an n8n form like a person would, saves screenshots, then saves the
resulting execution (with node-by-node data) to execution_logs/.

  python tools/submit_form.py <form-path> <workflow-id> <shot-prefix> field=value [field=value ...]
"""
import json
import os
import sys
import time
from pathlib import Path

from pwhelp import Browser, URL

LOGS = Path(__file__).resolve().parent.parent / "execution_logs"


def latest_execution(session, workflow_id, after_id):
    for _ in range(90):
        r = session.get(f"{URL}/rest/executions", params={"filter": json.dumps({"workflowId": workflow_id}), "limit": 1})
        rows = r.json()["data"]["results"]
        if rows and int(rows[0]["id"]) > after_id and rows[0]["status"] not in ("running", "new", "waiting"):
            return rows[0]
        time.sleep(1)
    raise TimeoutError("no finished execution")


def last_id(session, workflow_id):
    r = session.get(f"{URL}/rest/executions", params={"filter": json.dumps({"workflowId": workflow_id}), "limit": 1})
    rows = r.json()["data"]["results"]
    return int(rows[0]["id"]) if rows else 0


def unflatten(text):
    """Decode n8n's 'flatted' execution format: in objects and arrays every string is an
    index into the top-level list; top-level strings are the real string values."""
    table = json.loads(text)
    done = {}

    def resolve(i):
        if i in done:
            return done[i]
        v = table[i]
        if isinstance(v, dict):
            out = done[i] = {}
            for k, x in v.items():
                out[k] = resolve(int(x)) if isinstance(x, str) else x
        elif isinstance(v, list):
            out = done[i] = []
            out.extend(resolve(int(x)) if isinstance(x, str) else x for x in v)
        else:
            out = done[i] = v
        return out

    return resolve(0)


def redact(o):
    """Drop personal Telegram identifiers (recipient chat id, names, username) before saving."""
    if isinstance(o, dict):
        return {k: ({kk: ("<redacted>" if kk in ("id", "first_name", "last_name", "username") else vv)
                     for kk, vv in v.items()} if k == "chat" and isinstance(v, dict) else redact(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [redact(x) for x in o]
    return o


def node_summary(run_data):
    out = []
    for node, runs in run_data.items():
        r = runs[-1]
        items = (r.get("data") or {}).get("main") or [[]]
        n = sum(len(b or []) for b in items)
        out.append({"node": node, "status": r.get("executionStatus"), "items_out": n,
                    "ms": r.get("executionTime"), "error": (r.get("error") or {}).get("message")})
    return out


def save_execution(session, ex_id, name):
    full = session.get(f"{URL}/rest/executions/{ex_id}").json()["data"]
    data = redact(unflatten(full["data"]))
    run_data = data.get("resultData", {}).get("runData", {})
    doc = {k: full[k] for k in ("id", "mode", "status", "startedAt", "stoppedAt", "workflowId")}
    doc["workflow"] = full["workflowData"]["name"]
    doc["nodes"] = node_summary(run_data)
    doc["runData"] = run_data
    LOGS.mkdir(exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if chat:
        text = text.replace(chat, "<redacted>")
    (LOGS / name).write_text(text, encoding="utf-8")
    for s in doc["nodes"]:
        print(f"   {s['node']:<42} {s['status']:<8} items={s['items_out']}" + (f"  ERROR {s['error']}" if s["error"] else ""))
    return doc


def submit(form_path, workflow_id, prefix, values):
    b = Browser(width=900, height=1100)
    p = b.page
    before = last_id(b.session, workflow_id)
    p.goto(f"{URL}/form/{form_path}")
    p.wait_for_load_state("networkidle")
    for field, value in values.items():
        el = p.get_by_label(field, exact=True)
        if el.evaluate("e => e.tagName") == "SELECT":
            el.select_option(value)
        else:
            el.fill(value)
    b.shot(f"{prefix}_1_form_filled.png", full=True)
    p.get_by_role("button", name="Submit").click()
    p.wait_for_timeout(2500)
    ex = latest_execution(b.session, workflow_id, before)
    p.wait_for_timeout(1500)
    b.shot(f"{prefix}_2_form_response.png", full=True)
    save_execution(b.session, ex["id"], f"{prefix}_execution_{ex['id']}.json")
    print(f"execution {ex['id']} status={ex['status']}")
    b.close()
    return ex["id"]


if __name__ == "__main__":
    form_path, wf_id, prefix = sys.argv[1:4]
    submit(form_path, wf_id, prefix, dict(a.split("=", 1) for a in sys.argv[4:]))
