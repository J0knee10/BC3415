"""Independent check of the bot's output against the ECB's official XML feed.

The bot gets its numbers by driving a browser over the ECB web pages. This script
gets the same reference rates a different way (the 90-day XML file the ECB
publishes for machines), recomputes every SGD conversion and the 1-month
statistics, and compares them with output/ap_fx_exposure_<date>.csv.

Standard library only:  python tools/verify_against_ecb_xml.py [rate_date]
"""
import csv
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XML_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


def read_settings():
    out = {"history_days": 22}
    with open(ROOT / "input" / "bot_settings.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["setting"] == "history_days":
                out["history_days"] = round(float(row["value"]))
    return out


def ecb_series():
    """{date: {ccy: units per EUR}} for the last ~90 days."""
    req = urllib.request.Request(XML_URL, headers={"User-Agent": "Mozilla/5.0"})
    tree = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
    days = {}
    for day in tree.iterfind(".//e:Cube[@time]", NS):
        days[day.get("time")] = {c.get("currency"): float(c.get("rate")) for c in day}
    return days


def sgd_per_unit(rates, ccy):
    if ccy == "SGD":
        return 1.0
    if ccy == "EUR":
        return rates["SGD"]
    return rates["SGD"] / rates[ccy]


def main():
    days = ecb_series()
    reports = sorted((ROOT / "output").glob("ap_fx_exposure_*.csv"))
    if not reports:
        sys.exit("No output/ap_fx_exposure_*.csv - run the bot first")
    path = ROOT / "output" / f"ap_fx_exposure_{sys.argv[1]}.csv" if len(sys.argv) > 1 else reports[-1]
    rate_date = path.stem.rsplit("_", 1)[-1]
    if rate_date not in days:
        sys.exit(f"{rate_date} not in the ECB 90-day feed")
    window = sorted(d for d in days if d <= rate_date)[-read_settings()["history_days"]:]

    print(f"Checking {path.name} against {XML_URL}")
    print(f"Reference date {rate_date}; 1-month window {window[0]} .. {window[-1]} ({len(window)} fixings)\n")
    checked = failed = 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            ccy = row["currency"]
            if ccy not in days[rate_date] and ccy not in ("EUR", "SGD"):
                ok = row["status"] == "EXCEPTION"
                print(f"{row['invoice_id']}  {ccy}: not an ECB currency -> bot status {row['status']}  {'OK' if ok else 'MISMATCH'}")
            else:
                amount = float(row["amount"])
                rate = sgd_per_unit(days[rate_date], ccy)
                high = max([sgd_per_unit(days[d], ccy) for d in window] + [rate])
                exp_sgd, exp_risk = round(amount * rate, 2), round(amount * (high - rate), 2)
                got_sgd, got_risk = float(row["amount_sgd"]), float(row["fx_risk_sgd"])
                ok = abs(exp_sgd - got_sgd) <= 0.01 and abs(exp_risk - got_risk) <= 0.01
                print(f"{row['invoice_id']}  {ccy} {amount:>14,.2f}  SGD bot {got_sgd:>11,.2f} / feed {exp_sgd:>11,.2f}"
                      f"   risk bot {got_risk:>8,.2f} / feed {exp_risk:>8,.2f}   {'OK' if ok else 'MISMATCH'}")
            checked += 1
            failed += not ok
    print(f"\n{checked} invoices checked, {failed} mismatches -> {'PASS' if not failed else 'FAIL'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
